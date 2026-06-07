from __future__ import annotations

import json
import time
import urllib.request
from contextlib import suppress
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from typing import Any, cast

import gripprobe.telemetry_proxy as telemetry_proxy_module
from gripprobe.telemetry_proxy import OllamaTelemetryProxy


class _StreamingUpstream:
    def __init__(self) -> None:
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                if self.path == "/sse":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self._write_chunk(
                        b'data: {"type":"function_call","name":"apply_patch","call_id":"call_sse"}\n\n'
                    )
                    time.sleep(0.2)
                    self._write_chunk(b"data: [DONE]\n\n")
                    self._write_chunk(b"")
                    return
                if self.path == "/sse-delayed":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self._write_chunk(b'data: {"type":"message","content":"first"}\n\n')
                    time.sleep(1.2)
                    self._write_chunk(b"data: [DONE]\n\n")
                    self._write_chunk(b"")
                    return
                if self.path == "/sse-usage":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self._write_chunk(
                        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"id":"call_u","type":"function","function":{"name":"Bash","arguments":"{}"}}]}}]}\n\n'
                    )
                    time.sleep(0.05)
                    self._write_chunk(
                        b'data: {"id":"x","choices":[],"usage":{"prompt_tokens":321,"completion_tokens":12,"total_tokens":333}}\n\n'
                    )
                    self._write_chunk(b"data: [DONE]\n\n")
                    self._write_chunk(b"")
                    return
                if self.path == "/sse-fragmented-tool":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self._write_chunk(
                        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_frag","type":"function","function":{"name":"Bash","arguments":"{\\"command\\":\\"sed "}}]}}]}\n\n'
                    )
                    time.sleep(0.05)
                    self._write_chunk(
                        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"s/STATUS=old/STATUS=new/ patch-target.txt"}}]}}]}\n\n'
                    )
                    time.sleep(0.05)
                    self._write_chunk(
                        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"}"}}]}}]}\n\n'
                    )
                    self._write_chunk(b"data: [DONE]\n\n")
                    self._write_chunk(b"")
                    return
                if self.path == "/ndjson":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self._write_chunk(b'{"type":"function_call","name":"read","call_id":"call_ndjson"}\n')
                    time.sleep(0.2)
                    self._write_chunk(b'{"type":"tool_result","name":"read","call_id":"call_ndjson"}\n')
                    self._write_chunk(b"")
                    return
                if self.path == "/stall":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    upstream.stall_started.set()
                    upstream.release_stall.wait(timeout=10)
                    return
                if self.path == "/delayed-headers":
                    upstream.delayed_headers_started.set()
                    upstream.release_delayed_headers.wait(timeout=10)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", "2")
                    self.end_headers()
                    self.wfile.write(b"{}")
                    self.wfile.flush()
                    return
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self) -> None:
                if self.path in {"/chat", "/api/chat"}:
                    content_length = int(self.headers.get("Content-Length", "0") or "0")
                    body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    self.wfile.flush()
                    return
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _write_chunk(self, chunk: bytes) -> None:
                self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

            def log_message(self, format: str, *args: object) -> None:
                return

        def handler_factory(
            request: Any,
            client_address: Any,
            server: ThreadingHTTPServer,
        ) -> BaseHTTPRequestHandler:
            return Handler(request, client_address, server)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self.stall_started = Event()
        self.release_stall = Event()
        self.delayed_headers_started = Event()
        self.release_delayed_headers = Event()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.release_stall.set()
        self.release_delayed_headers.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _NoopSocket:
    def settimeout(self, timeout_seconds: float) -> None:
        return


class _NoopRaw:
    def __init__(self) -> None:
        self._sock = _NoopSocket()


class _NoopFp:
    def __init__(self) -> None:
        self.raw = _NoopRaw()


class _DeterministicStreamingResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.fp = _NoopFp()

    def read(self, _: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _IncompleteReadStreamingResponse(_DeterministicStreamingResponse):
    def read(self, _: int) -> bytes:
        if self._chunks:
            chunk = self._chunks.pop(0)
            if chunk == b"__INCOMPLETE_READ__":
                raise IncompleteRead(b"partial")
            return chunk
        return b""


class _RecordingWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, value: bytes) -> int:
        self.buffer.extend(value)
        return len(value)

    def flush(self) -> None:
        return


