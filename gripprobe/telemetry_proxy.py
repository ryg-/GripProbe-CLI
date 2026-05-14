from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProxyCaptureSummary:
    status: str
    skip_reason: str | None
    artifact_relpath: str | None
    ollama_host: str | None
    openai_base_url: str | None


class OllamaTelemetryProxy:
    def __init__(
        self,
        *,
        case_dir: Path,
        upstream_base_url: str,
        artifact_relpath: str = "artifacts/proxy.http.jsonl",
    ) -> None:
        self.case_dir = case_dir
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self.artifact_relpath = artifact_relpath
        self.artifact_path = case_dir / artifact_relpath
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str | None = None

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _sanitize_text(value: str) -> str:
        text = value.replace("\r\n", "\n")
        for token in ("authorization", "api_key", "apikey", "token", "secret", "password", "nonce"):
            text = _redact_assignments(text, token)
        return text

    @staticmethod
    def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
        sanitized: dict[str, str] = {}
        for key, value in headers.items():
            lowered = key.lower()
            if lowered in {"authorization", "proxy-authorization"}:
                sanitized[key] = "[redacted]"
            elif lowered in {"set-cookie", "cookie", "x-api-key"}:
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = OllamaTelemetryProxy._sanitize_text(value)
        return sanitized

    @staticmethod
    def _safe_json_loads(raw: bytes) -> dict[str, Any] | list[Any] | None:
        try:
            decoded = raw.decode("utf-8", errors="replace")
        except Exception:
            return None
        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, (dict, list)):
            return payload
        return None

    def start(self) -> None:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                proxy._handle(self)

            def do_POST(self) -> None:
                proxy._handle(self)

            def do_PUT(self) -> None:
                proxy._handle(self)

            def do_PATCH(self) -> None:
                proxy._handle(self)

            def do_DELETE(self) -> None:
                proxy._handle(self)

            def log_message(self, format: str, *args: Any) -> None:
                return

        def _handler_factory(request: Any, client_address: Any, server: ThreadingHTTPServer) -> BaseHTTPRequestHandler:
            return Handler(request, client_address, server)

        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_path.write_text("", encoding="utf-8")
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
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

    def _append_event(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            with self.artifact_path.open("a", encoding="utf-8") as stream:
                stream.write(line)

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        started = time.monotonic()
        parsed = urlsplit(handler.path)
        upstream_url = f"{self.upstream_base_url}{parsed.path}"
        if parsed.query:
            upstream_url = f"{upstream_url}?{parsed.query}"

        request_headers = {key: value for key, value in handler.headers.items()}
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        request_body = handler.rfile.read(content_length) if content_length > 0 else b""
        request_payload = self._safe_json_loads(request_body)

        response_status = 502
        response_headers: dict[str, str] = {"content-type": "application/json"}
        response_body = b'{"error":"proxy_error"}'
        proxy_error: str | None = None

        upstream_request = urllib.request.Request(
            upstream_url,
            data=(request_body if request_body else None),
            method=handler.command,
            headers={k: v for k, v in request_headers.items() if k.lower() != "host"},
        )
        try:
            with urllib.request.urlopen(upstream_request, timeout=180) as upstream_response:
                response_status = int(getattr(upstream_response, "status", 200))
                response_headers = {key: value for key, value in upstream_response.headers.items()}
                response_body = upstream_response.read()
        except urllib.error.HTTPError as exc:
            response_status = int(exc.code)
            response_headers = {key: value for key, value in (exc.headers.items() if exc.headers else [])}
            response_body = exc.read()
        except Exception as exc:  # noqa: BLE001
            proxy_error = str(exc)
            response_status = 502
            response_headers = {"content-type": "application/json"}
            response_body = json.dumps({"error": "proxy_upstream_error", "detail": str(exc)}).encode("utf-8")

        try:
            handler.send_response(response_status)
            content_type = response_headers.get("Content-Type") or response_headers.get("content-type")
            if content_type:
                handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(response_body)))
            handler.end_headers()
            handler.wfile.write(response_body)
        except Exception:  # noqa: BLE001
            # Connection may already be closed; keep telemetry entry and move on.
            pass

        response_payload = self._safe_json_loads(response_body)
        tool_calls, tool_results = _extract_tool_evidence(
            request_payload=request_payload,
            response_payload=response_payload,
            response_body=response_body,
            response_headers=response_headers,
        )
        request_text = request_body.decode("utf-8", errors="replace")
        response_text = response_body.decode("utf-8", errors="replace")
        event = {
            "timestamp": self._utc_now_iso(),
            "method": handler.command,
            "path": parsed.path,
            "query": parsed.query or None,
            "upstream_url": upstream_url,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "request": {
                "headers": self._sanitize_headers(request_headers),
                "body_excerpt": self._sanitize_text(request_text[:2000]),
            },
            "response": {
                "status": response_status,
                "headers": self._sanitize_headers(response_headers),
                "body_excerpt": self._sanitize_text(response_text[:2000]),
            },
            "tool_call_count": len(tool_calls),
            "tool_names": tool_calls,
            "tool_result_count": tool_results,
            "proxy_error": self._sanitize_text(proxy_error) if proxy_error else None,
        }
        self._append_event({k: v for k, v in event.items() if v is not None})


