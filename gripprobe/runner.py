from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Callable, Iterable

from gripprobe.adapters.base import AdapterError
from gripprobe.adapters.aider import AiderAdapter
from gripprobe.adapters.codex import CodexAdapter
from gripprobe.adapters.continue_cli import ContinueCliAdapter
from gripprobe.adapters.gptme import GptmeAdapter
from gripprobe.adapters.opencode import OpencodeAdapter
from gripprobe.adapters.pi import PiAdapter
from gripprobe.case_result import build_case_result
from gripprobe.cli_agent_version import parse_cli_agent_version, with_cli_agent_version
from gripprobe.event_evaluator import apply_event_evaluation
from gripprobe.fixtures import (
    WebNonceChallenge,
    WebSearchChallenge,
    patch_web_nonce_validators,
    patch_web_search_validators,
    prepare_web_nonce_workspace,
    prepare_web_search_workspace,
    prepare_workspace,
)
from gripprobe.phase_execution import run_case_with_phase_proxy
from gripprobe.models import BackendSpec, CaseDefinition, CaseResult, CliAgentSpec, ModelSpec, TestSpec
from gripprobe.proxy_capture import (
    build_proxy_capture_options,
    proxy_artifact_path,
    should_disable_proxy_for_cli_agent,
)
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import create_run_paths, write_json
from gripprobe.spec_loader import load_cli_agent_specs, load_model_specs, load_test_specs
from gripprobe.telemetry import (
    TelemetryProxyStatus,
    extract_and_persist_case_telemetry,
    normalize_telemetry_proxy_mode,
)
from gripprobe.telemetry_proxy import OllamaTelemetryProxy


DEFAULT_BACKEND = "ollama"


def _find_one(items, attr: str, value: str):
    for item in items:
        if getattr(item, attr) == value or getattr(item, "label", None) == value:
            return item
    raise ValueError(f"Could not find {attr}={value}")


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(f"[{_timestamp()}] {message}")


