from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import json
import secrets
import threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlsplit
from typing import Any, Callable, Iterable, Literal

from gripprobe.adapters.base import AdapterError
from gripprobe.adapters.aider import AiderAdapter
from gripprobe.adapters.codex import CodexAdapter
from gripprobe.adapters.continue_cli import ContinueCliAdapter
from gripprobe.adapters.gptme import GptmeAdapter
from gripprobe.adapters.opencode import OpencodeAdapter
from gripprobe.case_result import build_case_result
from gripprobe.cli_agent_version import parse_cli_agent_version, with_cli_agent_version
from gripprobe.event_evaluator import apply_event_evaluation
from gripprobe.models import BackendSpec, CaseDefinition, CaseResult, CliAgentSpec, ModelSpec, TestSpec
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


def _create_ollama_telemetry_proxy(
    case_dir: Path,
    upstream_base_url: str,
    artifact_relpath: str = "artifacts/proxy.measured.http.jsonl",
    filter_tools: bool = False,
    allowed_tool_names: list[str] | None = None,
    strip_git_context: bool = False,
    strip_commit_signature_context: bool = False,
    reasoning_effort: str | None = None,
    temperature_override: float | None = None,
    capture_ollama_usage: bool = False,
    capture_stream_timing: bool = False,
) -> OllamaTelemetryProxy:
    return OllamaTelemetryProxy(
        case_dir=case_dir,
        upstream_base_url=upstream_base_url,
        artifact_relpath=artifact_relpath,
        filter_tools=filter_tools,
        allowed_tool_names=allowed_tool_names,
        strip_git_context=strip_git_context,
        strip_commit_signature_context=strip_commit_signature_context,
        reasoning_effort=reasoning_effort,
        temperature_override=temperature_override,
        capture_ollama_usage=capture_ollama_usage,
        capture_stream_timing=capture_stream_timing,
    )


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


