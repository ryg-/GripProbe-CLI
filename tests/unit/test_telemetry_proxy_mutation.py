from __future__ import annotations

import json
from pathlib import Path

import pytest

from gripprobe.telemetry_proxy import OllamaTelemetryProxy


def test_mutate_request_body_strips_git_context_and_applies_overrides(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url="http://127.0.0.1:11434",
        strip_git_context=True,
        strip_commit_signature_context=True,
        reasoning_effort="none",
        temperature_override=0.0,
    )
    payload = {
        "model": "qwen3:1.7b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Header\n"
                    "Is directory a git repo: true\n"
                    "<context name=\"gitStatus\">M file.txt</context>\n"
                    "<context name=\"commitSignature\">Generated with Continue</context>\n"
                    "Footer\n"
                ),
            },
            {"role": "user", "content": "Run pwd."},
        ],
    }
    raw = json.dumps(payload).encode("utf-8")

    mutated, metrics = proxy._mutate_request_body("/v1/chat/completions", raw)  # noqa: SLF001
    decoded = json.loads(mutated.decode("utf-8"))
    system_text = decoded["messages"][0]["content"]

    assert "gitStatus" not in system_text
    assert "Is directory a git repo:" not in system_text
    assert "commitSignature" not in system_text
    assert "Header" in system_text
    assert "Footer" in system_text
    assert decoded["reasoning_effort"] == "none"
    assert decoded["temperature"] == 0.0
    assert metrics["x_gripprobe_git_context_strip_applied"] is True
    assert metrics["x_gripprobe_commit_signature_context_strip_applied"] is True
    assert metrics["x_gripprobe_reasoning_effort_applied"] is True
    assert metrics["x_gripprobe_temperature_applied"] is True


@pytest.mark.parametrize(
    "request_path",
    ["/api/version", "/api/tags", "/api/show", "/unknown"],
)
def test_mutation_leaves_non_inference_endpoints_unchanged(tmp_path: Path, request_path: str) -> None:
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url="http://127.0.0.1:11434",
        filter_tools=True,
        allowed_tool_names=["Bash"],
        reasoning_effort="none",
        temperature_override=0.0,
    )
    raw = json.dumps(
        {
            "name": "qwen3:1.7b",
            "tools": [{"type": "function", "function": {"name": "Read"}}],
        }
    ).encode("utf-8")

    mutated, metrics = proxy._mutate_request_body(request_path, raw)  # noqa: SLF001

    assert mutated == raw
    assert metrics["x_gripprobe_mutation_endpoint_supported"] is False
    assert metrics["x_gripprobe_tools_filter_applied"] is False
    assert metrics["x_gripprobe_tools_filter_reason"] == "unsupported_endpoint"


def test_ollama_temperature_override_uses_options(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url="http://127.0.0.1:11434",
        reasoning_effort="none",
        temperature_override=0.0,
    )
    raw = json.dumps({"model": "qwen3:1.7b", "messages": []}).encode("utf-8")

    mutated, metrics = proxy._mutate_request_body("/api/chat", raw)  # noqa: SLF001
    payload = json.loads(mutated)

    assert payload["options"]["temperature"] == 0.0
    assert "temperature" not in payload
    assert "reasoning_effort" not in payload
    assert metrics["x_gripprobe_temperature_applied"] is True
    assert metrics["x_gripprobe_reasoning_effort_applied"] is False


def test_mutate_request_body_strips_skills_instructions_from_responses_input(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url="http://127.0.0.1:11434",
        strip_skills_instructions=True,
    )
    payload = {
        "model": "llama3.2:latest",
        "input": [
            {
                "type": "message",
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "<permissions instructions>\nKeep this.\n</permissions instructions>\n\n"
                            "<skills_instructions>\nRemove this whole block.\n</skills_instructions>\n\n"
                            "Tail"
                        ),
                    }
                ],
            }
        ],
        "tools": [],
    }
    raw = json.dumps(payload).encode("utf-8")

    mutated, metrics = proxy._mutate_request_body("/v1/responses", raw)  # noqa: SLF001
    decoded = json.loads(mutated.decode("utf-8"))
    text = decoded["input"][0]["content"][0]["text"]

    assert "<skills_instructions>" not in text
    assert "Remove this whole block." not in text
    assert "<permissions instructions>" in text
    assert "Tail" in text
    assert metrics["x_gripprobe_skills_instructions_strip_enabled"] is True
    assert metrics["x_gripprobe_skills_instructions_strip_applied"] is True


def test_mutate_request_body_strips_permissions_instructions_from_responses_input(tmp_path: Path) -> None:
    proxy = OllamaTelemetryProxy(
        case_dir=tmp_path,
        upstream_base_url="http://127.0.0.1:11434",
        strip_permissions_instructions=True,
    )
    payload = {
        "model": "llama3.2:latest",
        "input": [
            {
                "type": "message",
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "<permissions instructions>\nRemove this whole block.\n</permissions instructions>\n\n"
                            "<skills_instructions>\nKeep this.\n</skills_instructions>\n\n"
                            "Tail"
                        ),
                    }
                ],
            }
        ],
        "tools": [],
    }
    raw = json.dumps(payload).encode("utf-8")

    mutated, metrics = proxy._mutate_request_body("/v1/responses", raw)  # noqa: SLF001
    decoded = json.loads(mutated.decode("utf-8"))
    text = decoded["input"][0]["content"][0]["text"]

    assert "<permissions instructions>" not in text
    assert "Remove this whole block." not in text
    assert "<skills_instructions>" in text
    assert "Keep this." in text
    assert "Tail" in text
    assert metrics["x_gripprobe_permissions_instructions_strip_enabled"] is True
    assert metrics["x_gripprobe_permissions_instructions_strip_applied"] is True
