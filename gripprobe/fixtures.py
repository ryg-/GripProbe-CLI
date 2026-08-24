from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from gripprobe.models import TestSpec


def prepare_workspace(path: Path, test_id: str) -> None:
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


class WebNonceChallenge:
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


class WebSearchChallenge:
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


def prepare_web_nonce_workspace(path: Path, challenge_url: str) -> None:
    (path / "challenge-url.txt").write_text(challenge_url + "\n", encoding="utf-8")


def prepare_web_search_workspace(path: Path, search_url: str, query: str, required_token: str) -> None:
    (path / "search-url.txt").write_text(search_url + "\n", encoding="utf-8")
    (path / "query.txt").write_text(query + "\n", encoding="utf-8")
    (path / "required-token.txt").write_text(required_token + "\n", encoding="utf-8")


def patch_web_nonce_validators(test_spec: TestSpec, challenge: WebNonceChallenge) -> TestSpec:
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


def patch_web_search_validators(test_spec: TestSpec, challenge: WebSearchChallenge) -> TestSpec:
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



