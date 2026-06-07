from __future__ import annotations

import contextlib
import http.client
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit

_TOOL_CALL_ID_PATTERN = re.compile(r"@([A-Za-z_][A-Za-z0-9_-]*)\((call_[^) \t]+)\)")
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_STREAMING_CONTENT_TYPES = {
    "application/x-ndjson",
    "application/ndjson",
    "application/jsonl",
    "application/jsonlines",
    "text/event-stream",
}
_STREAM_READ_SIZE = 4096
_STREAM_CAPTURE_LIMIT = 256 * 1024
_DEFAULT_UPSTREAM_TIMEOUT_SECONDS = 180
_STREAM_UPSTREAM_TIMEOUT_SECONDS = 3600
_UPSTREAM_POLL_TIMEOUT_SECONDS = 1.0
_DEFAULT_BODY_EXCERPT_LIMIT = 2 * 1024 * 1024
_GIT_CONTEXT_BLOCK_PATTERN = re.compile(r"<context name=\"gitStatus\">[\s\S]*?</context>\n*", re.IGNORECASE)
_COMMIT_SIGNATURE_BLOCK_PATTERN = re.compile(r"<context name=\"commitSignature\">[\s\S]*?</context>\n*", re.IGNORECASE)
_OPENAI_MUTATION_PATHS = {"/v1/chat/completions", "/v1/responses"}
_OLLAMA_CHAT_MUTATION_PATHS = {"/api/chat"}
_OLLAMA_GENERATE_MUTATION_PATHS = {"/api/generate"}
_MUTATION_PATHS = _OPENAI_MUTATION_PATHS | _OLLAMA_CHAT_MUTATION_PATHS | _OLLAMA_GENERATE_MUTATION_PATHS


@dataclass(frozen=True)
class ProxyCaptureSummary:
    status: str
    skip_reason: str | None
    artifact_relpath: str | None
    ollama_host: str | None
    openai_base_url: str | None


@dataclass(frozen=True)
class _SseEvent:
    event: str | None
    data: str


@dataclass(frozen=True)
class _ToolEvidence:
    tool_calls: list[tuple[str, str | None]]
    tool_results: list[tuple[str, str | None]]
    nonstructured_tool_names: list[str]
    nonstructured_tool_call_ids: list[str]
    tool_call_details: list[dict[str, str | None]]


@dataclass
class _PartialToolCall:
    order: int
    index: int | None = None
    call_id: str | None = None
    name: str | None = None
    arguments_parts: list[str] | None = None

    def append_arguments(self, value: str) -> None:
        if self.arguments_parts is None:
            self.arguments_parts = []
        self.arguments_parts.append(value)


class _ProxyStoppedError(RuntimeError):
    pass


@dataclass(frozen=True)
class _StreamRelayResult:
    response_body: bytes
    client_disconnected: bool
    stream_metrics: dict[str, Any]
    disconnect_error_type: str | None = None
    disconnect_error_message: str | None = None
    upstream_error_type: str | None = None
    upstream_error_message: str | None = None


