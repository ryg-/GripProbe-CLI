from __future__ import annotations

import json
from pathlib import Path

from gripprobe.telemetry import extract_and_persist_case_telemetry


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_extract_and_persist_case_telemetry_parses_events_and_sanitizes_payload(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text(
        '@patch(call_1): {"path":"/home/source-user/work/private/file.txt","token":"abc123"}\n',
        encoding="utf-8",
    )
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "recipient_name": "functions.exec_command",
                        "type": "tool_use",
                        "content": "cat /home/source-user/work/private/file.txt token=abc123",
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_result",
                        "tool_name": "exec_command",
                        "exit_code": 0,
                        "status": "success",
                    }
                ),
                json.dumps(
                    {
                        "role": "assistant",
                        "content": "DONE Authorization=Bearer sk-secret-value",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")

    transcript_path = case_dir / "runtime" / "gptme" / "measured" / "session" / "conversation.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        json.dumps({"role": "assistant", "content": "DONE token=super-secret"}) + "\n",
        encoding="utf-8",
    )

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-1",
        case_id="case-1",
        cli_agent_id="codex",
        telemetry_proxy_mode="auto",
    )

    warmup_events_path = case_dir / "artifacts" / "events.warmup.jsonl"
    measured_events_path = case_dir / "artifacts" / "events.measured.jsonl"
    summary_path = case_dir / "artifacts" / "events.summary.json"
    assert warmup_events_path.exists()
    assert measured_events_path.exists()
    assert summary_path.exists()

    measured_events = _read_jsonl(measured_events_path)
    assert any(event["event_type"] == "tool_call_start" for event in measured_events)
    assert any(event["event_type"] == "tool_call_result" for event in measured_events)

    serialized_events = json.dumps(measured_events, ensure_ascii=False)
    assert "/home/source-user" not in serialized_events
    assert "abc123" not in serialized_events
    assert "sk-secret-value" not in serialized_events
    assert "$HOME/work/private/file.txt" in serialized_events
    assert "[redacted]" in serialized_events

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["event_capture_status"] == "collected"
    assert summary["telemetry_proxy_status"] == "skipped"
    assert summary["telemetry_proxy_skip_reason"] == "unsupported_backend"
    assert summary["tool_event_verdict"] == "confirmed_tool_use"
    assert summary["telemetry_tool_call_count"] >= 1
    assert summary["telemetry_tool_result_count"] >= 1
    assert metadata["telemetry_source_tier"] == "B"


def test_extract_and_persist_case_telemetry_handles_missing_capture_deterministically(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-2",
        case_id="case-2",
        cli_agent_id="aider",
        telemetry_proxy_mode="off",
    )

    summary_path = case_dir / "artifacts" / "events.summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert metadata["event_capture_status"] == "missing"
    assert metadata["tool_event_verdict"] == "tool_event_inconclusive"
    assert metadata["tool_event_verdict_reason"] == "capture_missing"
    assert metadata["telemetry_proxy_status"] == "skipped"
    assert metadata["telemetry_proxy_skip_reason"] == "disabled"

    assert summary["telemetry_event_count"] == 0
    assert summary["telemetry_tool_call_count"] == 0
    assert summary["telemetry_tool_result_count"] == 0
    assert summary["tool_event_verdict"] == "tool_event_inconclusive"
    assert summary["tool_event_verdict_reason"] == "capture_missing"

    assert (case_dir / "artifacts" / "events.warmup.jsonl").exists()
    assert (case_dir / "artifacts" / "events.measured.jsonl").exists()


def test_extract_and_persist_case_telemetry_marks_force_mode_proxy_error(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-3",
        case_id="case-3",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
    )

    assert metadata["telemetry_proxy_status"] == "error"
    assert metadata["telemetry_proxy_skip_reason"] == "unsupported_backend"
    assert metadata["tool_event_verdict"] == "tool_event_inconclusive"
    assert metadata["tool_event_verdict_reason"] == "proxy_error"


def test_extract_and_persist_case_telemetry_ingests_proxy_artifact_when_collected(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "proxy.http.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-14T17:00:00+00:00",
                "method": "POST",
                "path": "/v1/responses",
                "response": {"status": 200},
                "tool_call_count": 1,
                "tool_names": ["apply_patch"],
                "tool_result_count": 1,
                "duration_ms": 17,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-4",
        case_id="case-4",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
        proxy_capture_status="collected",
        proxy_capture_skip_reason=None,
        proxy_artifact_relpath="artifacts/proxy.http.jsonl",
    )

    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    assert any(event.get("source") == "proxy" for event in measured_events)
    assert any(event.get("source_tier") == "A" for event in measured_events)
    assert metadata["telemetry_proxy_status"] == "collected"
    assert metadata["telemetry_tool_call_count"] >= 1
    assert metadata["telemetry_tool_result_count"] >= 1
    assert metadata["tool_event_verdict"] == "confirmed_tool_use"