def _prepare_workspace(path: Path, test_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for file in path.iterdir():
        if file.is_file() or file.is_symlink():
            file.unlink()
        elif file.is_dir():
            shutil.rmtree(file)
    if test_id in {"patch_file", "patch_file_codex_apply_patch", "patch_file_shell"}:
        (path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")
    if test_id == "patch_file_prepared":
        (path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")
        (path / "prepared.patch").write_text(
            "<<<<<<< ORIGINAL\n"
            "STATUS=old\n"
            "=======\n"
            "STATUS=new\n"
            ">>>>>>> UPDATED\n",
            encoding="utf-8",
        )
    if test_id == "weekly_plan_next_week":
        current_monday = date.today() - timedelta(days=date.today().weekday())
        next_monday = current_monday + timedelta(days=7)
        (path / "Plan.md").write_text(
            "# Plan\n\n"
            f"## Week of {current_monday.isoformat()}\n"
            "- [ ] Carry over outstanding items\n\n"
            f"## Week of {next_monday.isoformat()}\n"
            "- [ ] Placeholder for planning\n\n"
            "## Monthly Summary\n"
            "- [ ] No entries yet\n",
            encoding="utf-8",
        )
    if test_id == "json_rank_from_file":
        (path / "query.txt").write_text("weekly plan static fixture checkbox\n", encoding="utf-8")
        (path / "required-token.txt").write_text("static-token-abc123\n", encoding="utf-8")
        (path / "search-response.json").write_text(
            json.dumps(
                {
                    "query": "weekly plan static fixture checkbox",
                    "results": [
                        {
                            "id": "doc-intro",
                            "title": "Markdown planning intro",
                            "url": "https://kb.example/intro",
                            "snippet": "Basic markdown checklist examples.",
                            "score": 0.72,
                            "lang": "en",
                        },
                        {
                            "id": "doc-static-top",
                            "title": "Weekly planning with checkboxes",
                            "url": "https://kb.example/static-top",
                            "snippet": "Actionable template. Required token: static-token-abc123.",
                            "score": 0.98,
                            "lang": "en",
                        },
                        {
                            "id": "doc-static-alt",
                            "title": "Alternate planning approach",
                            "url": "https://kb.example/static-alt",
                            "snippet": "Also mentions token static-token-abc123, but less relevant.",
                            "score": 0.91,
                            "lang": "en",
                        },
                        {
                            "id": "doc-noise",
                            "title": "General productivity",
                            "url": "https://kb.example/noise",
                            "snippet": "Time-blocking article.",
                            "score": 0.44,
                            "lang": "en",
                        },
                    ],
                    "total": 4,
                    "returned": 4,
                    "error": "",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


class _WebNonceChallenge:
    def __init__(self, case_dir: Path):
        self.case_dir = case_dir
        self.request_log_path = case_dir / "web-challenge-requests.json"
        self.warmup_token = secrets.token_urlsafe(18)
        self.measured_token = secrets.token_urlsafe(18)
        self.warmup_nonce = secrets.token_hex(16)
        self.warmup_payload = secrets.token_hex(12)
        self.measured_nonce = secrets.token_hex(16)
        self.measured_payload = secrets.token_hex(12)
        self._request_paths: list[str] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""
        self.warmup_path = f"/challenge/{self.warmup_token}"
        self.measured_path = f"/challenge/{self.measured_token}"
        self.warmup_url = ""
        self.measured_url = ""

    @staticmethod
    def _proof(nonce: str, payload: str) -> str:
        return hashlib.sha256(f"{nonce}:{payload}".encode("utf-8")).hexdigest()

    @property
    def measured_proof(self) -> str:
        return self._proof(self.measured_nonce, self.measured_payload)

    def _write_request_log(self) -> None:
        self.request_log_path.write_text(
            json.dumps(self._request_paths, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _register_hit(self, path: str) -> None:
        with self._lock:
            self._request_paths.append(path)
            self._write_request_log()

    def _response_for_path(self, path: str) -> dict[str, str] | None:
        if path == self.warmup_path:
            return {"nonce": self.warmup_nonce, "payload": self.warmup_payload}
        if path == self.measured_path:
            return {"nonce": self.measured_nonce, "payload": self.measured_payload}
        return None

    def start(self) -> None:
        challenge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlsplit(self.path)
                response = challenge._response_for_path(parsed.path)
                if response is None:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"not_found"}')
                    return
                challenge._register_hit(parsed.path)
                payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args):
                return

        def _handler_factory(request: Any, client_address: Any, server: ThreadingHTTPServer) -> BaseHTTPRequestHandler:
            return Handler(request, client_address, server)

        self.case_dir.mkdir(parents=True, exist_ok=True)
        self._write_request_log()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self.warmup_url = f"{self.base_url}{self.warmup_path}"
        self.measured_url = f"{self.base_url}{self.measured_path}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._write_request_log()


class _WebSearchChallenge:
    def __init__(self, case_dir: Path):
        self.case_dir = case_dir
        self.request_log_path = case_dir / "web-search-requests.json"
        self.warmup_token = secrets.token_urlsafe(18)
        self.measured_token = secrets.token_urlsafe(18)
        self.warmup_path = f"/search/{self.warmup_token}"
        self.measured_path = f"/search/{self.measured_token}"
        self.base_url = ""
        self.warmup_url = ""
        self.measured_url = ""
        self.warmup_query = f"warmup query {secrets.token_hex(4)}"
        self.measured_query = f"weekly plan {secrets.token_hex(6)} checkbox"
        self.required_token = secrets.token_hex(8)
        self.selected_id = f"doc-{secrets.token_hex(4)}"
        self.selected_url = f"https://kb.example/{secrets.token_hex(6)}"
        self.selected_score = 0.97
        self.warmup_results = self._build_results(
            required_token=secrets.token_hex(6),
            selected_id=f"doc-{secrets.token_hex(4)}",
            selected_url=f"https://kb.example/{secrets.token_hex(6)}",
            selected_score=0.94,
        )
        self.measured_results = self._build_results(
            required_token=self.required_token,
            selected_id=self.selected_id,
            selected_url=self.selected_url,
            selected_score=self.selected_score,
        )
        self._request_paths: list[str] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @staticmethod
    def _build_results(required_token: str, selected_id: str, selected_url: str, selected_score: float) -> list[dict[str, Any]]:
        return [
            {
                "id": "doc-intro",
                "title": "Markdown planning intro",
                "url": "https://kb.example/intro",
                "snippet": "Basic markdown checklist examples.",
                "score": 0.72,
                "lang": "en",
            },
            {
                "id": selected_id,
                "title": "Weekly planning with checkboxes",
                "url": selected_url,
                "snippet": f"Actionable template. Required token: {required_token}.",
                "score": selected_score,
                "lang": "en",
            },
            {
                "id": "doc-alt-token",
                "title": "Alternate planning approach",
                "url": "https://kb.example/alt",
                "snippet": f"Also mentions token {required_token}, but less relevant.",
                "score": selected_score - 0.13,
                "lang": "en",
            },
            {
                "id": "doc-ru",
                "title": "План на неделю",
                "url": "https://kb.example/ru-weekly",
                "snippet": "Русскоязычный шаблон.",
                "score": 0.61,
                "lang": "ru",
            },
            {
                "id": "doc-de",
                "title": "Wochenplan Vorlage",
                "url": "https://kb.example/de-weekly",
                "snippet": "Deutsche Checklisten-Idee.",
                "score": 0.59,
                "lang": "de",
            },
            {
                "id": "doc-noise-1",
                "title": "General productivity",
                "url": "https://kb.example/noise-1",
                "snippet": "Time-blocking article.",
                "score": 0.44,
                "lang": "en",
            },
            {
                "id": "doc-noise-2",
                "title": "Meeting notes",
                "url": "https://kb.example/noise-2",
                "snippet": "Unrelated meeting summary.",
                "score": 0.37,
                "lang": "en",
            },
            {
                "id": "doc-noise-3",
                "title": "Shopping checklist",
                "url": "https://kb.example/noise-3",
                "snippet": "Groceries list example.",
                "score": 0.21,
                "lang": "en",
            },
        ]

    @property
    def expected_output(self) -> dict[str, str | float]:
        return {
            "query": self.measured_query,
            "selected_id": self.selected_id,
            "selected_url": self.selected_url,
            "selected_score": self.selected_score,
        }

    @property
    def expected_raw_output(self) -> dict[str, str | int]:
        return {
            "query": self.measured_query,
            "total": len(self.measured_results),
            "returned": len(self.measured_results),
        }

    def _write_request_log(self) -> None:
        self.request_log_path.write_text(
            json.dumps(self._request_paths, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _register_hit(self, path: str) -> None:
        with self._lock:
            self._request_paths.append(path)
            self._write_request_log()

    def _payload_for_request(self, path: str, query: str) -> dict[str, Any] | None:
        if path == self.warmup_path:
            expected_query = self.warmup_query
            results = self.warmup_results if query == self.warmup_query else []
        elif path == self.measured_path:
            expected_query = self.measured_query
            results = self.measured_results if query == self.measured_query else []
        else:
            return None
        return {
            "query": query,
            "results": results,
            "total": len(results),
            "returned": len(results),
            "error": "" if query == expected_query else "query_mismatch",
        }

    def start(self) -> None:
        challenge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlsplit(self.path)
                request_query = parse_qs(parsed.query).get("q", [""])[0]
                response = challenge._payload_for_request(parsed.path, request_query)
                if response is None:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"not_found"}')
                    return
                challenge._register_hit(parsed.path)
                payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args):
                return

        def _handler_factory(request: Any, client_address: Any, server: ThreadingHTTPServer) -> BaseHTTPRequestHandler:
            return Handler(request, client_address, server)

        self.case_dir.mkdir(parents=True, exist_ok=True)
        self._write_request_log()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self.warmup_url = f"{self.base_url}{self.warmup_path}"
        self.measured_url = f"{self.base_url}{self.measured_path}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._write_request_log()


def _prepare_web_nonce_workspace(path: Path, challenge_url: str) -> None:
    (path / "challenge-url.txt").write_text(challenge_url + "\n", encoding="utf-8")


def _prepare_web_search_workspace(path: Path, search_url: str, query: str, required_token: str) -> None:
    (path / "search-url.txt").write_text(search_url + "\n", encoding="utf-8")
    (path / "query.txt").write_text(query + "\n", encoding="utf-8")
    (path / "required-token.txt").write_text(required_token + "\n", encoding="utf-8")


def _patch_web_nonce_validators(test_spec: TestSpec, challenge: _WebNonceChallenge) -> TestSpec:
    validators = []
    for validator in test_spec.validators:
        if validator.type != "web_nonce_proof":
            validators.append(validator)
            continue
        validators.append(
            validator.model_copy(
                update={
                    "nonce": challenge.measured_nonce,
                    "payload": challenge.measured_payload,
                    "proof": challenge.measured_proof,
                    "request_log": str(challenge.request_log_path),
                    "request_path": challenge.measured_path,
                }
            )
        )
    return test_spec.model_copy(update={"validators": validators})


def _patch_web_search_validators(test_spec: TestSpec, challenge: _WebSearchChallenge) -> TestSpec:
    if test_spec.id == "web_search_json_ranked":
        expected_payload: dict[str, str | float | int] = challenge.expected_output
    elif test_spec.id == "web_fetch_json_raw":
        expected_payload = challenge.expected_raw_output
    else:
        expected_payload = challenge.expected_output
    expected_json = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True)
    validators = []
    for validator in test_spec.validators:
        if validator.type != "web_search_result":
            validators.append(validator)
            continue
        validators.append(
            validator.model_copy(
                update={
                    "expected": expected_json,
                    "request_log": str(challenge.request_log_path),
                    "request_path": challenge.measured_path,
                }
            )
        )
    return test_spec.model_copy(update={"validators": validators})


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


_PROXY_TOOL_NAME_MAP = {
    "shell": "Bash",
    "read": "Read",
    "save": "Write",
    "write": "Write",
    "patch": "MultiEdit",
    "fetch": "Fetch",
    "list": "List",
}


def _resolve_proxy_allowed_tool_names(
    case: CaseDefinition,
    cli_agent_spec: CliAgentSpec,
    model_spec: ModelSpec | None = None,
) -> list[str]:
    raw_tools = case.allowed_tools or cli_agent_spec.default_tools
    names: list[str] = []
    for tool_name in raw_tools:
        resolved = _PROXY_TOOL_NAME_MAP.get(tool_name, tool_name)
        if resolved not in names:
            names.append(resolved)
    include_exit = True
    extra_tool_names: list[str] = []
    if model_spec is not None:
        overrides = model_spec.policy_overrides or {}
        include_exit = bool(overrides.get("proxy_include_exit_tool", True))
        raw_extra_tool_names = overrides.get("proxy_include_tool_names")
        if isinstance(raw_extra_tool_names, list):
            for tool_name in raw_extra_tool_names:
                if not isinstance(tool_name, str):
                    continue
                resolved = _PROXY_TOOL_NAME_MAP.get(tool_name, tool_name)
                if resolved not in extra_tool_names:
                    extra_tool_names.append(resolved)
    for tool_name in extra_tool_names:
        if tool_name not in names:
            names.append(tool_name)
    if include_exit and "Bash" in names and "Exit" not in names:
        names.append("Exit")
    return names


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


_TelemetryPhase = Literal["warmup", "measured"]
_TELEMETRY_PHASES: tuple[_TelemetryPhase, ...] = ("warmup", "measured")


def _phase_from_command_paths(
    *,
    case: CaseDefinition,
    stdout_path: Path,
    workspace_dir: Path | None,
) -> _TelemetryPhase:
    if stdout_path.name.startswith("warmup.") or workspace_dir == case.warmup_workspace_dir:
        return "warmup"
    return "measured"


def _proxy_relpath_for_phase(phase: _TelemetryPhase) -> str:
    return f"artifacts/proxy.{phase}.http.jsonl"


def _run_case_with_phase_proxy(
    *,
    adapter: Any,
    case: CaseDefinition,
    cli_agent_spec: CliAgentSpec,
    model_spec: ModelSpec,
    test_spec: TestSpec,
    upstream_base_url: str,
) -> tuple[CaseResult, dict[str, str], dict[str, str], str | None]:
    original_run_command = adapter.run_command
    phase_statuses: dict[_TelemetryPhase, str] = {}
    phase_skip_reasons: dict[_TelemetryPhase, str] = {}
    phase_artifacts: dict[_TelemetryPhase, str] = {}
    proxy_runtime_error: str | None = None
    expected_phase_artifacts: dict[_TelemetryPhase, str] = {
        "warmup": _proxy_relpath_for_phase("warmup"),
        "measured": _proxy_relpath_for_phase("measured"),
    }
    proxies: dict[_TelemetryPhase, OllamaTelemetryProxy] = {}
    stopped_phases: set[_TelemetryPhase] = set()
    filter_tools = bool((model_spec.policy_overrides or {}).get("telemetry_proxy_filter_tools"))
    allowed_tool_names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec) if filter_tools else []
    strip_git_context = bool((model_spec.policy_overrides or {}).get("telemetry_proxy_strip_git_context"))
    strip_commit_signature_context = bool(
        (model_spec.policy_overrides or {}).get("telemetry_proxy_strip_commit_signature_context")
    )
    raw_reasoning_effort = (model_spec.policy_overrides or {}).get("telemetry_proxy_reasoning_effort")
    reasoning_effort = str(raw_reasoning_effort).strip() if isinstance(raw_reasoning_effort, str) else None
    raw_temperature_override = (model_spec.policy_overrides or {}).get("telemetry_proxy_temperature_override")
    temperature_override: float | None = None
    if isinstance(raw_temperature_override, (int, float)):
        temperature_override = float(raw_temperature_override)
    capture_ollama_usage = bool((model_spec.policy_overrides or {}).get("telemetry_proxy_capture_ollama_usage"))
    capture_stream_timing = bool((model_spec.policy_overrides or {}).get("telemetry_proxy_capture_stream_timing"))

    for phase in _TELEMETRY_PHASES:
        artifact_relpath = expected_phase_artifacts[phase]
        try:
            proxy_kwargs: dict[str, Any] = {}
            if filter_tools:
                proxy_kwargs = {
                    "filter_tools": True,
                    "allowed_tool_names": allowed_tool_names,
                }
            if strip_git_context:
                proxy_kwargs["strip_git_context"] = True
            if strip_commit_signature_context:
                proxy_kwargs["strip_commit_signature_context"] = True
            if reasoning_effort:
                proxy_kwargs["reasoning_effort"] = reasoning_effort
            if temperature_override is not None:
                proxy_kwargs["temperature_override"] = temperature_override
            if capture_ollama_usage:
                proxy_kwargs["capture_ollama_usage"] = True
            if capture_stream_timing:
                proxy_kwargs["capture_stream_timing"] = True
            proxy_capture = _create_ollama_telemetry_proxy(
                case_dir=case.case_dir,
                upstream_base_url=upstream_base_url,
                artifact_relpath=artifact_relpath,
                **proxy_kwargs,
            )
            proxy_capture.start()
            if not proxy_capture.base_url:
                raise RuntimeError("telemetry proxy failed to publish base URL")
            proxies[phase] = proxy_capture
            phase_statuses[phase] = "collected"
            phase_skip_reasons[phase] = ""
            phase_artifacts[phase] = artifact_relpath
        except Exception as exc:  # noqa: BLE001
            phase_statuses[phase] = "error"
            phase_skip_reasons[phase] = "proxy_start_failed"
            if proxy_runtime_error is None:
                proxy_runtime_error = str(exc)

    phase_proxy_metadata: dict[str, str] = {}
    for phase, proxy_capture in proxies.items():
        if proxy_capture.base_url:
            phase_proxy_metadata[f"telemetry_proxy_{phase}_ollama_host"] = proxy_capture.base_url
            phase_proxy_metadata[f"telemetry_proxy_{phase}_openai_base_url"] = f"{proxy_capture.base_url}/v1"
    if phase_proxy_metadata:
        case.run_metadata = {**case.run_metadata, **phase_proxy_metadata}

    def _run_command_with_proxy(
        command_case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        workspace_dir: Path | None = None,
    ):
        nonlocal proxy_runtime_error
        phase = _phase_from_command_paths(case=command_case, stdout_path=stdout_path, workspace_dir=workspace_dir)
        proxy_capture = proxies.get(phase)
        if proxy_capture is None or not proxy_capture.base_url:
            phase_statuses[phase] = "error"
            phase_skip_reasons[phase] = "proxy_unavailable"
            return original_run_command(
                command_case,
                args,
                env,
                stdout_path,
                stderr_path,
                workspace_dir=workspace_dir,
            )
        try:
            phase_statuses[phase] = "collected"
            phase_skip_reasons[phase] = ""
            phase_artifacts[phase] = proxy_capture.artifact_relpath
            env["OLLAMA_HOST"] = proxy_capture.base_url
            env["OPENAI_BASE_URL"] = f"{proxy_capture.base_url}/v1"
            return original_run_command(
                command_case,
                args,
                env,
                stdout_path,
                stderr_path,
                workspace_dir=workspace_dir,
            )
        finally:
            if phase not in stopped_phases:
                try:
                    proxy_capture.stop()
                    stopped_phases.add(phase)
                except Exception as exc:  # noqa: BLE001
                    phase_statuses[phase] = "error"
                    phase_skip_reasons[phase] = "proxy_stop_failed"
                    if proxy_runtime_error is None:
                        proxy_runtime_error = str(exc)
            artifact_relpath = expected_phase_artifacts.get(phase)
            if (
                artifact_relpath
                and phase_statuses.get(phase) == "collected"
                and not (command_case.case_dir / artifact_relpath).exists()
            ):
                phase_statuses[phase] = "error"
                phase_skip_reasons[phase] = "capture_missing"

    adapter.run_command = _run_command_with_proxy
    result: CaseResult | None = None
    try:
        result = adapter.run_case(case, model_spec, test_spec)
    finally:
        adapter.run_command = original_run_command
        for phase in _TELEMETRY_PHASES:
            proxy_capture = proxies.get(phase)
            if proxy_capture is None:
                continue
            if phase in stopped_phases:
                continue
            try:
                proxy_capture.stop()
                stopped_phases.add(phase)
            except Exception as exc:  # noqa: BLE001
                phase_statuses[phase] = "error"
                phase_skip_reasons[phase] = "proxy_stop_failed"
                if proxy_runtime_error is None:
                    proxy_runtime_error = str(exc)

    if result is None:
        raise RuntimeError("adapter completed without returning a case result")
    proxy_runtime_metadata = {
        "telemetry_proxy_upstream_base_url": upstream_base_url,
        "telemetry_proxy_warmup_artifact_path": _proxy_relpath_for_phase("warmup"),
        "telemetry_proxy_measured_artifact_path": _proxy_relpath_for_phase("measured"),
        **phase_proxy_metadata,
    }
    default_proxy_base_url = (
        proxies.get("measured").base_url
        if proxies.get("measured") is not None
        else (proxies.get("warmup").base_url if proxies.get("warmup") is not None else None)
    )
    if default_proxy_base_url:
        proxy_runtime_metadata.update(
            {
                "telemetry_proxy_ollama_host": default_proxy_base_url,
                "telemetry_proxy_openai_base_url": f"{default_proxy_base_url}/v1",
            }
        )
    return result, proxy_runtime_metadata, phase_artifacts, proxy_runtime_error


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
    run_paths = create_run_paths(root, run_id=run_id)
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
            _prepare_workspace(warmup_workspace_dir, test_spec.id)
            _prepare_workspace(workspace_dir, test_spec.id)
            _write_ollama_modelfile_artifact(case_dir, ollama_modelfile)
            active_test_spec = test_spec
            web_challenge: _WebNonceChallenge | None = None
            web_search_challenge: _WebSearchChallenge | None = None
            if test_spec.id == "web_nonce_proof":
                web_challenge = _WebNonceChallenge(case_dir)
                web_challenge.start()
                _prepare_web_nonce_workspace(warmup_workspace_dir, web_challenge.warmup_url)
                _prepare_web_nonce_workspace(workspace_dir, web_challenge.measured_url)
                assert web_challenge is not None
                active_test_spec = _patch_web_nonce_validators(test_spec, web_challenge)
            if test_spec.id in {"web_search_json_ranked", "web_fetch_json_raw"}:
                search_challenge = _WebSearchChallenge(case_dir)
                web_search_challenge = search_challenge
                search_challenge.start()
                _prepare_web_search_workspace(
                    warmup_workspace_dir,
                    search_challenge.warmup_url,
                    search_challenge.warmup_query,
                    search_challenge.required_token,
                )
                _prepare_web_search_workspace(
                    workspace_dir,
                    search_challenge.measured_url,
                    search_challenge.measured_query,
                    search_challenge.required_token,
                )
                active_test_spec = _patch_web_search_validators(test_spec, search_challenge)
            proxy_capture_status: TelemetryProxyStatus = "skipped"
            proxy_capture_skip_reason: str | None = None
            proxy_capture_artifact_relpaths: dict[str, str] = {}
            proxy_capture_error: str | None = None
            proxy_runtime_metadata: dict[str, str] = {}
            upstream_base_url: str | None = None
            if proxy_mode == "off":
                proxy_capture_skip_reason = "disabled"
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
                    "telemetry_proxy_warmup_artifact_path": _proxy_relpath_for_phase("warmup"),
                    "telemetry_proxy_measured_artifact_path": _proxy_relpath_for_phase("measured"),
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
                if proxy_mode != "off" and backend.id == "ollama" and upstream_base_url is not None:
                    result, phase_proxy_metadata, proxy_capture_artifact_relpaths, proxy_capture_error = _run_case_with_phase_proxy(
                        adapter=adapter,
                        case=case,
                        cli_agent_spec=cli_agent_spec,
                        model_spec=model_spec,
                        test_spec=active_test_spec,
                        upstream_base_url=upstream_base_url,
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
            if proxy_mode != "off" and backend.id == "ollama":
                expected_proxy_artifacts = {
                    "warmup": _proxy_relpath_for_phase("warmup"),
                    "measured": _proxy_relpath_for_phase("measured"),
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
            proxy_required_failed = (
                proxy_mode == "force"
                and str(telemetry_metadata.get("telemetry_proxy_status")) != "collected"
            )
            if proxy_required_failed:
                result.status = "HARNESS_ERROR"
                result.invoked = "no"
                result.match_percent = 0
                result.metadata = {
                    **result.metadata,
                    "failure_reason": "proxy_required_but_not_available",
                    "error": "telemetry proxy mode=force requires active proxy capture",
                }
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
            apply_event_evaluation(result)
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
