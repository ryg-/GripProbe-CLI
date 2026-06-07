from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path
from typing import Any, Iterator

import pytest

from gripprobe.telemetry_proxy import OllamaTelemetryProxy


pytestmark = pytest.mark.real_e2e

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:12434"
DEFAULT_MODEL = "granite4:3b"


@pytest.fixture()
def live_ollama_base_url() -> str:
    return os.environ.get("GRIPPROBE_REAL_OLLAMA_HOST", DEFAULT_OLLAMA_HOST).rstrip("/")


@pytest.fixture()
def live_ollama_model() -> str:
    return os.environ.get("GRIPPROBE_REAL_PROXY_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


@pytest.fixture()
def live_proxy(tmp_path: Path, live_ollama_base_url: str) -> Iterator[OllamaTelemetryProxy]:
    _require_live_ollama(live_ollama_base_url)
    proxy = OllamaTelemetryProxy(case_dir=tmp_path, upstream_base_url=live_ollama_base_url)
    proxy.start()
    try:
        yield proxy
    finally:
        proxy.stop()


@pytest.mark.skipif(
    os.environ.get("GRIPPROBE_RUN_REAL_E2E") != "1",
    reason="real e2e is opt-in; set GRIPPROBE_RUN_REAL_E2E=1",
)
def test_live_ollama_proxy_ndjson_session(live_proxy: OllamaTelemetryProxy, live_ollama_model: str) -> None:
    request = urllib.request.Request(
        f"{live_proxy.base_url}/api/generate",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "model": live_ollama_model,
                "prompt": "Reply with exactly two short words.",
                "stream": True,
                "options": {"num_predict": 4},
            }
        ).encode("utf-8"),
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        assert response.headers.get("Content-Type") == "application/x-ndjson"
        first_line = response.readline()
        remaining = response.read()

    assert first_line.startswith(b"{")
    assert b'"done":true' in first_line or b'"done":true' in remaining

    event = _last_proxy_event(live_proxy)
    assert event["x_gripprobe_path"] == "/api/generate"
    assert event["x_gripprobe_response_status"] == 200
    assert event["x_gripprobe_client_disconnected"] is False
    assert event["x_gripprobe_response"]["x_gripprobe_headers"]["Content-Type"] == "application/x-ndjson"


@pytest.mark.skipif(
    os.environ.get("GRIPPROBE_RUN_REAL_E2E") != "1",
    reason="real e2e is opt-in; set GRIPPROBE_RUN_REAL_E2E=1",
)
def test_live_ollama_proxy_sse_session(live_proxy: OllamaTelemetryProxy, live_ollama_model: str) -> None:
    request = urllib.request.Request(
        f"{live_proxy.base_url}/v1/chat/completions",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "model": live_ollama_model,
                "messages": [{"role": "user", "content": "Reply with exactly two short words."}],
                "stream": True,
                "max_tokens": 4,
            }
        ).encode("utf-8"),
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        assert response.headers.get("Content-Type") == "text/event-stream"
        first_line = response.readline()
        remaining = response.read()

    assert first_line.startswith(b"data: ")
    assert b"[DONE]" in remaining

    event = _last_proxy_event(live_proxy)
    assert event["x_gripprobe_path"] == "/v1/chat/completions"
    assert event["x_gripprobe_response_status"] == 200
    assert event["x_gripprobe_client_disconnected"] is False
    assert event["x_gripprobe_response"]["x_gripprobe_headers"]["Content-Type"] == "text/event-stream"


@pytest.mark.skipif(
    os.environ.get("GRIPPROBE_RUN_REAL_E2E") != "1",
    reason="real e2e is opt-in; set GRIPPROBE_RUN_REAL_E2E=1",
)
def test_live_ollama_proxy_records_client_disconnect(live_proxy: OllamaTelemetryProxy, live_ollama_model: str) -> None:
    request = urllib.request.Request(
        f"{live_proxy.base_url}/v1/chat/completions",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "model": live_ollama_model,
                "messages": [
                    {"role": "user", "content": "Count from 1 to 40, one item at a time."},
                ],
                "stream": True,
                "max_tokens": 128,
            }
        ).encode("utf-8"),
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        first_line = response.readline()
        assert first_line.startswith(b"data: ")
        response.close()

    disconnected_event = _wait_for_disconnect_event(live_proxy)
    assert disconnected_event["x_gripprobe_path"] == "/v1/chat/completions"
    assert disconnected_event["x_gripprobe_client_disconnected"] is True


def _require_live_ollama(base_url: str) -> None:
    request = urllib.request.Request(f"{base_url}/api/version", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        pytest.skip(f"live ollama unavailable at {base_url}: {exc}")
    assert isinstance(payload, dict)
    assert "version" in payload


def _last_proxy_event(proxy: OllamaTelemetryProxy) -> dict[str, Any]:
    events = _read_proxy_events(proxy.artifact_path)
    assert events
    return events[-1]


def _read_proxy_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _wait_for_disconnect_event(proxy: OllamaTelemetryProxy, timeout_seconds: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        events = _read_proxy_events(proxy.artifact_path)
        if events:
            last_event = events[-1]
            if last_event.get("x_gripprobe_client_disconnected") is True:
                return last_event
        time.sleep(0.1)
    with suppress(Exception):
        return _last_proxy_event(proxy)
    raise AssertionError("disconnect event was not recorded")