class OllamaTelemetryProxy:
    def __init__(
        self,
        *,
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
    ) -> None:
        self.case_dir = case_dir
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self.artifact_relpath = artifact_relpath
        self.artifact_path = case_dir / artifact_relpath
        self.filter_tools = filter_tools
        self.allowed_tool_names = list(dict.fromkeys(allowed_tool_names or []))
        self.strip_git_context = strip_git_context
        self.strip_commit_signature_context = strip_commit_signature_context
        self.reasoning_effort = reasoning_effort.strip() if isinstance(reasoning_effort, str) and reasoning_effort.strip() else None
        self.temperature_override = temperature_override
        self.capture_ollama_usage = capture_ollama_usage
        self.capture_stream_timing = capture_stream_timing
        self._lock = threading.Lock()
        self._active_connections: set[http.client.HTTPConnection] = set()
        self._active_upstreams: set[Any] = set()
        self._stopping = threading.Event()
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
    def _body_excerpt_limit() -> int:
        raw = os.environ.get("GRIPPROBE_PROXY_BODY_EXCERPT_LIMIT", "").strip()
        if raw:
            try:
                parsed = int(raw)
            except ValueError:
                parsed = _DEFAULT_BODY_EXCERPT_LIMIT
            if parsed > 0:
                return parsed
        return _DEFAULT_BODY_EXCERPT_LIMIT

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

    @staticmethod
    def _estimate_token_count(text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    @staticmethod
    def _estimate_token_count_for_chars(char_count: int) -> int:
        if char_count <= 0:
            return 0
        return max(1, (char_count + 3) // 4)

    def _build_request_size_metrics(
        self,
        *,
        request_body: bytes,
        request_text: str,
        request_payload: dict[str, Any] | list[Any] | None,
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "x_gripprobe_request_body_bytes": len(request_body),
            "x_gripprobe_request_body_chars": len(request_text),
            "x_gripprobe_request_body_estimated_tokens": self._estimate_token_count(request_text),
        }
        if not isinstance(request_payload, dict):
            return metrics
        messages = request_payload.get("messages")
        if isinstance(messages, list):
            system_chars = 0
            user_chars = 0
            assistant_chars = 0
            other_chars = 0
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "")
                content = message.get("content")
                if isinstance(content, str):
                    content_text = content
                else:
                    content_text = json.dumps(content, ensure_ascii=False) if content is not None else ""
                length = len(content_text)
                if role == "system":
                    system_chars += length
                elif role == "user":
                    user_chars += length
                elif role == "assistant":
                    assistant_chars += length
                else:
                    other_chars += length
            metrics["x_gripprobe_messages_system_chars"] = system_chars
            metrics["x_gripprobe_messages_user_chars"] = user_chars
            metrics["x_gripprobe_messages_assistant_chars"] = assistant_chars
            metrics["x_gripprobe_messages_other_chars"] = other_chars
            total_message_chars = system_chars + user_chars + assistant_chars + other_chars
            metrics["x_gripprobe_messages_estimated_tokens"] = self._estimate_token_count_for_chars(total_message_chars)
            metrics["x_gripprobe_messages_system_estimated_tokens"] = self._estimate_token_count_for_chars(system_chars)
            metrics["x_gripprobe_messages_user_estimated_tokens"] = self._estimate_token_count_for_chars(user_chars)

        tools = request_payload.get("tools")
        if isinstance(tools, list):
            tools_json = json.dumps(tools, ensure_ascii=False)
            metrics["x_gripprobe_tools_count"] = len(tools)
            metrics["x_gripprobe_tools_schema_chars"] = len(tools_json)
            metrics["x_gripprobe_tools_schema_estimated_tokens"] = self._estimate_token_count(tools_json)
        return metrics

    @staticmethod
    def _strip_git_context_from_text(content: str) -> str:
        stripped = _GIT_CONTEXT_BLOCK_PATTERN.sub("", content)
        stripped = re.sub(r"^Is directory a git repo:.*\n?", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"\n{3,}", "\n\n", stripped)
        return stripped

    @staticmethod
    def _strip_commit_signature_context_from_text(content: str) -> str:
        stripped = _COMMIT_SIGNATURE_BLOCK_PATTERN.sub("", content)
        stripped = re.sub(r"\n{3,}", "\n\n", stripped)
        return stripped

    def _mutate_request_body(self, request_path: str, request_body: bytes) -> tuple[bytes, dict[str, Any]]:
        metadata: dict[str, Any] = {
            "x_gripprobe_mutation_endpoint_supported": request_path in _MUTATION_PATHS,
            "x_gripprobe_tools_filter_enabled": self.filter_tools,
            "x_gripprobe_tools_filter_allowed_names": self.allowed_tool_names,
            "x_gripprobe_git_context_strip_enabled": self.strip_git_context,
            "x_gripprobe_commit_signature_context_strip_enabled": self.strip_commit_signature_context,
            "x_gripprobe_reasoning_effort_override": self.reasoning_effort,
            "x_gripprobe_temperature_override": self.temperature_override,
        }
        if request_path not in _MUTATION_PATHS:
            metadata.update(
                {
                    "x_gripprobe_tools_filter_applied": False,
                    "x_gripprobe_tools_filter_reason": "unsupported_endpoint",
                    "x_gripprobe_git_context_strip_applied": False,
                    "x_gripprobe_git_context_strip_reason": "unsupported_endpoint",
                    "x_gripprobe_commit_signature_context_strip_applied": False,
                    "x_gripprobe_commit_signature_context_strip_reason": "unsupported_endpoint",
                    "x_gripprobe_reasoning_effort_applied": False,
                    "x_gripprobe_temperature_applied": False,
                }
            )
            return request_body, metadata
        payload = self._safe_json_loads(request_body)
        if not isinstance(payload, dict):
            metadata["x_gripprobe_tools_filter_applied"] = False
            metadata["x_gripprobe_git_context_strip_applied"] = False
            metadata["x_gripprobe_commit_signature_context_strip_applied"] = False
            metadata["x_gripprobe_tools_filter_reason"] = "non_json_object"
            metadata["x_gripprobe_git_context_strip_reason"] = "non_json_object"
            metadata["x_gripprobe_commit_signature_context_strip_reason"] = "non_json_object"
            return request_body, metadata
        changed = False

        supports_tools = request_path in (_OPENAI_MUTATION_PATHS | _OLLAMA_CHAT_MUTATION_PATHS)
        supports_messages = request_path in ({"/v1/chat/completions"} | _OLLAMA_CHAT_MUTATION_PATHS)

        tools = payload.get("tools")
        if self.filter_tools and supports_tools and isinstance(tools, list):
            allowed = set(self.allowed_tool_names)
            filtered_tools = [
                tool
                for tool in tools
                if not isinstance(tool, dict)
                or str((tool.get("function") or {}).get("name") if isinstance(tool.get("function"), dict) else tool.get("name"))
                in allowed
            ]
            metadata["x_gripprobe_tools_filter_original_count"] = len(tools)
            metadata["x_gripprobe_tools_filter_filtered_count"] = len(filtered_tools)
            metadata["x_gripprobe_tools_filter_applied"] = True
            filtered_tools = self._rewrite_bash_tool_descriptions(filtered_tools)
            if len(filtered_tools) != len(tools):
                payload["tools"] = filtered_tools
                changed = True
            elif filtered_tools != tools:
                payload["tools"] = filtered_tools
                changed = True
        elif self.filter_tools:
            metadata["x_gripprobe_tools_filter_applied"] = False
            metadata["x_gripprobe_tools_filter_reason"] = (
                "missing_tools" if supports_tools else "unsupported_endpoint_schema"
            )
        else:
            metadata["x_gripprobe_tools_filter_applied"] = False

        if self.strip_git_context and supports_messages:
            messages = payload.get("messages")
            removed_count = 0
            if isinstance(messages, list):
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    if str(message.get("role") or "") != "system":
                        continue
                    content = message.get("content")
                    if not isinstance(content, str):
                        continue
                    updated = self._strip_git_context_from_text(content)
                    if updated != content:
                        message["content"] = updated
                        removed_count += 1
                        changed = True
            metadata["x_gripprobe_git_context_strip_applied"] = removed_count > 0
            metadata["x_gripprobe_git_context_strip_message_count"] = removed_count
            if removed_count == 0:
                metadata["x_gripprobe_git_context_strip_reason"] = "no_git_context_found"
        else:
            metadata["x_gripprobe_git_context_strip_applied"] = False

        if self.strip_commit_signature_context and supports_messages:
            messages = payload.get("messages")
            removed_count = 0
            if isinstance(messages, list):
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    if str(message.get("role") or "") != "system":
                        continue
                    content = message.get("content")
                    if not isinstance(content, str):
                        continue
                    updated = self._strip_commit_signature_context_from_text(content)
                    if updated != content:
                        message["content"] = updated
                        removed_count += 1
                        changed = True
            metadata["x_gripprobe_commit_signature_context_strip_applied"] = removed_count > 0
            metadata["x_gripprobe_commit_signature_context_strip_message_count"] = removed_count
            if removed_count == 0:
                metadata["x_gripprobe_commit_signature_context_strip_reason"] = "no_commit_signature_context_found"
        else:
            metadata["x_gripprobe_commit_signature_context_strip_applied"] = False

        if self.reasoning_effort and request_path in _OPENAI_MUTATION_PATHS:
            if payload.get("reasoning_effort") != self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
                changed = True
            metadata["x_gripprobe_reasoning_effort_applied"] = True
        else:
            metadata["x_gripprobe_reasoning_effort_applied"] = False

        if self.temperature_override is not None and request_path in _OPENAI_MUTATION_PATHS:
            if payload.get("temperature") != self.temperature_override:
                payload["temperature"] = self.temperature_override
                changed = True
            metadata["x_gripprobe_temperature_applied"] = True
        elif self.temperature_override is not None and request_path in (
            _OLLAMA_CHAT_MUTATION_PATHS | _OLLAMA_GENERATE_MUTATION_PATHS
        ):
            options = payload.get("options")
            if not isinstance(options, dict):
                options = {}
            if options.get("temperature") != self.temperature_override:
                payload["options"] = {**options, "temperature": self.temperature_override}
                changed = True
            metadata["x_gripprobe_temperature_applied"] = True
        else:
            metadata["x_gripprobe_temperature_applied"] = False

        if not changed:
            return request_body, metadata
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), metadata

    def _rewrite_bash_tool_descriptions(self, tools: list[Any]) -> list[Any]:
        has_dedicated_editor = False
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function_payload = tool.get("function")
            if not isinstance(function_payload, dict):
                continue
            tool_name = str(function_payload.get("name") or "").strip()
            if tool_name in {"Edit", "MultiEdit", "Write"}:
                has_dedicated_editor = True
                break
        if has_dedicated_editor:
            return tools
        rewritten: list[Any] = []
        for tool in tools:
            if not isinstance(tool, dict):
                rewritten.append(tool)
                continue
            function_payload = tool.get("function")
            if not isinstance(function_payload, dict):
                rewritten.append(tool)
                continue
            tool_name = str(function_payload.get("name") or "").strip()
            if tool_name != "Bash":
                rewritten.append(tool)
                continue
            description = function_payload.get("description")
            if not isinstance(description, str):
                rewritten.append(tool)
                continue
            updated_description = description.replace(
                "IMPORTANT: To edit files, use Edit/MultiEdit tools instead of bash commands (sed, awk, etc).\n",
                "IMPORTANT: No dedicated file-edit tool is available in this session. Use Bash when you need to modify files.\n",
            )
            if updated_description == description:
                rewritten.append(tool)
                continue
            rewritten.append({**tool, "function": {**function_payload, "description": updated_description}})
        return rewritten

    def start(self) -> None:
        self._stopping.clear()
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

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
        self._stopping.set()
        with self._lock:
            active_connections = list(self._active_connections)
            active_upstreams = list(self._active_upstreams)
        for connection in active_connections:
            with contextlib.suppress(Exception):
                connection.close()
        for upstream in active_upstreams:
            with contextlib.suppress(Exception):
                upstream.close()
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
        original_request_body = handler.rfile.read(content_length) if content_length > 0 else b""
        request_body, request_mutation_metrics = self._mutate_request_body(parsed.path, original_request_body)
        request_payload = self._safe_json_loads(request_body)
        upstream_timeout = _STREAM_UPSTREAM_TIMEOUT_SECONDS if _request_prefers_streaming(request_headers, request_payload) else _DEFAULT_UPSTREAM_TIMEOUT_SECONDS

        response_status = 502
        response_headers: dict[str, str] = {"content-type": "application/json"}
        response_body = b'{"error":"proxy_error"}'
        proxy_error: str | None = None
        client_disconnected = False
        client_disconnect_error_type: str | None = None
        client_disconnect_error_message: str | None = None
        upstream_stream_error_type: str | None = None
        upstream_stream_error_message: str | None = None

        upstream_request = urllib.request.Request(
            upstream_url,
            data=(request_body if request_body else None),
            method=handler.command,
            headers=_filter_request_headers({**request_headers, "Content-Length": str(len(request_body))}),
        )
        try:
            upstream_connection, upstream_response = self._open_upstream_response(
                upstream_url=upstream_url,
                upstream_request=upstream_request,
                timeout_seconds=upstream_timeout,
            )
            with contextlib.closing(upstream_connection), contextlib.closing(upstream_response):
                self._register_active_upstream(upstream_response)
                try:
                    response_status = int(getattr(upstream_response, "status", 200))
                    response_headers = {key: value for key, value in upstream_response.headers.items()}
                    stream_metrics: dict[str, Any] = {}
                    if _is_streaming_response(response_headers):
                        relay_result = self._relay_streaming_response(
                            handler=handler,
                            upstream_response=upstream_response,
                            response_status=response_status,
                            response_headers=response_headers,
                            started_monotonic=started,
                        )
                        response_body = relay_result.response_body
                        client_disconnected = relay_result.client_disconnected
                        stream_metrics = relay_result.stream_metrics
                        client_disconnect_error_type = relay_result.disconnect_error_type
                        client_disconnect_error_message = relay_result.disconnect_error_message
                        upstream_stream_error_type = relay_result.upstream_error_type
                        upstream_stream_error_message = relay_result.upstream_error_message
                    else:
                        response_body = upstream_response.read()
                        self._send_buffered_response(
                            handler=handler,
                            response_status=response_status,
                            response_headers=response_headers,
                            response_body=response_body,
                        )
                finally:
                    self._unregister_active_upstream(upstream_response)
        except _ProxyStoppedError:
            proxy_error = "proxy_stopped"
            client_disconnected = True
            client_disconnect_error_type = _ProxyStoppedError.__name__
            client_disconnect_error_message = "proxy stopped while opening upstream response"
        except Exception as exc:  # noqa: BLE001
            proxy_error = str(exc)
            response_status = 502
            response_headers = {"content-type": "application/json"}
            response_body = json.dumps({"error": "proxy_upstream_error", "detail": str(exc)}).encode("utf-8")
            self._send_buffered_response(
                handler=handler,
                response_status=response_status,
                response_headers=response_headers,
                response_body=response_body,
            )

        response_payload = self._safe_json_loads(response_body)
        tool_evidence = _extract_tool_evidence_details(
            request_payload=request_payload,
            response_payload=response_payload,
            response_body=response_body,
            response_headers=response_headers,
        )
        request_text = request_body.decode("utf-8", errors="replace")
        response_text = response_body.decode("utf-8", errors="replace")
        request_size_metrics = self._build_request_size_metrics(
            request_body=request_body,
            request_text=request_text,
            request_payload=request_payload,
        )
        event = {
            "x_gripprobe_schema_version": 1,
            "x_gripprobe_timestamp": self._utc_now_iso(),
            "x_gripprobe_method": handler.command,
            "x_gripprobe_path": parsed.path,
            "x_gripprobe_query": parsed.query or None,
            "x_gripprobe_upstream_url": upstream_url,
            "x_gripprobe_duration_ms": round((time.monotonic() - started) * 1000),
            "x_gripprobe_request": {
                "x_gripprobe_headers": self._sanitize_headers(request_headers),
                "x_gripprobe_body_excerpt": self._sanitize_text(request_text[: self._body_excerpt_limit()]),
            },
            "x_gripprobe_response": {
                "x_gripprobe_status": response_status,
                "x_gripprobe_headers": self._sanitize_headers(response_headers),
                "x_gripprobe_body_excerpt": self._sanitize_text(response_text[: self._body_excerpt_limit()]),
            },
            "x_gripprobe_response_status": response_status,
            "x_gripprobe_tool_call_count": len(tool_evidence.tool_calls),
            "x_gripprobe_tool_names": [name for name, _ in tool_evidence.tool_calls],
            "x_gripprobe_tool_call_ids": [call_id or "unknown" for _, call_id in tool_evidence.tool_calls],
            "x_gripprobe_tool_call_nonstructured_count": len(tool_evidence.nonstructured_tool_names),
            "x_gripprobe_tool_names_nonstructured": tool_evidence.nonstructured_tool_names,
            "x_gripprobe_tool_call_ids_nonstructured": tool_evidence.nonstructured_tool_call_ids,
            "x_gripprobe_tool_call_details": [
                {
                    "tool_name": self._sanitize_text(detail.get("tool_name") or "unknown"),
                    "tool_call_id": self._sanitize_text(detail.get("tool_call_id") or "unknown"),
                    "tool_arguments_json": self._sanitize_text(detail.get("tool_arguments_json") or "")
                    if detail.get("tool_arguments_json")
                    else None,
                    "bash_command": self._sanitize_text(detail.get("bash_command") or "")
                    if detail.get("bash_command")
                    else None,
                }
                for detail in tool_evidence.tool_call_details
            ],
            "x_gripprobe_tool_result_count": len(tool_evidence.tool_results),
            "x_gripprobe_tool_result_names": [name for name, _ in tool_evidence.tool_results],
            "x_gripprobe_tool_result_ids": [call_id or "unknown" for _, call_id in tool_evidence.tool_results],
            "x_gripprobe_proxy_error": self._sanitize_text(proxy_error) if proxy_error else None,
            "x_gripprobe_client_disconnected": client_disconnected,
            "x_gripprobe_client_disconnect_error_type": client_disconnect_error_type,
            "x_gripprobe_client_disconnect_error": self._sanitize_text(client_disconnect_error_message)
            if client_disconnect_error_message
            else None,
            "x_gripprobe_upstream_stream_error_type": upstream_stream_error_type,
            "x_gripprobe_upstream_stream_error": self._sanitize_text(upstream_stream_error_message)
            if upstream_stream_error_message
            else None,
            **request_mutation_metrics,
            **request_size_metrics,
            **(stream_metrics if self.capture_stream_timing else {}),
        }
        if self.capture_ollama_usage:
            event.update(_extract_ollama_usage_metrics(response_payload, response_body, response_headers))
        self._append_event({k: v for k, v in event.items() if v is not None})

    def _send_buffered_response(
        self,
        *,
        handler: BaseHTTPRequestHandler,
        response_status: int,
        response_headers: dict[str, str],
        response_body: bytes,
    ) -> None:
        try:
            handler.send_response(response_status)
            for key, value in _filter_response_headers(response_headers, streaming=False).items():
                handler.send_header(key, value)
            handler.send_header("Content-Length", str(len(response_body)))
            handler.end_headers()
            handler.wfile.write(response_body)
            handler.wfile.flush()
        except Exception:  # noqa: BLE001
            pass

    def _register_active_upstream(self, upstream_response: Any) -> None:
        with self._lock:
            self._active_upstreams.add(upstream_response)

    def _unregister_active_upstream(self, upstream_response: Any) -> None:
        with self._lock:
            self._active_upstreams.discard(upstream_response)

    def _register_active_connection(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            self._active_connections.add(connection)

    def _unregister_active_connection(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            self._active_connections.discard(connection)

    def _open_upstream_response(
        self,
        *,
        upstream_url: str,
        upstream_request: urllib.request.Request,
        timeout_seconds: float,
    ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        parsed = urlsplit(upstream_url)
        connection = _build_http_connection(parsed)
        connection.timeout = _UPSTREAM_POLL_TIMEOUT_SECONDS
        self._register_active_connection(connection)
        try:
            connection.request(
                upstream_request.get_method(),
                _request_target_from_split(parsed),
                body=upstream_request.data,
                headers=dict(upstream_request.header_items()),
            )
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    response = connection.getresponse()
                    return connection, response
                except (socket.timeout, TimeoutError):
                    if self._stopping.is_set():
                        raise _ProxyStoppedError("proxy stopped while opening upstream response")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out waiting for upstream response headers")
        except Exception:
            connection.close()
            raise
        finally:
            self._unregister_active_connection(connection)

    def _relay_streaming_response(
        self,
        *,
        handler: BaseHTTPRequestHandler,
        upstream_response: Any,
        response_status: int,
        response_headers: dict[str, str],
        started_monotonic: float,
    ) -> _StreamRelayResult:
        captured_chunks: list[bytes] = []
        captured_bytes = 0
        client_disconnected = False
        chunked_response_started = False
        stream_metrics: dict[str, Any] = {}
        disconnect_error_type: str | None = None
        disconnect_error_message: str | None = None
        upstream_error_type: str | None = None
        upstream_error_message: str | None = None
        first_chunk_at: float | None = None
        first_tool_call_chunk_at: float | None = None
        streamed_bytes = 0
        streamed_chunks = 0
        _set_upstream_socket_timeout(upstream_response, timeout_seconds=_STREAM_UPSTREAM_TIMEOUT_SECONDS)
        try:
            handler.send_response(response_status)
            for key, value in _filter_response_headers(response_headers, streaming=True).items():
                handler.send_header(key, value)
            handler.send_header("Transfer-Encoding", "chunked")
            handler.end_headers()
            chunked_response_started = True
            while True:
                try:
                    chunk = upstream_response.read(_STREAM_READ_SIZE)
                except (socket.timeout, TimeoutError):
                    if self._stopping.is_set():
                        disconnect_error_type = _ProxyStoppedError.__name__
                        disconnect_error_message = "proxy stopped while relaying upstream stream"
                        break
                    continue
                except Exception as exc:  # noqa: BLE001
                    upstream_error_type = type(exc).__name__
                    upstream_error_message = str(exc)
                    break
                if not chunk:
                    break
                now = time.monotonic()
                if first_chunk_at is None:
                    first_chunk_at = now
                streamed_chunks += 1
                streamed_bytes += len(chunk)
                if captured_bytes < _STREAM_CAPTURE_LIMIT:
                    capture_slice = chunk[: _STREAM_CAPTURE_LIMIT - captured_bytes]
                    if capture_slice:
                        captured_chunks.append(capture_slice)
                        captured_bytes += len(capture_slice)
                        if first_tool_call_chunk_at is None and b'"tool_calls"' in capture_slice:
                            first_tool_call_chunk_at = now
                chunk_prefix = f"{len(chunk):X}\r\n".encode("ascii")
                try:
                    handler.wfile.write(chunk_prefix)
                    handler.wfile.write(chunk)
                    handler.wfile.write(b"\r\n")
                    handler.wfile.flush()
                except Exception as exc:  # noqa: BLE001
                    client_disconnected = True
                    disconnect_error_type = type(exc).__name__
                    disconnect_error_message = str(exc)
                    break
        except Exception as exc:  # noqa: BLE001
            client_disconnected = True
            disconnect_error_type = type(exc).__name__
            disconnect_error_message = str(exc)
        finally:
            if chunked_response_started and not client_disconnected:
                with contextlib.suppress(Exception):
                    handler.wfile.write(b"0\r\n\r\n")
                    handler.wfile.flush()
        completed_at = time.monotonic()
        if first_chunk_at is not None:
            stream_metrics["x_gripprobe_stream_first_chunk_ms"] = round((first_chunk_at - started_monotonic) * 1000)
            active_seconds = max(1e-6, completed_at - first_chunk_at)
            stream_metrics["x_gripprobe_stream_duration_after_first_chunk_ms"] = round(active_seconds * 1000)
            stream_metrics["x_gripprobe_stream_bytes"] = streamed_bytes
            stream_metrics["x_gripprobe_stream_chunks"] = streamed_chunks
            stream_metrics["x_gripprobe_stream_bytes_per_second"] = round(streamed_bytes / active_seconds, 3)
        if first_tool_call_chunk_at is not None:
            stream_metrics["x_gripprobe_stream_first_tool_call_chunk_ms"] = round(
                (first_tool_call_chunk_at - started_monotonic) * 1000
            )
        return _StreamRelayResult(
            response_body=b"".join(captured_chunks),
            client_disconnected=client_disconnected,
            stream_metrics=stream_metrics,
            disconnect_error_type=disconnect_error_type,
            disconnect_error_message=disconnect_error_message,
            upstream_error_type=upstream_error_type,
            upstream_error_message=upstream_error_message,
        )


def _extract_tool_evidence(
    *,
    request_payload: dict[str, Any] | list[Any] | None,
    response_payload: dict[str, Any] | list[Any] | None,
    response_body: bytes,
    response_headers: dict[str, str],
) -> tuple[list[str], int, list[str], list[str]]:
    evidence = _extract_tool_evidence_details(
        request_payload=request_payload,
        response_payload=response_payload,
        response_body=response_body,
        response_headers=response_headers,
    )
    return (
        [name for name, _ in evidence.tool_calls],
        len(evidence.tool_results),
        evidence.nonstructured_tool_names,
        evidence.nonstructured_tool_call_ids,
    )


def _extract_tool_evidence_details(
    *,
    request_payload: dict[str, Any] | list[Any] | None,
    response_payload: dict[str, Any] | list[Any] | None,
    response_body: bytes,
    response_headers: dict[str, str],
) -> _ToolEvidence:
    structured_calls: list[tuple[str, str | None]] = []
    structured_results: list[tuple[str, str | None]] = []
    structured_payloads: list[dict[str, Any] | list[Any]] = []

    structured_results.extend(_extract_tool_results_from_obj(request_payload))
    structured_results.extend(_extract_tool_results_from_obj(response_payload))
    structured_calls.extend(_extract_structured_tool_calls_from_obj(response_payload))
    if response_payload is not None:
        structured_payloads.append(response_payload)

    content_type = (response_headers.get("Content-Type") or response_headers.get("content-type") or "").lower()
    if "text/event-stream" in content_type or _looks_like_sse(response_body):
        for payload in _extract_payloads_from_sse(response_body):
            structured_calls.extend(_extract_structured_tool_calls_from_obj(payload))
            structured_results.extend(_extract_tool_results_from_obj(payload))
            structured_payloads.append(payload)
    if _is_ndjson_content_type(content_type) or _looks_like_ndjson(response_body):
        for payload in _extract_payloads_from_ndjson(response_body):
            structured_calls.extend(_extract_structured_tool_calls_from_obj(payload))
            structured_results.extend(_extract_tool_results_from_obj(payload))
            structured_payloads.append(payload)
    nonstructured_tool_names, nonstructured_tool_call_ids = _extract_nonstructured_tool_markers(response_body)
    return _ToolEvidence(
        tool_calls=_dedup_pairs(structured_calls),
        tool_results=_dedup_pairs(structured_results),
        nonstructured_tool_names=nonstructured_tool_names,
        nonstructured_tool_call_ids=nonstructured_tool_call_ids,
        tool_call_details=_extract_structured_tool_call_details(structured_payloads),
    )


def _extract_structured_tool_call_details(payloads: list[dict[str, Any] | list[Any]]) -> list[dict[str, str | None]]:
    partials: dict[str, _PartialToolCall] = {}
    sequence = 0
    for payload in payloads:
        sequence = _collect_tool_call_details_from_payload(payload, partials, sequence)
    details: list[dict[str, str | None]] = []
    for partial in sorted(partials.values(), key=lambda item: item.order):
        tool_name = (partial.name or "unknown").strip() or "unknown"
        tool_call_id = partial.call_id.strip() if isinstance(partial.call_id, str) and partial.call_id.strip() else None
        arguments_json = None
        if partial.arguments_parts:
            arguments_json = "".join(partial.arguments_parts).strip() or None
        bash_command = _extract_bash_command_from_arguments(arguments_json) if tool_name == "Bash" else None
        details.append(
            {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "tool_arguments_json": arguments_json,
                "bash_command": bash_command,
            }
        )
    deduped: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for detail in details:
        normalized = (
            detail["tool_name"] or "unknown",
            detail["tool_call_id"],
            detail["tool_arguments_json"],
            detail["bash_command"],
        )
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(detail)
    return deduped


def _collect_tool_call_details_from_payload(
    payload: object,
    partials: dict[str, _PartialToolCall],
    sequence: int,
) -> int:
    if isinstance(payload, dict):
        if _looks_like_tool_call_item(payload):
            sequence += 1
            _merge_tool_call_item(partials, payload, sequence)
        for value in payload.values():
            sequence = _collect_tool_call_details_from_payload(value, partials, sequence)
        return sequence
    if isinstance(payload, list):
        for item in payload:
            sequence = _collect_tool_call_details_from_payload(item, partials, sequence)
    return sequence


def _looks_like_tool_call_item(payload: dict[str, Any]) -> bool:
    payload_type = str(payload.get("type", "")).lower()
    function_payload = payload.get("function")
    if payload_type in {"function_call", "tool_call"}:
        return True
    if isinstance(function_payload, dict) and any(key in payload for key in ("id", "call_id", "index")):
        return True
    return False


def _merge_tool_call_item(
    partials: dict[str, _PartialToolCall],
    payload: dict[str, Any],
    sequence: int,
) -> None:
    function_payload = payload.get("function") if isinstance(payload.get("function"), dict) else {}
    call_id = _tool_call_id_from_obj(payload)
    index = payload.get("index") if isinstance(payload.get("index"), int) else None
    key = _tool_call_partial_key(call_id=call_id, index=index, sequence=sequence)
    if call_id and index is not None:
        index_key = _tool_call_partial_key(call_id=None, index=index, sequence=None)
        if key not in partials and index_key in partials:
            partials[key] = partials.pop(index_key)
    partial = partials.get(key)
    if partial is None and index is not None:
        partial = next((item for item in partials.values() if item.index == index), None)
    if partial is None:
        partial = _PartialToolCall(order=sequence, index=index)
        partials[key] = partial
    if call_id:
        partial.call_id = call_id
    if index is not None:
        partial.index = index
    name = _tool_name_from_obj(payload)
    if name != "unknown":
        partial.name = name
    arguments_value = None
    if isinstance(function_payload, dict) and "arguments" in function_payload:
        arguments_value = function_payload.get("arguments")
    elif "arguments" in payload:
        arguments_value = payload.get("arguments")
    serialized_arguments = _serialize_tool_arguments(arguments_value)
    if serialized_arguments is not None:
        partial.append_arguments(serialized_arguments)


def _tool_call_partial_key(*, call_id: str | None, index: int | None, sequence: int | None) -> str:
    if isinstance(call_id, str) and call_id.strip():
        return f"call_id:{call_id.strip()}"
    if isinstance(index, int):
        return f"index:{index}"
    return f"anonymous:{sequence or 0}"


def _serialize_tool_arguments(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return None


def _extract_bash_command_from_arguments(arguments_json: str | None) -> str | None:
    if not arguments_json:
        return None
    try:
        payload = json.loads(arguments_json)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        command = payload.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
    return None


def _extract_nonstructured_tool_markers(raw: bytes) -> tuple[list[str], list[str]]:
    text = raw.decode("utf-8", errors="replace")
    names: list[str] = []
    call_ids: list[str] = []
    for match in _iter_nonstructured_tool_marker_matches(text):
        tool_name = match[0].strip()
        tool_call_id = match[1].strip() if len(match) > 1 else ""
        names.append(tool_name.lower() or "unknown")
        call_ids.append(tool_call_id or "unknown")
    return names, call_ids


def _iter_nonstructured_tool_marker_matches(text: str) -> list[tuple[str, str]]:
    markers: list[tuple[str, str]] = []
    for line in text.splitlines():
        if _is_known_echo_noise(line):
            continue
        for match in re.finditer(r"@([A-Za-z_][A-Za-z0-9_-]*)\((call_[^) \t]+)\)", line):
            markers.append((match.group(1), match.group(2)))
    return markers


def _count_tool_results_in_obj(payload: object) -> int:
    if isinstance(payload, dict):
        current = 1 if str(payload.get("type", "")).lower() in {"function_call_output", "tool_result"} else 0
        return current + sum(_count_tool_results_in_obj(value) for value in payload.values())
    if isinstance(payload, list):
        return sum(_count_tool_results_in_obj(item) for item in payload)
    return 0


def _extract_tool_calls_from_obj(payload: object) -> list[str]:
    return [name for name, _ in _extract_structured_tool_calls_from_obj(payload)]


def _extract_structured_tool_calls_from_obj(payload: object) -> list[tuple[str, str | None]]:
    calls: list[tuple[str, str | None]] = []
    if isinstance(payload, dict):
        payload_type = str(payload.get("type", "")).lower()
        if payload_type in {"function_call", "tool_call"}:
            calls.append((_tool_name_from_obj(payload), _tool_call_id_from_obj(payload)))
        function_payload = payload.get("function")
        if isinstance(function_payload, dict) and ("name" in function_payload or payload.get("id")):
            calls.append((_tool_name_from_obj(payload), _tool_call_id_from_obj(payload)))
        tool_calls = payload.get("tool_calls")
        if isinstance(tool_calls, list):
            for item in tool_calls:
                calls.extend(_extract_structured_tool_calls_from_obj(item))
        elif isinstance(tool_calls, dict):
            calls.extend(_extract_structured_tool_calls_from_obj(tool_calls))
        for value in payload.values():
            if value is tool_calls:
                continue
            calls.extend(_extract_structured_tool_calls_from_obj(value))
    elif isinstance(payload, list):
        for item in payload:
            calls.extend(_extract_structured_tool_calls_from_obj(item))
    return _dedup_pairs(calls)


def _extract_tool_results_from_obj(payload: object) -> list[tuple[str, str | None]]:
    results: list[tuple[str, str | None]] = []
    if isinstance(payload, dict):
        payload_type = str(payload.get("type", "")).lower()
        role = str(payload.get("role", "")).lower()
        if payload_type in {"function_call_output", "tool_result", "function_result", "tool_output"} or role == "tool":
            results.append((_tool_name_from_obj(payload), _tool_call_id_from_obj(payload)))
        for value in payload.values():
            results.extend(_extract_tool_results_from_obj(value))
    elif isinstance(payload, list):
        for item in payload:
            results.extend(_extract_tool_results_from_obj(item))
    return _dedup_pairs(results)


def _extract_tool_calls_from_sse(raw: bytes) -> list[str]:
    names: list[str] = []
    for payload in _extract_payloads_from_sse(raw):
        names.extend(_extract_tool_calls_from_obj(payload))
    return names


def _looks_like_sse(raw: bytes) -> bool:
    stripped = raw.lstrip()
    return stripped.startswith((b"event:", b"data:", b":"))


def _looks_like_ndjson(raw: bytes) -> bool:
    stripped = raw.lstrip()
    return stripped.startswith((b"{", b"["))


def _extract_payloads_from_ndjson(raw: bytes) -> list[dict[str, Any] | list[Any]]:
    payloads: list[dict[str, Any] | list[Any]] = []
    text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, (dict, list)):
            payloads.append(payload)
    return payloads


def _extract_payloads_from_sse(raw: bytes) -> list[dict[str, Any] | list[Any]]:
    payloads: list[dict[str, Any] | list[Any]] = []
    for event in _parse_sse_events(raw):
        data = event.data.strip()
        if not data or data == "[DONE]":
            continue
        parsed = _parse_sse_json_payload(data)
        if parsed is not None:
            payloads.append(parsed)
    return payloads


def _parse_sse_events(raw: bytes) -> list[_SseEvent]:
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    events: list[_SseEvent] = []
    event_name: str | None = None
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if event_name is not None or data_lines:
            events.append(_SseEvent(event=event_name, data="\n".join(data_lines)))
        event_name = None
        data_lines = []

    for raw_line in text.split("\n"):
        if raw_line == "":
            flush()
            continue
        if raw_line.startswith(":"):
            continue
        field, separator, value = raw_line.partition(":")
        if not separator:
            continue
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
    flush()
    return events


def _parse_sse_json_payload(data: str) -> dict[str, Any] | list[Any] | None:
    for candidate in (data, data.replace("\n", "")):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, (dict, list)):
            return payload
    return None


def _extract_ollama_usage_metrics(
    response_payload: dict[str, Any] | list[Any] | None,
    response_body: bytes,
    response_headers: dict[str, str],
) -> dict[str, int]:
    usage = _extract_usage_from_obj(response_payload)
    if usage is None:
        content_type = (response_headers.get("Content-Type") or response_headers.get("content-type") or "").lower()
        if "text/event-stream" in content_type or _looks_like_sse(response_body):
            for payload in _extract_payloads_from_sse(response_body):
                usage = _extract_usage_from_obj(payload)
                if usage is not None:
                    break
        if usage is None and (_is_ndjson_content_type(content_type) or _looks_like_ndjson(response_body)):
            for payload in _extract_payloads_from_ndjson(response_body):
                usage = _extract_usage_from_obj(payload)
                if usage is not None:
                    break
    if usage is None:
        return {}
    metrics: dict[str, int] = {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if isinstance(prompt_tokens, int):
        metrics["x_gripprobe_ollama_usage_prompt_tokens"] = prompt_tokens
    if isinstance(completion_tokens, int):
        metrics["x_gripprobe_ollama_usage_completion_tokens"] = completion_tokens
    if isinstance(total_tokens, int):
        metrics["x_gripprobe_ollama_usage_total_tokens"] = total_tokens
    return metrics


def _extract_usage_from_obj(payload: object) -> dict[str, int] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if isinstance(usage, dict):
        has_any_token = any(isinstance(usage.get(k), int) for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
        if has_any_token:
            return usage
    for value in payload.values():
        extracted = _extract_usage_from_obj(value)
        if extracted is not None:
            return extracted
    return None


def _tool_name_from_obj(payload: dict[str, Any]) -> str:
    for key in ("name", "tool_name", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    function_payload = payload.get("function")
    if isinstance(function_payload, dict):
        value = function_payload.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _tool_call_id_from_obj(payload: dict[str, Any]) -> str | None:
    for key in ("call_id", "tool_call_id", "id", "item_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _dedup_pairs(pairs: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[tuple[str, str | None]] = []
    for name, call_id in pairs:
        normalized = (name.strip() or "unknown", call_id.strip() if isinstance(call_id, str) and call_id.strip() else None)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _is_known_echo_noise(line: str) -> bool:
    lowered = line.lower()
    if "auto-title" in lowered or "auto_title" in lowered:
        return True
    return ("\"title\"" in lowered or "'title'" in lowered) and _TOOL_CALL_ID_PATTERN.search(line) is not None


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


def _filter_request_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _HOP_BY_HOP_HEADERS | {"host"}}


def _filter_response_headers(headers: dict[str, str], *, streaming: bool) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in _HOP_BY_HOP_HEADERS:
            continue
        if lowered == "content-length":
            continue
        filtered[key] = value
    if streaming and "Cache-Control" not in filtered and "cache-control" not in filtered:
        filtered["Cache-Control"] = "no-cache"
    return filtered


def _is_streaming_response(headers: dict[str, str]) -> bool:
    content_type = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    return "text/event-stream" in content_type or _is_ndjson_content_type(content_type)


def _is_ndjson_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _STREAMING_CONTENT_TYPES - {"text/event-stream"}


def _request_prefers_streaming(
    request_headers: dict[str, str],
    request_payload: dict[str, Any] | list[Any] | None,
) -> bool:
    accept = request_headers.get("Accept", request_headers.get("accept", ""))
    if "text/event-stream" in accept.lower():
        return True
    if isinstance(request_payload, dict):
        stream_flag = request_payload.get("stream")
        if isinstance(stream_flag, bool):
            return stream_flag
    return False


def _set_upstream_socket_timeout(upstream_response: Any, *, timeout_seconds: float) -> None:
    with contextlib.suppress(Exception):
        upstream_response.fp.raw._sock.settimeout(timeout_seconds)


def _build_http_connection(parsed: SplitResult) -> http.client.HTTPConnection:
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(host, port=port, timeout=_UPSTREAM_POLL_TIMEOUT_SECONDS)
    return http.client.HTTPConnection(host, port=port, timeout=_UPSTREAM_POLL_TIMEOUT_SECONDS)


def _request_target_from_split(parsed: SplitResult) -> str:
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path
