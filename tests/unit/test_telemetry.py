from __future__ import annotations

import json
from pathlib import Path

from gripprobe.telemetry import extract_and_persist_case_telemetry
from gripprobe.telemetry_proxy import _extract_tool_evidence, _extract_tool_evidence_details


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
    assert summary["telemetry_proxy_tool_call_nonstructured_count"] == 0
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
    assert summary["telemetry_proxy_tool_call_nonstructured_count"] == 0
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


def test_extract_and_persist_case_telemetry_ingests_phase_proxy_artifacts_when_collected(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    proxy_payload = (
        json.dumps(
            {
                "x_gripprobe_timestamp": "2026-05-14T17:00:00+00:00",
                "x_gripprobe_method": "POST",
                "x_gripprobe_path": "/v1/responses",
                "x_gripprobe_response_status": 200,
                "x_gripprobe_tool_call_count": 1,
                "x_gripprobe_tool_names": ["apply_patch"],
                "x_gripprobe_tool_result_count": 1,
                "x_gripprobe_duration_ms": 17,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    (artifacts_dir / "proxy.warmup.http.jsonl").write_text(proxy_payload, encoding="utf-8")
    (artifacts_dir / "proxy.measured.http.jsonl").write_text(proxy_payload, encoding="utf-8")

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-4",
        case_id="case-4",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
        proxy_capture_status="collected",
        proxy_capture_skip_reason=None,
        proxy_artifact_relpaths={
            "warmup": "artifacts/proxy.warmup.http.jsonl",
            "measured": "artifacts/proxy.measured.http.jsonl",
        },
    )

    warmup_events = _read_jsonl(case_dir / "artifacts" / "events.warmup.jsonl")
    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    assert any(event.get("source") == "proxy" and event.get("phase") == "warmup" for event in warmup_events)
    assert any(event.get("source") == "proxy" for event in measured_events)
    assert any(event.get("source_tier") == "A" and event.get("phase") == "measured" for event in measured_events)
    assert metadata["telemetry_proxy_status"] == "collected"
    assert metadata["telemetry_proxy_warmup_http_path"] == "artifacts/proxy.warmup.http.jsonl"
    assert metadata["telemetry_proxy_measured_http_path"] == "artifacts/proxy.measured.http.jsonl"
    assert metadata["telemetry_proxy_warmup_http_count"] == 1
    assert metadata["telemetry_proxy_measured_http_count"] == 1
    assert metadata["telemetry_warmup_tool_call_count"] >= 1
    assert metadata["telemetry_measured_tool_call_count"] >= 1
    assert metadata["telemetry_tool_call_count"] >= 2
    assert metadata["telemetry_proxy_tool_call_nonstructured_count"] == 0
    assert metadata["telemetry_tool_result_count"] >= 2
    assert metadata["tool_event_verdict"] == "confirmed_tool_use"


def test_extract_and_persist_case_telemetry_does_not_confirm_from_warmup_only(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text('@patch(call_1): {"path":"patch-target.txt"}\n', encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("DONE\n", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-warmup-only",
        case_id="case-warmup-only",
        cli_agent_id="codex",
        telemetry_proxy_mode="off",
    )

    assert metadata["telemetry_warmup_tool_call_count"] == 1
    assert metadata["telemetry_measured_tool_call_count"] == 0
    assert metadata["telemetry_tool_call_count"] == 1
    assert metadata["tool_event_verdict"] == "no_tool_event_observed"
    assert metadata["tool_event_verdict_reason"] == "structured_event_absent"


def test_extract_and_persist_case_telemetry_ignores_legacy_proxy_fields(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "proxy.warmup.http.jsonl").write_text("", encoding="utf-8")
    (artifacts_dir / "proxy.measured.http.jsonl").write_text(
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
        run_id="run-5",
        case_id="case-5",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
        proxy_capture_status="collected",
        proxy_capture_skip_reason=None,
        proxy_artifact_relpaths={
            "warmup": "artifacts/proxy.warmup.http.jsonl",
            "measured": "artifacts/proxy.measured.http.jsonl",
        },
    )

    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    assert not any(event.get("source") == "proxy" for event in measured_events)
    assert metadata["telemetry_proxy_status"] == "collected"
    assert metadata["telemetry_tool_call_count"] == 0
    assert metadata["telemetry_proxy_tool_call_nonstructured_count"] == 0
    assert metadata["telemetry_tool_result_count"] == 0


def test_extract_and_persist_case_telemetry_converts_proxy_nonstructured_markers_to_tier_c(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "proxy.warmup.http.jsonl").write_text("", encoding="utf-8")
    (artifacts_dir / "proxy.measured.http.jsonl").write_text(
        json.dumps(
            {
                "x_gripprobe_timestamp": "2026-05-14T17:00:00+00:00",
                "x_gripprobe_method": "POST",
                "x_gripprobe_path": "/v1/chat/completions",
                "x_gripprobe_response_status": 200,
                "x_gripprobe_tool_call_count": 0,
                "x_gripprobe_tool_names": [],
                "x_gripprobe_tool_call_nonstructured_count": 2,
                "x_gripprobe_tool_names_nonstructured": ["read", "write"],
                "x_gripprobe_tool_call_ids_nonstructured": ["call_read", "call_write"],
                "x_gripprobe_tool_result_count": 0,
                "x_gripprobe_duration_ms": 23,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-6",
        case_id="case-6",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
        proxy_capture_status="collected",
        proxy_capture_skip_reason=None,
        proxy_artifact_relpaths={
            "warmup": "artifacts/proxy.warmup.http.jsonl",
            "measured": "artifacts/proxy.measured.http.jsonl",
        },
    )

    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    proxy_events = [event for event in measured_events if event.get("source") == "proxy"]
    assert len(proxy_events) == 2
    assert all(event.get("source_tier") == "C" for event in proxy_events)
    assert all(isinstance(event.get("payload"), dict) for event in proxy_events)
    assert all(event["payload"].get("evidence_mode") == "proxy_nonstructured" for event in proxy_events)
    assert [event.get("tool_call_id") for event in proxy_events] == ["call_read", "call_write"]
    assert metadata["telemetry_tool_call_count"] == 2
    assert metadata["telemetry_proxy_tool_call_nonstructured_count"] == 2
    assert metadata["telemetry_tool_result_count"] == 0


def test_proxy_capture_emits_separate_nonstructured_tool_fields() -> None:
    tool_calls, tool_results, nonstructured_names, nonstructured_ids = _extract_tool_evidence(
        request_payload={"type": "function_call_output"},
        response_payload={"type": "message", "content": "@Read(call_123)"},
        response_body=b"Running @Read(call_123) before final answer",
        response_headers={"Content-Type": "text/plain"},
    )

    assert tool_calls == []
    assert tool_results == 1
    assert nonstructured_names == ["read"]
    assert nonstructured_ids == ["call_123"]


def test_proxy_sse_parser_reconstructs_fragmented_data_frames() -> None:
    body = (
        b"event: response.output_item.added\n"
        b'data: {"type":"response.output_item.added","item":{"type":"function_call",\n'
        b'data: "name":"apply_patch","call_id":"call_sse_1"}}\n'
        b"\n"
        b"event: response.completed\n"
        b"data: [DONE]\n"
        b"\n"
    )

    tool_calls, tool_results, nonstructured_names, nonstructured_ids = _extract_tool_evidence(
        request_payload={"type": "function_call_output", "call_id": "call_sse_1"},
        response_payload=None,
        response_body=body,
        response_headers={"Content-Type": "text/event-stream; charset=utf-8"},
    )

    assert tool_calls == ["apply_patch"]
    assert tool_results == 1
    assert nonstructured_names == []
    assert nonstructured_ids == []


def test_proxy_sse_parser_reconstructs_fragmented_tool_arguments() -> None:
    body = (
        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_frag","type":"function","function":{"name":"Bash","arguments":"{\\"command\\":\\"sed "}}]}}]}\n\n'
        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"s/STATUS=old/STATUS=new/ patch-target.txt"}}]}}]}\n\n'
        b'data: {"id":"x","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"}"}}]}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    evidence = _extract_tool_evidence_details(
        request_payload=None,
        response_payload=None,
        response_body=body,
        response_headers={"Content-Type": "text/event-stream; charset=utf-8"},
    )

    assert evidence.tool_calls == [("Bash", "call_frag")]
    assert evidence.tool_call_details == [
        {
            "tool_name": "Bash",
            "tool_call_id": "call_frag",
            "tool_arguments_json": '{"command":"sed s/STATUS=old/STATUS=new/ patch-target.txt"}',
            "bash_command": "sed s/STATUS=old/STATUS=new/ patch-target.txt",
        }
    ]