def _extract_tool_evidence(
    *,
    request_payload: dict[str, Any] | list[Any] | None,
    response_payload: dict[str, Any] | list[Any] | None,
    response_body: bytes,
    response_headers: dict[str, str],
) -> tuple[list[str], int]:
    tool_calls: list[str] = []
    tool_results = 0

    tool_results += _count_tool_results_in_obj(request_payload)
    tool_calls.extend(_extract_tool_calls_from_obj(response_payload))

    content_type = (response_headers.get("Content-Type") or response_headers.get("content-type") or "").lower()
    if "text/event-stream" in content_type or response_body.startswith(b"event: "):
        tool_calls.extend(_extract_tool_calls_from_sse(response_body))
    return tool_calls, tool_results


def _count_tool_results_in_obj(payload: object) -> int:
    if isinstance(payload, dict):
        current = 1 if str(payload.get("type", "")).lower() in {"function_call_output", "tool_result"} else 0
        return current + sum(_count_tool_results_in_obj(value) for value in payload.values())
    if isinstance(payload, list):
        return sum(_count_tool_results_in_obj(item) for item in payload)
    return 0


def _extract_tool_calls_from_obj(payload: object) -> list[str]:
    names: list[str] = []
    if isinstance(payload, dict):
        payload_type = str(payload.get("type", "")).lower()
        if payload_type in {"function_call", "tool_call"}:
            name = str(payload.get("name", "")).strip()
            names.append(name or "unknown")
        for value in payload.values():
            names.extend(_extract_tool_calls_from_obj(value))
    elif isinstance(payload, list):
        for item in payload:
            names.extend(_extract_tool_calls_from_obj(item))
    return names


def _extract_tool_calls_from_sse(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload_text = line[5:].strip()
        if not payload_text or payload_text == "[DONE]":
            continue
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event_type = str(payload.get("type", "")).lower()
        if event_type in {"response.output_item.added", "response.output_item.done"}:
            item = payload.get("item")
            if isinstance(item, dict):
                item_type = str(item.get("type", "")).lower()
                if item_type in {"function_call", "tool_call"}:
                    name = str(item.get("name", "")).strip()
                    names.append(name or "unknown")
        elif event_type in {"response.function_call_arguments.done"}:
            # Arguments event implies function_call event already happened, keep for resilience.
            item_id = str(payload.get("item_id", "")).strip()
            if item_id:
                names.append("unknown")
    return names


def _redact_assignments(text: str, key: str) -> str:
    lowered = key.lower()
    pieces = []
    start = 0
    while True:
        idx = text.lower().find(lowered, start)
        if idx < 0:
            pieces.append(text[start:])
            break
        pieces.append(text[start:idx + len(key)])
        cursor = idx + len(key)
        while cursor < len(text) and text[cursor] in (" ", "\t"):
            pieces.append(text[cursor])
            cursor += 1
        if cursor < len(text) and text[cursor] in (":", "="):
            pieces.append(text[cursor])
            cursor += 1
            while cursor < len(text) and text[cursor] in (" ", "\t"):
                pieces.append(text[cursor])
                cursor += 1
            while cursor < len(text) and text[cursor] not in ("\n", "\r", " ", "\t", ",", ";", '"', "'"):
                cursor += 1
            pieces.append("[redacted]")
            start = cursor
        else:
            start = idx + len(key)
    return "".join(pieces)