def _collect_cli_agent_runtime_metadata(executable: str) -> dict[str, str]:
    executable_name = str(executable)
    metadata: dict[str, str] = {
        "cli_agent_executable": executable_name,
        "shell_executable": executable_name,
    }
    resolve_executable: Callable[[str], str | None] = getattr(shutil, "which")
    resolved = resolve_executable(executable_name)
    if resolved:
        home = str(Path.home())
        sanitized_path = resolved.replace(home, "$HOME", 1) if resolved.startswith(home) else resolved
        metadata["cli_agent_executable_path"] = sanitized_path
        metadata["shell_executable_path"] = sanitized_path
    try:
        probe = subprocess.run(
            [executable_name, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return with_cli_agent_version(metadata)
    version_output = (probe.stdout or probe.stderr or "").strip()
    if version_output:
        first_line = version_output.splitlines()[0]
        metadata["cli_agent_version"] = parse_cli_agent_version(first_line)
        metadata["shell_version"] = first_line
    metadata["cli_agent_version_exit_code"] = str(probe.returncode)
    metadata["shell_version_exit_code"] = str(probe.returncode)
    for key in (
        "OLLAMA_CONTEXT_LENGTH",
        "OLLAMA_NUM_PARALLEL",
        "OLLAMA_FLASH_ATTENTION",
        "OLLAMA_KV_CACHE_TYPE",
    ):
        value = os.environ.get(key)
        if value:
            metadata[key.lower()] = value
    return with_cli_agent_version(metadata)


def _collect_shell_runtime_metadata(executable: str) -> dict[str, str]:
    # Legacy compatibility alias for existing tests/callers.
    return _collect_cli_agent_runtime_metadata(executable)


def _run_probe_command(args: list[str], timeout_seconds: int = 5) -> dict[str, str | int | float]:
    started = time.monotonic()
    command = " ".join(args)
    try:
        probe = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "command": command,
            "status": "unavailable",
            "error": "command not found",
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "status": "timeout",
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "command": command,
            "status": "error",
            "error": str(exc),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    return {
        "command": command,
        "status": "ok",
        "exit_code": probe.returncode,
        "stdout": (probe.stdout or "").strip(),
        "stderr": (probe.stderr or "").strip(),
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def _run_remote_probe_command(target: str, remote_command: str, timeout_seconds: int = 5) -> dict[str, str | int | float]:
    return _run_probe_command(
        ["ssh", target, remote_command],
        timeout_seconds=timeout_seconds,
    )


def _ollama_base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    if not host:
        host = "http://127.0.0.1:11434"
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/")


def _normalize_http_base(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raw = "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    return raw.rstrip("/")


def _resolve_ollama_host_for_backend(backend: BackendSpec) -> str:
    env = backend.env or {}
    explicit_host = str(env.get("OLLAMA_HOST", "")).strip()
    if explicit_host:
        return _normalize_http_base(explicit_host)
    explicit_api_base = str(env.get("OLLAMA_API_BASE", "")).strip()
    if explicit_api_base:
        normalized = _normalize_http_base(explicit_api_base)
        if normalized.endswith("/v1"):
            normalized = normalized[:-3]
        return normalized.rstrip("/")
    return _ollama_base_url()

def _ollama_host_name() -> str:
    parsed = urlparse(_ollama_base_url())
    return parsed.hostname or ""


def _looks_local_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in {"", "localhost", "127.0.0.1", "::1"}


def _ollama_probe_target() -> str | None:
    explicit = os.environ.get("GRIPPROBE_OLLAMA_SSH_TARGET", "").strip()
    if explicit:
        return explicit
    host = _ollama_host_name()
    if _looks_local_host(host):
        return None
    return host


def _run_http_probe(url: str, timeout_seconds: int = 5) -> dict[str, str | int | float]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            status_code = getattr(response, "status", None) or response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        return {
            "command": f"GET {url}",
            "status": "http_error",
            "http_status": exc.code,
            "stdout": body,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except urllib.error.URLError as exc:
        return {
            "command": f"GET {url}",
            "status": "connection_error",
            "error": str(exc.reason),
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except TimeoutError:
        return {
            "command": f"GET {url}",
            "status": "timeout",
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    return {
        "command": f"GET {url}",
        "status": "ok",
        "http_status": status_code,
        "stdout": body,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def _fetch_ollama_model_digest(model_id: str, timeout_seconds: int = 10) -> str | None:
    url = f"{_ollama_base_url()}/api/tags"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    models = payload.get("models")
    if not isinstance(models, list):
        return None
    for item in models:
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip() != model_id:
            continue
        digest = str(item.get("digest", "")).strip()
        if digest:
            return digest
    return None


def _fetch_ollama_model_modelfile(model_id: str, timeout_seconds: int = 10) -> str | None:
    url = f"{_ollama_base_url()}/api/show"
    for key in ("name", "model"):
        request = urllib.request.Request(
            url,
            data=json.dumps({key: model_id}).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        modelfile = payload.get("modelfile")
        if isinstance(modelfile, str) and modelfile.strip():
            return modelfile.rstrip() + "\n"
    return None


def _resolve_model_hash(backend: BackendSpec, cli_model_hash: str | None = None) -> str:
    if backend.id == "ollama":
        digest = _fetch_ollama_model_digest(backend.model_id)
        if digest:
            return digest
    if cli_model_hash:
        return cli_model_hash
    if backend.model_hash:
        return backend.model_hash
    return "unknown"


def _collect_runtime_snapshot(include_ollama: bool = False) -> dict[str, object]:
    remote_target = _ollama_probe_target() if include_ollama else None
    if remote_target:
        probes: dict[str, dict[str, str | int | float]] = {
            "loadavg": _run_remote_probe_command(remote_target, "cat /proc/loadavg"),
            "meminfo": _run_remote_probe_command(remote_target, "cat /proc/meminfo"),
            "nvidia_smi": _run_remote_probe_command(
                remote_target,
                "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits",
            ),
        }
    else:
        probes = {
            "loadavg": _run_probe_command(["cat", "/proc/loadavg"]),
            "meminfo": _run_probe_command(["cat", "/proc/meminfo"]),
            "nvidia_smi": _run_probe_command(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ]
            ),
        }
    if include_ollama:
        probes["ollama_ps"] = _run_http_probe(f"{_ollama_base_url()}/api/ps", timeout_seconds=10)
    return {
        "captured_at": _timestamp(),
        "probes": probes,
    }


def _write_ollama_modelfile_artifact(case_dir: Path, modelfile_text: str | None) -> None:
    if not modelfile_text:
        return
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "model.modelfile").write_text(modelfile_text, encoding="utf-8")


def _adapter_for(cli_agent_spec: CliAgentSpec):
    if cli_agent_spec.id == "aider":
        return AiderAdapter(cli_agent_spec)
    if cli_agent_spec.id == "codex":
        return CodexAdapter(cli_agent_spec)
    if cli_agent_spec.id == "gptme":
        return GptmeAdapter(cli_agent_spec)
    if cli_agent_spec.id == "continue-cli":
        return ContinueCliAdapter(cli_agent_spec)
    if cli_agent_spec.id == "opencode":
        return OpencodeAdapter(cli_agent_spec)
    if cli_agent_spec.id == "pi":
        return PiAdapter(cli_agent_spec)
    raise ValueError(f"Unsupported CLI agent adapter: {cli_agent_spec.id}")


def _apply_model_policy_overrides(cli_agent_spec: CliAgentSpec, model_spec: ModelSpec) -> CliAgentSpec:
    overrides = model_spec.policy_overrides or {}
    cli_agent_timeouts = overrides.get("cli_agent_timeout_seconds")
    if not isinstance(cli_agent_timeouts, dict):
        legacy_shell_timeouts = overrides.get("shell_timeout_seconds")
        cli_agent_timeouts = legacy_shell_timeouts if isinstance(legacy_shell_timeouts, dict) else None
    if isinstance(cli_agent_timeouts, dict):
        timeout_override = cli_agent_timeouts.get(cli_agent_spec.id)
        if isinstance(timeout_override, int) and timeout_override > 0:
            return cli_agent_spec.model_copy(update={"timeout_seconds": timeout_override})
    return cli_agent_spec


def _apply_prompt_policy_overrides(prompt: str, model_spec: ModelSpec) -> str:
    overrides = model_spec.policy_overrides or {}
    updated = prompt

    if bool(overrides.get("prompt_append_no_think")) and "/no_think" not in updated:
        updated = f"{updated.rstrip()}\n/no_think\n"

    prompt_suffix = overrides.get("prompt_suffix")
    if isinstance(prompt_suffix, str) and prompt_suffix:
        updated = f"{updated.rstrip()}\n{prompt_suffix.rstrip()}\n"

    return updated

def _filter_tests(tests: list[TestSpec], selected: Iterable[str] | None) -> list[TestSpec]:
    if not selected:
        return tests
    wanted = set(selected)
    return [test for test in tests if test.id in wanted or test.title in wanted]


def _filter_tests_by_tags(tests: list[TestSpec], selected_tags: Iterable[str] | None) -> list[TestSpec]:
    if not selected_tags:
        return tests
    wanted = set(selected_tags)
    return [test for test in tests if wanted.intersection(test.tags)]


def _filter_formats(formats: list[str], selected: Iterable[str] | None) -> list[str]:
    if not selected:
        return formats
    wanted = set(selected)
    return [fmt for fmt in formats if fmt in wanted]


def _select_backend(model_spec: ModelSpec, backend_name: str) -> BackendSpec:
    for backend in model_spec.backends:
        if backend.id == backend_name:
            return backend
    available = ", ".join(backend.id for backend in model_spec.backends) or "<none>"
    raise ValueError(
        f"Model {model_spec.id} does not define backend={backend_name}. Available: {available}"
    )


def _harness_error_result(case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec, message: str) -> CaseResult:
    return build_case_result(
        case=case,
        model_spec=model_spec,
        test_spec=test_spec,
        status="HARNESS_ERROR",
        invoked="no",
        match_percent=0,
        warmup_seconds=0.0,
        measured_seconds=0.0,
        metadata={
            "error": message,
            "model_hash": case.model_hash,
            **case.run_metadata,
        },
    )

def run(
    root: Path,
    cli_agent_name: str | None = None,
    model_name: str = "",
    backend_name: str = DEFAULT_BACKEND,
    run_id: str | None = None,
    tests_filter: list[str] | None = None,
    test_tags_filter: list[str] | None = None,
    formats_filter: list[str] | None = None,
    container_image: str | None = None,
    keep_system_messages: bool = False,
    model_hash: str | None = None,
    run_metadata: dict[str, str] | None = None,
    progress: Callable[[str], None] | None = None,
    shell_name: str | None = None,
    telemetry_proxy_mode: str = "auto",
    runs_root: Path | None = None,
) -> tuple[Path, list[CaseResult]]:
    proxy_mode = normalize_telemetry_proxy_mode(telemetry_proxy_mode)
    tests = load_test_specs(root)
    models = load_model_specs(root)
    cli_agents = load_cli_agent_specs(root)
    selected_cli_agent = (cli_agent_name or shell_name or "").strip()
    if not selected_cli_agent:
        raise ValueError("cli_agent_name is required")
    if not model_name:
        raise ValueError("model_name is required")

    model_spec: ModelSpec = _find_one(models, "label", model_name)
    cli_agent_spec: CliAgentSpec = _apply_model_policy_overrides(
        _find_one(cli_agents, "id", selected_cli_agent),
        model_spec,
    )
    backend = _select_backend(model_spec, backend_name)
    resolved_model_hash = _resolve_model_hash(backend, model_hash)
    ollama_modelfile = _fetch_ollama_model_modelfile(backend.model_id) if backend.id == "ollama" else None
    adapter = _adapter_for(cli_agent_spec)
    run_paths = create_run_paths(root, run_id=run_id, runs_root=runs_root)
    runtime_metadata = _collect_shell_runtime_metadata(cli_agent_spec.executable)
    runtime_snapshots = {
        "run_started": _collect_runtime_snapshot(include_ollama=backend.id == "ollama"),
    }
    merged_run_metadata = {
        **runtime_metadata,
        **(run_metadata or {}),
        "runtime_snapshots": runtime_snapshots,
    }
    _emit(
        progress,
        "START "
        f"cli_agent={cli_agent_spec.id} "
        f"model={model_spec.label} "
        f"backend={backend.id} "
        f"report={run_paths.reports_dir / 'summary.html'}",
    )

    results: list[CaseResult] = []
    tests = _filter_tests(tests, tests_filter)
    tests = _filter_tests_by_tags(tests, test_tags_filter)
    formats = [
        fmt for fmt in model_spec.supported_formats if fmt in cli_agent_spec.supported_formats
    ] or cli_agent_spec.supported_formats
    formats = _filter_formats(formats, formats_filter)

    for tool_format in formats:
        format_started_at = time.monotonic()
        _emit(
            progress,
            "START "
            f"model={model_spec.label} "
            f"backend={backend.id} "
            f"format={tool_format}",
        )
        format_cases = 0
        for test_spec in tests:
            if test_spec.supported_cli_agents and cli_agent_spec.id not in test_spec.supported_cli_agents:
                continue
            if test_spec.supported_formats and tool_format not in test_spec.supported_formats:
                continue
            format_cases += 1
            case_id = f"{cli_agent_spec.id}__{model_spec.id}__{backend.id}__{tool_format}__{test_spec.id}"
            case_started_at = time.monotonic()
            _emit(
                progress,
                "START "
                f"model={model_spec.label} "
                f"backend={backend.id} "
                f"format={tool_format} "
                f"test={test_spec.id} "
                f"case={case_id}",
            )
            case_dir = run_paths.cases_dir / case_id
            warmup_workspace_dir = case_dir / "workspace-warmup"
            workspace_dir = case_dir / "workspace"
            prepare_workspace(warmup_workspace_dir, test_spec.id)
            prepare_workspace(workspace_dir, test_spec.id)
            _write_ollama_modelfile_artifact(case_dir, ollama_modelfile)
            active_test_spec = test_spec
            web_challenge: WebNonceChallenge | None = None
            web_search_challenge: WebSearchChallenge | None = None
            if test_spec.id == "web_nonce_proof":
                web_challenge = WebNonceChallenge(case_dir)
                web_challenge.start()
                prepare_web_nonce_workspace(warmup_workspace_dir, web_challenge.warmup_url)
                prepare_web_nonce_workspace(workspace_dir, web_challenge.measured_url)
                assert web_challenge is not None
                active_test_spec = patch_web_nonce_validators(test_spec, web_challenge)
            if test_spec.id in {"web_search_json_ranked", "web_fetch_json_raw"}:
                search_challenge = WebSearchChallenge(case_dir)
                web_search_challenge = search_challenge
                search_challenge.start()
                prepare_web_search_workspace(
                    warmup_workspace_dir,
                    search_challenge.warmup_url,
                    search_challenge.warmup_query,
                    search_challenge.required_token,
                )
                prepare_web_search_workspace(
                    workspace_dir,
                    search_challenge.measured_url,
                    search_challenge.measured_query,
                    search_challenge.required_token,
                )
                active_test_spec = patch_web_search_validators(test_spec, search_challenge)
            proxy_capture_status: TelemetryProxyStatus = "skipped"
            proxy_capture_skip_reason: str | None = None
            proxy_capture_artifact_relpaths: dict[str, str] = {}
            proxy_capture_error: str | None = None
            proxy_runtime_metadata: dict[str, str] = {}
            upstream_base_url: str | None = None
            proxy_disabled = should_disable_proxy_for_cli_agent(cli_agent_spec, model_spec)
            if proxy_mode == "off":
                proxy_capture_skip_reason = "disabled"
            elif proxy_disabled:
                proxy_capture_skip_reason = "disabled_by_cli_agent_policy"
            elif backend.id != "ollama":
                if proxy_mode == "force":
                    proxy_capture_status = "error"
                    proxy_capture_skip_reason = "unsupported_backend"
                else:
                    proxy_capture_skip_reason = "unsupported_backend"
            else:
                resolved_upstream_base_url = _resolve_ollama_host_for_backend(backend)
                upstream_base_url = resolved_upstream_base_url
                proxy_capture_status = "collected"
                proxy_capture_skip_reason = None
                proxy_runtime_metadata = {
                    "telemetry_proxy_upstream_base_url": resolved_upstream_base_url,
                    "telemetry_proxy_warmup_artifact_path": proxy_artifact_path("warmup"),
                    "telemetry_proxy_measured_artifact_path": proxy_artifact_path("measured"),
                }
            case = CaseDefinition(
                case_id=case_id,
                run_id=run_paths.run_id,
                cli_agent_id=cli_agent_spec.id,
                cli_agent_label=cli_agent_spec.label,
                model_id=model_spec.id,
                model_label=model_spec.label,
                backend_id=backend.id,
                backend_model_id=backend.model_id,
                cli_agent_model_id=backend.cli_agent_model_id,
                model_hash=resolved_model_hash,
                quantization=model_spec.quantization,
                tool_format=tool_format,
                test_id=active_test_spec.id,
                test_title=active_test_spec.title,
                prompt=_apply_prompt_policy_overrides(active_test_spec.prompt, model_spec),
                warmup_workspace_dir=warmup_workspace_dir,
                workspace_dir=workspace_dir,
                case_dir=case_dir,
                allowed_tools=active_test_spec.allowed_tools,
                container_image=container_image or cli_agent_spec.container_image,
                keep_system_messages=keep_system_messages,
                run_metadata={**merged_run_metadata, **proxy_runtime_metadata},
            )
            case_runtime_before = _collect_runtime_snapshot(include_ollama=backend.id == "ollama")
            try:
                if (
                    proxy_mode != "off"
                    and backend.id == "ollama"
                    and upstream_base_url is not None
                    and not proxy_disabled
                ):
                    result, phase_proxy_metadata, proxy_capture_artifact_relpaths, proxy_capture_error = run_case_with_phase_proxy(
                        adapter=adapter,
                        case=case,
                        model_spec=model_spec,
                        test_spec=active_test_spec,
                        upstream_base_url=upstream_base_url,
                        proxy_options=build_proxy_capture_options(case, cli_agent_spec, model_spec),
                        proxy_factory=OllamaTelemetryProxy,
                    )
                    proxy_runtime_metadata = {**proxy_runtime_metadata, **phase_proxy_metadata}
                else:
                    result = adapter.run_case(case, model_spec, active_test_spec)
            except AdapterError as exc:
                result = _harness_error_result(case, model_spec, active_test_spec, str(exc))
            finally:
                if web_challenge is not None:
                    web_challenge.stop()
                if web_search_challenge is not None:
                    web_search_challenge.stop()
            if (
                proxy_mode != "off"
                and backend.id == "ollama"
                and not proxy_disabled
            ):
                expected_proxy_artifacts = {
                    "warmup": proxy_artifact_path("warmup"),
                    "measured": proxy_artifact_path("measured"),
                }
                missing_phase = next(
                    (
                        phase
                        for phase, relpath in expected_proxy_artifacts.items()
                        if not (case_dir / relpath).exists()
                    ),
                    None,
                )
                if missing_phase is not None:
                    proxy_capture_status = "error"
                    proxy_capture_skip_reason = "capture_missing"
                    proxy_capture_artifact_relpaths = {
                        phase: relpath
                        for phase, relpath in expected_proxy_artifacts.items()
                        if (case_dir / relpath).exists()
                    }
                else:
                    proxy_capture_status = "collected"
                    proxy_capture_skip_reason = None
                    proxy_capture_artifact_relpaths = expected_proxy_artifacts
            case_runtime_after = _collect_runtime_snapshot(include_ollama=backend.id == "ollama")
            telemetry_metadata = extract_and_persist_case_telemetry(
                case_dir=case_dir,
                run_id=run_paths.run_id,
                case_id=case_id,
                cli_agent_id=cli_agent_spec.id,
                telemetry_proxy_mode=proxy_mode,
                proxy_capture_status=proxy_capture_status,
                proxy_capture_skip_reason=proxy_capture_skip_reason,
                proxy_artifact_relpaths=proxy_capture_artifact_relpaths,
            )
            result.metadata = {
                **merged_run_metadata,
                **proxy_runtime_metadata,
                **result.metadata,
                **({"telemetry_proxy_runtime_error": proxy_capture_error} if proxy_capture_error else {}),
                **(
                    {
                        "web_challenge": {
                            "base_url": web_challenge.base_url,
                            "warmup_path": web_challenge.warmup_path,
                            "measured_path": web_challenge.measured_path,
                            "request_log": str(web_challenge.request_log_path),
                        }
                    }
                    if web_challenge is not None
                    else {}
                ),
                **(
                    {
                        "web_search_challenge": {
                            "base_url": web_search_challenge.base_url,
                            "warmup_path": web_search_challenge.warmup_path,
                            "measured_path": web_search_challenge.measured_path,
                            "request_log": str(web_search_challenge.request_log_path),
                            "query": web_search_challenge.measured_query,
                            "required_token": web_search_challenge.required_token,
                        }
                    }
                    if web_search_challenge is not None
                    else {}
                ),
                "runtime_snapshots": {
                    "before": case_runtime_before,
                    "after": case_runtime_after,
                },
                **telemetry_metadata,
            }
            if proxy_capture_error != "adapter_missing_run_command":
                apply_event_evaluation(result, proxy_required=proxy_mode == "force")
            write_json(case_dir / "case.json", result.model_dump())
            results.append(result)
            _emit(
                progress,
                "DONE "
                f"model={model_spec.label} "
                f"backend={backend.id} "
                f"format={tool_format} "
                f"test={test_spec.id} "
                f"case={case_id} "
                f"status={result.status} "
                f"seconds={time.monotonic() - case_started_at:.3f}",
            )
        _emit(
            progress,
            "DONE "
            f"model={model_spec.label} "
            f"backend={backend.id} "
            f"format={tool_format} "
            f"cases={format_cases} "
            f"seconds={time.monotonic() - format_started_at:.3f}",
        )

    write_markdown_summary(results, run_paths.reports_dir / "summary.md")
    merged_run_metadata["runtime_snapshots"]["run_finished"] = _collect_runtime_snapshot(include_ollama=backend.id == "ollama")
    write_html_summary(results, run_paths.reports_dir / "summary.html")
    write_json(
        run_paths.run_dir / "manifest.json",
        {
            "run_id": run_paths.run_id,
            "cli_agent_id": cli_agent_spec.id,
            "model": model_spec.id,
            "backend": backend.id,
            "model_hash": resolved_model_hash,
            "cases": len(results),
            "formats": formats,
            "tests": [test.id for test in tests],
            "container_image": container_image or cli_agent_spec.container_image,
            "keep_system_messages": keep_system_messages,
            "run_metadata": merged_run_metadata,
        },
    )
    _emit(
        progress,
        "DONE "
        f"cli_agent={cli_agent_spec.id} "
        f"model={model_spec.label} "
        f"backend={backend.id} "
        f"cases={len(results)} "
        f"report={run_paths.reports_dir / 'summary.html'}",
    )
    return run_paths.run_dir, results