def test_extract_and_persist_case_telemetry_dedups_without_phase_bleed(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text(
        '@patch(call_same): {"path":"warmup.txt"}\n@patch(call_same): {"path":"warmup.txt"}\n',
        encoding="utf-8",
    )
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text('@patch(call_same): {"path":"measured.txt"}\n', encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "proxy.warmup.http.jsonl").write_text("", encoding="utf-8")
    (artifacts_dir / "proxy.measured.http.jsonl").write_text(
        json.dumps(
            {
                "x_gripprobe_timestamp": "2026-05-14T17:00:00+00:00",
                "x_gripprobe_method": "POST",
                "x_gripprobe_path": "/v1/responses",
                "x_gripprobe_response_status": 200,
                "x_gripprobe_tool_call_count": 1,
                "x_gripprobe_tool_names": ["patch"],
                "x_gripprobe_tool_call_ids": ["call_same"],
                "x_gripprobe_tool_result_count": 0,
                "x_gripprobe_duration_ms": 17,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-dedup",
        case_id="case-dedup",
        cli_agent_id="codex",
        telemetry_proxy_mode="force",
        proxy_capture_status="collected",
        proxy_capture_skip_reason=None,
        proxy_artifact_relpaths={
            "warmup": "artifacts/proxy.warmup.http.jsonl",
            "measured": "artifacts/proxy.measured.http.jsonl",
        },
    )

    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    measured_tool_calls = [event for event in measured_events if event.get("event_type") == "tool_call_start"]
    assert metadata["telemetry_warmup_tool_call_count"] == 1
    assert metadata["telemetry_measured_tool_call_count"] == 1
    assert metadata["telemetry_tool_call_count"] == 2
    assert len(measured_tool_calls) == 1
    assert measured_tool_calls[0]["source_tier"] == "A"


def test_extract_and_persist_case_telemetry_ignores_auto_title_tool_echo(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text('{"title":"@Read(call_echo)"}\nDONE\n', encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-echo",
        case_id="case-echo",
        cli_agent_id="codex",
        telemetry_proxy_mode="off",
    )

    assert metadata["telemetry_measured_tool_call_count"] == 0
    assert metadata["tool_event_verdict"] == "no_tool_event_observed"


def test_extract_and_persist_case_telemetry_maps_system_ran_command_to_result(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    (case_dir / "warmup.stdout").write_text("", encoding="utf-8")
    (case_dir / "warmup.stderr").write_text("", encoding="utf-8")
    (case_dir / "measured.stdout").write_text("System:\nRan command: `pwd > pwd-output.txt` exit_code=0\n", encoding="utf-8")
    (case_dir / "measured.stderr").write_text("", encoding="utf-8")

    metadata = extract_and_persist_case_telemetry(
        case_dir=case_dir,
        run_id="run-system",
        case_id="case-system",
        cli_agent_id="codex",
        telemetry_proxy_mode="off",
    )

    measured_events = _read_jsonl(case_dir / "artifacts" / "events.measured.jsonl")
    result_events = [event for event in measured_events if event.get("event_type") == "tool_call_result"]
    assert metadata["telemetry_measured_tool_call_count"] == 0
    assert metadata["telemetry_measured_tool_result_count"] == 1
    assert metadata["tool_event_verdict"] == "confirmed_tool_use"
    assert len(result_events) == 1
    assert result_events[0]["status"] == "success"
    assert result_events[0]["exit_code"] == 0
    assert result_events[0]["payload"]["evidence_mode"] == "system_ran_command"
