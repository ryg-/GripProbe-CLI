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
from typing import Any, Callable, Iterable, cast

from gripprobe.adapters.base import AdapterError
from gripprobe.adapters.aider import AiderAdapter
from gripprobe.adapters.continue_cli import ContinueCliAdapter
from gripprobe.adapters.gptme import GptmeAdapter
from gripprobe.adapters.opencode import OpencodeAdapter
from gripprobe.case_result import build_case_result
from gripprobe.models import BackendSpec, CaseDefinition, CaseResult, ModelSpec, ShellSpec, TestSpec
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import create_run_paths, write_json
from gripprobe.spec_loader import load_model_specs, load_shell_specs, load_test_specs


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


def _collect_shell_runtime_metadata(executable: str) -> dict[str, str]:
    executable_name = str(executable)
    metadata: dict[str, str] = {"shell_executable": executable_name}
    resolved = shutil.which(cast(str, executable_name))
    if resolved:
        home = str(Path.home())
        metadata["shell_executable_path"] = resolved.replace(home, "$HOME", 1) if resolved.startswith(home) else resolved
    try:
        probe = subprocess.run(
            [executable_name, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return metadata
    version_output = (probe.stdout or probe.stderr or "").strip()
    if version_output:
        metadata["shell_version"] = version_output.splitlines()[0]
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
    return metadata


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
    if test_id == "patch_file":
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


def _adapter_for(shell_spec: ShellSpec):
    if shell_spec.id == "aider":
        return AiderAdapter(shell_spec)
    if shell_spec.id == "gptme":
        return GptmeAdapter(shell_spec)
    if shell_spec.id == "continue-cli":
        return ContinueCliAdapter(shell_spec)
    if shell_spec.id == "opencode":
        return OpencodeAdapter(shell_spec)
    raise ValueError(f"Unsupported shell adapter: {shell_spec.id}")


def _apply_model_policy_overrides(shell_spec: ShellSpec, model_spec: ModelSpec) -> ShellSpec:
    overrides = model_spec.policy_overrides or {}
    shell_timeouts = overrides.get("shell_timeout_seconds")
    if isinstance(shell_timeouts, dict):
        timeout_override = shell_timeouts.get(shell_spec.id)
        if isinstance(timeout_override, int) and timeout_override > 0:
            return shell_spec.model_copy(update={"timeout_seconds": timeout_override})
    return shell_spec


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
    shell_name: str,
    model_name: str,
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
) -> tuple[Path, list[CaseResult]]:
    tests = load_test_specs(root)
    models = load_model_specs(root)
    shells = load_shell_specs(root)

    model_spec: ModelSpec = _find_one(models, "label", model_name)
    shell_spec: ShellSpec = _apply_model_policy_overrides(_find_one(shells, "id", shell_name), model_spec)
    backend = _select_backend(model_spec, backend_name)
    resolved_model_hash = _resolve_model_hash(backend, model_hash)
    ollama_modelfile = _fetch_ollama_model_modelfile(backend.model_id) if backend.id == "ollama" else None
    adapter = _adapter_for(shell_spec)
    run_paths = create_run_paths(root, run_id=run_id)
    runtime_metadata = _collect_shell_runtime_metadata(shell_spec.executable)
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
        f"shell={shell_spec.id} "
        f"model={model_spec.label} "
        f"backend={backend.id} "
        f"report={run_paths.reports_dir / 'summary.html'}",
    )

    results: list[CaseResult] = []
    tests = _filter_tests(tests, tests_filter)
    tests = _filter_tests_by_tags(tests, test_tags_filter)
    formats = [fmt for fmt in model_spec.supported_formats if fmt in shell_spec.supported_formats] or shell_spec.supported_formats
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
            if test_spec.supported_shells and shell_spec.id not in test_spec.supported_shells:
                continue
            if test_spec.supported_formats and tool_format not in test_spec.supported_formats:
                continue
            format_cases += 1
            case_id = f"{shell_spec.id}__{model_spec.id}__{backend.id}__{tool_format}__{test_spec.id}"
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
            case = CaseDefinition(
                case_id=case_id,
                run_id=run_paths.run_id,
                shell_id=shell_spec.id,
                shell_label=shell_spec.label,
                model_id=model_spec.id,
                model_label=model_spec.label,
                backend_id=backend.id,
                backend_model_id=backend.model_id,
                shell_model_id=backend.shell_model_id,
                model_hash=resolved_model_hash,
                quantization=model_spec.quantization,
                tool_format=tool_format,
                test_id=active_test_spec.id,
                test_title=active_test_spec.title,
                prompt=active_test_spec.prompt,
                warmup_workspace_dir=warmup_workspace_dir,
                workspace_dir=workspace_dir,
                case_dir=case_dir,
                allowed_tools=active_test_spec.allowed_tools,
                container_image=container_image or shell_spec.container_image,
                keep_system_messages=keep_system_messages,
                run_metadata=merged_run_metadata,
            )
            case_runtime_before = _collect_runtime_snapshot(include_ollama=backend.id == "ollama")
            try:
                result = adapter.run_case(case, model_spec, active_test_spec)
            except AdapterError as exc:
                result = _harness_error_result(case, model_spec, active_test_spec, str(exc))
            finally:
                if web_challenge is not None:
                    web_challenge.stop()
                if web_search_challenge is not None:
                    web_search_challenge.stop()
            case_runtime_after = _collect_runtime_snapshot(include_ollama=backend.id == "ollama")
            result.metadata = {
                **merged_run_metadata,
                **result.metadata,
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
            }
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
            "shell": shell_spec.id,
            "model": model_spec.id,
            "backend": backend.id,
            "model_hash": resolved_model_hash,
            "cases": len(results),
            "formats": formats,
            "tests": [test.id for test in tests],
            "container_image": container_image or shell_spec.container_image,
            "keep_system_messages": keep_system_messages,
            "run_metadata": merged_run_metadata,
        },
    )
    _emit(
        progress,
        "DONE "
        f"shell={shell_spec.id} "
        f"model={model_spec.label} "
        f"backend={backend.id} "
        f"cases={len(results)} "
        f"report={run_paths.reports_dir / 'summary.html'}",
    )
    return run_paths.run_dir, results