class _BrokenPipeWriter:
    def __init__(self, fail_after_writes: int = 1) -> None:
        self.fail_after_writes = fail_after_writes
        self.write_calls = 0

    def write(self, _: bytes) -> int:
        self.write_calls += 1
        if self.write_calls > self.fail_after_writes:
            raise BrokenPipeError("simulated broken pipe")
        return 0

    def flush(self) -> None:
        return


class _DeterministicHandler:
    def __init__(self, writer: _BrokenPipeWriter | _RecordingWriter) -> None:
        self.wfile = writer

    def send_response(self, _: int) -> None:
        return

    def send_header(self, _: str, __: str) -> None:
        return

    def end_headers(self) -> None:
        return


def _read_proxy_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _wait_for_proxy_events(path: Path, expected_count: int, timeout_seconds: float = 2.0) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        events = _read_proxy_events(path)
        if len(events) >= expected_count:
            return events
        time.sleep(0.05)
    return _read_proxy_events(path)


def test_proxy_streams_sse_without_buffering(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    try:
        started = time.monotonic()
        with urllib.request.urlopen(f"{proxy.base_url}/sse", timeout=5) as response:
            assert response.headers.get("Content-Type") == "text/event-stream"
            assert response.headers.get("Transfer-Encoding") == "chunked"
            first_line = response.readline()
            first_line_latency = time.monotonic() - started
            remainder = response.read()
        assert first_line.startswith(b"data: ")
        assert first_line_latency < 0.3
        assert b"[DONE]" in remainder

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        assert len(events) == 1
        assert events[0]["x_gripprobe_tool_call_count"] == 1
        assert events[0]["x_gripprobe_tool_names"] == ["apply_patch"]
        assert events[0].get("x_gripprobe_client_disconnect_error_type") is None
        assert events[0].get("x_gripprobe_client_disconnect_error") is None
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_streams_ndjson_and_keeps_tool_evidence(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    try:
        started = time.monotonic()
        with urllib.request.urlopen(f"{proxy.base_url}/ndjson", timeout=5) as response:
            assert response.headers.get("Content-Type") == "application/x-ndjson"
            assert response.headers.get("Transfer-Encoding") == "chunked"
            first_line = response.readline()
            first_line_latency = time.monotonic() - started
            second_line = response.readline()
        assert first_line.startswith(b'{"type":"function_call"')
        assert second_line.startswith(b'{"type":"tool_result"')
        assert first_line_latency < 0.3

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        assert len(events) == 1
        assert events[0]["x_gripprobe_tool_call_count"] == 1
        assert events[0]["x_gripprobe_tool_names"] == ["read"]
        assert events[0]["x_gripprobe_tool_result_count"] == 1
        assert events[0]["x_gripprobe_tool_result_names"] == ["read"]
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_tolerates_long_gap_between_stream_chunks(tmp_path: Path, monkeypatch) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    monkeypatch.setattr(telemetry_proxy_module, "_STREAM_UPSTREAM_TIMEOUT_SECONDS", 2.0)
    try:
        with urllib.request.urlopen(f"{proxy.base_url}/sse-delayed", timeout=5) as response:
            assert response.headers.get("Content-Type") == "text/event-stream"
            first_line = response.readline()
            remainder = response.read()
        assert first_line.startswith(b"data: ")
        assert b"[DONE]" in remainder

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1, timeout_seconds=3.0)
        assert len(events) == 1
        assert events[0]["x_gripprobe_client_disconnected"] is False
        assert events[0].get("x_gripprobe_client_disconnect_error_type") is None
        assert events[0].get("x_gripprobe_client_disconnect_error") is None
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_stop_aborts_active_stream_and_persists_event(tmp_path: Path, monkeypatch) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    monkeypatch.setattr(telemetry_proxy_module, "_STREAM_UPSTREAM_TIMEOUT_SECONDS", 0.1)
    request_done = Event()

    def make_request() -> None:
        with suppress(Exception):
            with urllib.request.urlopen(f"{proxy.base_url}/stall", timeout=5) as response:
                response.read()
        request_done.set()

    request_thread = Thread(target=make_request, daemon=True)
    proxy_stopped = False
    try:
        request_thread.start()
        assert upstream.stall_started.wait(timeout=1)
        proxy.stop()
        proxy_stopped = True
        request_done.wait(timeout=6)
        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1, timeout_seconds=6.0)
        assert len(events) == 1
        assert events[0]["x_gripprobe_path"] == "/stall"
        assert isinstance(events[0]["x_gripprobe_client_disconnected"], bool)
        if events[0]["x_gripprobe_client_disconnected"] is True:
            assert events[0]["x_gripprobe_client_disconnect_error_type"] == "_ProxyStoppedError"
            assert events[0]["x_gripprobe_client_disconnect_error"] == "proxy stopped while relaying upstream stream"
    finally:
        if not proxy_stopped:
            with suppress(Exception):
                proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_stop_aborts_waiting_header_open_and_persists_event(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    request_done = Event()

    def make_request() -> None:
        with suppress(Exception):
            with urllib.request.urlopen(f"{proxy.base_url}/delayed-headers", timeout=5) as response:
                response.read()
        request_done.set()

    request_thread = Thread(target=make_request, daemon=True)
    proxy_stopped = False
    try:
        request_thread.start()
        assert upstream.delayed_headers_started.wait(timeout=1)
        proxy.stop()
        proxy_stopped = True
        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        assert len(events) == 1
        assert events[0]["x_gripprobe_path"] == "/delayed-headers"
        if events[0]["x_gripprobe_client_disconnected"] is True:
            assert events[0]["x_gripprobe_proxy_error"] == "proxy_stopped"
            assert events[0]["x_gripprobe_client_disconnect_error_type"] == "_ProxyStoppedError"
            assert events[0]["x_gripprobe_client_disconnect_error"] == "proxy stopped while opening upstream response"
        else:
            assert events[0]["x_gripprobe_proxy_error"] is not None
        request_done.wait(timeout=6)
    finally:
        if not proxy_stopped:
            with suppress(Exception):
                proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_records_client_disconnect_exception_type(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url="http://example.invalid")
    relay_result = proxy._relay_streaming_response(
        handler=cast(BaseHTTPRequestHandler, cast(object, _DeterministicHandler(_BrokenPipeWriter()))),
        upstream_response=_DeterministicStreamingResponse([b"data: first\n\n", b"data: second\n\n"]),
        response_status=200,
        response_headers={"Content-Type": "text/event-stream"},
        started_monotonic=time.monotonic(),
    )
    assert relay_result.client_disconnected is True
    assert relay_result.disconnect_error_type == "BrokenPipeError"
    assert relay_result.disconnect_error_message == "simulated broken pipe"
    assert relay_result.response_body.startswith(b"data: first")


def test_proxy_records_upstream_incomplete_read_without_client_disconnect(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url="http://example.invalid")
    writer = _RecordingWriter()
    relay_result = proxy._relay_streaming_response(
        handler=cast(BaseHTTPRequestHandler, cast(object, _DeterministicHandler(writer))),
        upstream_response=_IncompleteReadStreamingResponse([b"data: first\n\n", b"__INCOMPLETE_READ__"]),
        response_status=200,
        response_headers={"Content-Type": "text/event-stream"},
        started_monotonic=time.monotonic(),
    )
    assert relay_result.client_disconnected is False
    assert relay_result.disconnect_error_type is None
    assert relay_result.upstream_error_type == "IncompleteRead"
    assert relay_result.upstream_error_message == "IncompleteRead(7 bytes read)"
    assert relay_result.response_body == b"data: first\n\n"
    assert bytes(writer.buffer).endswith(b"0\r\n\r\n")


def test_proxy_records_request_size_metrics_for_tools_schema(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    try:
        payload = {
            "model": "qwen3:1.7b",
            "messages": [
                {"role": "system", "content": "Use tools only."},
                {"role": "user", "content": "Run pwd and return DONE."},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "Bash",
                        "description": "Execute shell command",
                        "parameters": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    },
                }
            ],
        }
        request_data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{proxy.base_url}/chat",
            method="POST",
            data=request_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        assert len(events) == 1
        event = events[0]
        assert event["x_gripprobe_request_body_bytes"] == len(request_data)
        assert event["x_gripprobe_tools_count"] == 1
        assert int(event["x_gripprobe_tools_schema_chars"]) > 0
        assert int(event["x_gripprobe_tools_schema_estimated_tokens"]) > 0
        assert int(event["x_gripprobe_messages_system_chars"]) > 0
        assert int(event["x_gripprobe_messages_user_chars"]) > 0
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_filters_tools_before_upstream_request(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url=upstream.base_url,
        filter_tools=True,
        allowed_tool_names=["Bash"],
    )
    upstream.start()
    proxy.start()
    try:
        payload = {
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": "Run pwd."}],
            "tools": [
                {"type": "function", "function": {"name": "Read", "parameters": {"type": "object"}}},
                {
                    "type": "function",
                    "function": {
                        "name": "Bash",
                        "description": "Execute shell command\nIMPORTANT: To edit files, use Edit/MultiEdit tools instead of bash commands (sed, awk, etc).\n",
                        "parameters": {"type": "object"},
                    },
                },
            ],
        }
        request = urllib.request.Request(
            f"{proxy.base_url}/api/chat",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            echoed = json.loads(response.read().decode("utf-8"))
            assert response.status == 200

        assert [tool["function"]["name"] for tool in echoed["tools"]] == ["Bash"]
        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        event = events[0]
        assert event["x_gripprobe_tools_filter_applied"] is True
        assert event["x_gripprobe_tools_filter_original_count"] == 2
        assert event["x_gripprobe_tools_filter_filtered_count"] == 1
        assert event["x_gripprobe_tools_count"] == 1
        assert "No dedicated file-edit tool is available in this session." in echoed["tools"][0]["function"]["description"]
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_captures_fragmented_tool_arguments_in_event(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=upstream.base_url)
    upstream.start()
    proxy.start()
    try:
        with urllib.request.urlopen(f"{proxy.base_url}/sse-fragmented-tool", timeout=5) as response:
            assert response.status == 200
            _ = response.read()

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        event = events[0]
        assert event["x_gripprobe_tool_call_count"] == 1
        assert event["x_gripprobe_tool_call_details"] == [
            {
                "tool_name": "Bash",
                "tool_call_id": "call_frag",
                "tool_arguments_json": '{"command":"sed s/STATUS=old/STATUS=new/ patch-target.txt"}',
                "bash_command": "sed s/STATUS=old/STATUS=new/ patch-target.txt",
            }
        ]
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_strips_git_context_from_system_message(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url=upstream.base_url,
        strip_git_context=True,
    )
    upstream.start()
    proxy.start()
    try:
        payload = {
            "model": "qwen3:1.7b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Header\n"
                        "Is directory a git repo: true\n"
                        "<context name=\"gitStatus\">status payload</context>\n"
                        "Footer"
                    ),
                },
                {"role": "user", "content": "Run pwd."},
            ],
        }
        request = urllib.request.Request(
            f"{proxy.base_url}/api/chat",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            echoed = json.loads(response.read().decode("utf-8"))
            assert response.status == 200

        system_text = echoed["messages"][0]["content"]
        assert "gitStatus" not in system_text
        assert "Is directory a git repo:" not in system_text
        assert "Header" in system_text
        assert "Footer" in system_text

        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        event = events[0]
        assert event["x_gripprobe_git_context_strip_enabled"] is True
        assert event["x_gripprobe_git_context_strip_applied"] is True
        assert event["x_gripprobe_git_context_strip_message_count"] == 1
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()


def test_proxy_records_usage_and_stream_timing_metrics(tmp_path: Path) -> None:
    upstream = _StreamingUpstream()
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url=upstream.base_url,
        capture_ollama_usage=True,
        capture_stream_timing=True,
    )
    upstream.start()
    proxy.start()
    try:
        with urllib.request.urlopen(f"{proxy.base_url}/sse-usage", timeout=5) as response:
            assert response.status == 200
            _ = response.read()
        events = _wait_for_proxy_events(tmp_path / "artifacts" / "proxy.measured.http.jsonl", 1)
        event = events[0]
        assert event["x_gripprobe_ollama_usage_prompt_tokens"] == 321
        assert event["x_gripprobe_ollama_usage_completion_tokens"] == 12
        assert event["x_gripprobe_ollama_usage_total_tokens"] == 333
        assert int(event["x_gripprobe_stream_first_chunk_ms"]) >= 0
        assert int(event["x_gripprobe_stream_duration_after_first_chunk_ms"]) >= 0
        assert int(event["x_gripprobe_stream_chunks"]) >= 1
        assert int(event["x_gripprobe_stream_bytes"]) >= 1
    finally:
        with suppress(Exception):
            proxy.stop()
        with suppress(Exception):
            upstream.stop()
