from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

TelemetryProxyMode = Literal["off", "auto", "force"]
TelemetryProxyStatus = Literal["collected", "skipped", "error"]
TelemetryCaptureStatus = Literal["collected", "partial", "missing", "wrapper_parse_error"]
ToolEventVerdict = Literal[
    "confirmed_tool_use",
    "no_tool_event_observed",
    "tool_event_not_observable",
    "tool_event_inconclusive",
]
ToolEventVerdictReason = Literal[
    "none",
    "parser_not_capable_for_shell",
    "capture_missing",
    "proxy_error",
    "structured_event_absent",
    "wrapper_parse_error",
    "source_parse_inconclusive",
]

_PARSER_CAPABLE_CLI_AGENTS = {"codex", "gptme", "opencode", "pi"}
_SENSITIVE_QUERY_PARAM_RE = re.compile(r"([?&](?:token|api[_-]?key|key|auth|authorization)=)[^&\s]+", flags=re.IGNORECASE)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(authorization|api[_-]?key|token|secret|password|nonce)\b(\s*[:=]\s*)([^\s,;\"']+)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+")
_USERNAME_PATH_RE = re.compile(r"(?<![\w$])/(?:home|Users)/[^/\s\"'<>:]+")
_WINDOWS_USERNAME_PATH_RE = re.compile(r"(?<![\w$])[A-Za-z]:\\+Users\\+[^\\/\s\"'<>:]+")
_TOOL_CALL_ID_PATTERN = re.compile(r"@([A-Za-z_][A-Za-z0-9_-]*)\((call_[^) \t]+)\)")
_RECIPIENT_PATTERN = re.compile(r'recipient_name"\s*:\s*"([^"]+)"')
_CONTINUE_TOOL_CALL_PATTERN = re.compile(r"\b(Read|Write|Edit|Bash|Shell|Exec|Run)\(")
_EXIT_CODE_PATTERN = re.compile(r"\bexit_code=(-?\d+)\b")
_RAN_COMMAND_PATTERN = re.compile(r"\bRan command:\s*`?([^`]+)`?", flags=re.IGNORECASE)


@dataclass(frozen=True)
class _ExtractionState:
    parse_error: bool
    base_missing: list[str]
    base_present: list[str]
    structured_inputs_seen: bool
    unstructured_markers_seen: bool


def normalize_telemetry_proxy_mode(mode: str | None) -> TelemetryProxyMode:
    normalized = (mode or "off").strip().lower()
    if normalized not in {"off", "auto", "force"}:
        raise ValueError(f"Unsupported telemetry proxy mode: {mode!r}. Expected one of: off, auto, force.")
    return normalized  # type: ignore[return-value]


def extract_and_persist_case_telemetry(
    *,
    case_dir: Path,
    run_id: str,
    case_id: str,
    cli_agent_id: str,
    telemetry_proxy_mode: TelemetryProxyMode,
    proxy_capture_status: TelemetryProxyStatus | None = None,
    proxy_capture_skip_reason: str | None = None,
    proxy_artifact_relpaths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    artifacts_dir = case_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    warmup_events: list[dict[str, Any]] = []
    measured_events: list[dict[str, Any]] = []
    extraction_state = _ExtractionState(
        parse_error=False,
        base_missing=[],
        base_present=[],
        structured_inputs_seen=False,
        unstructured_markers_seen=False,
    )

    try:
        warmup_events, measured_events, extraction_state = _extract_events_by_phase(
            case_dir=case_dir,
            run_id=run_id,
            case_id=case_id,
        )
    except Exception:
        extraction_state = _ExtractionState(
            parse_error=True,
            base_missing=["warmup.stdout", "warmup.stderr", "measured.stdout", "measured.stderr"],
            base_present=[],
            structured_inputs_seen=False,
            unstructured_markers_seen=False,
        )
        warmup_events = []
        measured_events = []

    telemetry_proxy_status: TelemetryProxyStatus
    telemetry_proxy_skip_reason: str | None
    if proxy_capture_status is None:
        fallback_status, fallback_reason = _proxy_status_for_mode(telemetry_proxy_mode)
        telemetry_proxy_status = fallback_status
        telemetry_proxy_skip_reason = fallback_reason
    else:
        telemetry_proxy_status = proxy_capture_status
        telemetry_proxy_skip_reason = proxy_capture_skip_reason

    proxy_artifact_paths = {
        phase: relpath
        for phase, relpath in (proxy_artifact_relpaths or {}).items()
        if phase in {"warmup", "measured"} and relpath
    }
    proxy_http_counts: dict[str, int] = {"warmup": 0, "measured": 0}
    if telemetry_proxy_status == "collected":
        if set(proxy_artifact_paths) != {"warmup", "measured"}:
            telemetry_proxy_status = "error"
            telemetry_proxy_skip_reason = "capture_missing"
        else:
            for phase in ("warmup", "measured"):
                relpath = proxy_artifact_paths[phase]
                try:
                    proxy_events, proxy_line_count = _extract_proxy_events(
                        proxy_path=case_dir / relpath,
                        run_id=run_id,
                        case_id=case_id,
                        phase=phase,  # type: ignore[arg-type]
                        sequence_start=(len(warmup_events) + 1 if phase == "warmup" else len(measured_events) + 1),
                    )
                    proxy_http_counts[phase] = proxy_line_count
                    if phase == "warmup":
                        warmup_events.extend(proxy_events)
                    else:
                        measured_events.extend(proxy_events)
                except Exception:
                    telemetry_proxy_status = "error"
                    telemetry_proxy_skip_reason = "capture_missing"
                    break

    warmup_events = _deduplicate_events(_drop_result_fallbacks_when_structured_result_present(warmup_events))
    measured_events = _deduplicate_events(_drop_result_fallbacks_when_structured_result_present(measured_events))
    _renumber_events(warmup_events)
    _renumber_events(measured_events)

    _write_jsonl(artifacts_dir / "events.warmup.jsonl", warmup_events)
    _write_jsonl(artifacts_dir / "events.measured.jsonl", measured_events)

    total_events = [*warmup_events, *measured_events]
    warmup_tool_call_events = [event for event in warmup_events if event.get("event_type") == "tool_call_start"]
    measured_tool_call_events = [event for event in measured_events if event.get("event_type") == "tool_call_start"]
    warmup_tool_result_events = [event for event in warmup_events if event.get("event_type") == "tool_call_result"]
    measured_tool_result_events = [event for event in measured_events if event.get("event_type") == "tool_call_result"]
    tool_call_events = [*warmup_tool_call_events, *measured_tool_call_events]
    tool_result_events = [*warmup_tool_result_events, *measured_tool_result_events]
    proxy_nonstructured_tool_call_events = [
        event
        for event in tool_call_events
        if event.get("source") == "proxy"
        and event.get("source_tier") == "C"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("evidence_mode") == "proxy_nonstructured"
    ]
    telemetry_source_tier = _highest_source_tier(total_events)
    telemetry_retry_loop_detected = _detect_retry_loop(tool_call_events)

    event_capture_status = _capture_status(extraction_state)
    tool_event_verdict, tool_event_verdict_reason = _derive_tool_event_verdict(
        cli_agent_id=cli_agent_id,
        event_capture_status=event_capture_status,
        tool_call_count=len(measured_tool_call_events),
        tool_result_count=len(measured_tool_result_events),
        telemetry_proxy_mode=telemetry_proxy_mode,
        telemetry_proxy_status=telemetry_proxy_status,
    )
    telemetry_capture_skip_reason = _capture_skip_reason(event_capture_status)
    telemetry_invoked_confidence = _invoked_confidence(tool_event_verdict)

    summary = {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "case_id": case_id,
        "event_capture_status": event_capture_status,
        "telemetry_proxy_mode": telemetry_proxy_mode,
        "telemetry_proxy_status": telemetry_proxy_status,
        "telemetry_capture_skip_reason": telemetry_capture_skip_reason,
        "telemetry_proxy_skip_reason": telemetry_proxy_skip_reason,
        "telemetry_source_tier": telemetry_source_tier,
        "telemetry_event_count": len(total_events),
        "telemetry_tool_call_count": len(tool_call_events),
        "telemetry_proxy_tool_call_nonstructured_count": len(proxy_nonstructured_tool_call_events),
        "telemetry_tool_result_count": len(tool_result_events),
        "telemetry_invoked_confidence": telemetry_invoked_confidence,
        "telemetry_retry_loop_detected": telemetry_retry_loop_detected,
        "tool_event_verdict": tool_event_verdict,
        "tool_event_verdict_reason": tool_event_verdict_reason,
        "phase_event_counts": {
            "warmup": len(warmup_events),
            "measured": len(measured_events),
        },
        "phase_tool_call_counts": {
            "warmup": len(warmup_tool_call_events),
            "measured": len(measured_tool_call_events),
        },
        "phase_tool_result_counts": {
            "warmup": len(warmup_tool_result_events),
            "measured": len(measured_tool_result_events),
        },
        "telemetry_proxy_http_paths": proxy_artifact_paths,
        "telemetry_proxy_http_counts": proxy_http_counts,
    }
    _write_json(artifacts_dir / "events.summary.json", summary)

    return {
        "event_capture_status": event_capture_status,
        "telemetry_proxy_mode": telemetry_proxy_mode,
        "telemetry_proxy_status": telemetry_proxy_status,
        "telemetry_capture_skip_reason": telemetry_capture_skip_reason,
        "telemetry_proxy_skip_reason": telemetry_proxy_skip_reason,
        "telemetry_source_tier": telemetry_source_tier,
        "telemetry_event_count": len(total_events),
        "telemetry_tool_call_count": len(tool_call_events),
        "telemetry_proxy_tool_call_nonstructured_count": len(proxy_nonstructured_tool_call_events),
        "telemetry_tool_result_count": len(tool_result_events),
        "telemetry_invoked_confidence": telemetry_invoked_confidence,
        "telemetry_retry_loop_detected": telemetry_retry_loop_detected,
        "tool_event_verdict": tool_event_verdict,
        "tool_event_verdict_reason": tool_event_verdict_reason,
        "telemetry_events_warmup_path": "artifacts/events.warmup.jsonl",
        "telemetry_events_measured_path": "artifacts/events.measured.jsonl",
        "telemetry_events_summary_path": "artifacts/events.summary.json",
        "telemetry_proxy_warmup_http_path": proxy_artifact_paths.get("warmup"),
        "telemetry_proxy_measured_http_path": proxy_artifact_paths.get("measured"),
        "telemetry_proxy_http_paths": proxy_artifact_paths,
        "telemetry_proxy_warmup_http_count": proxy_http_counts["warmup"],
        "telemetry_proxy_measured_http_count": proxy_http_counts["measured"],
        "telemetry_warmup_event_count": len(warmup_events),
        "telemetry_measured_event_count": len(measured_events),
        "telemetry_warmup_tool_call_count": len(warmup_tool_call_events),
        "telemetry_measured_tool_call_count": len(measured_tool_call_events),
        "telemetry_warmup_tool_result_count": len(warmup_tool_result_events),
        "telemetry_measured_tool_result_count": len(measured_tool_result_events),
    }


def _extract_events_by_phase(case_dir: Path, run_id: str, case_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], _ExtractionState]:
    phase_events: dict[str, list[dict[str, Any]]] = {"warmup": [], "measured": []}
    sequence_by_phase: dict[str, int] = {"warmup": 1, "measured": 1}
    base_paths = {
        "warmup.stdout": case_dir / "warmup.stdout",
        "warmup.stderr": case_dir / "warmup.stderr",
        "measured.stdout": case_dir / "measured.stdout",
        "measured.stderr": case_dir / "measured.stderr",
    }
    base_missing: list[str] = []
    base_present: list[str] = []
    structured_inputs_seen = False
    unstructured_markers_seen = False

    for name, path in base_paths.items():
        if not path.exists():
            base_missing.append(name)
            continue
        base_present.append(name)
        phase: Literal["warmup", "measured"] = "warmup" if name.startswith("warmup.") else "measured"
        events, sequence, source_structured, source_markers = _extract_events_from_path(
            path=path,
            phase=phase,
            sequence_start=sequence_by_phase[phase],
            run_id=run_id,
            case_id=case_id,
        )
        phase_events[phase].extend(events)
        sequence_by_phase[phase] = sequence
        structured_inputs_seen = structured_inputs_seen or source_structured
        unstructured_markers_seen = unstructured_markers_seen or source_markers

    transcript_paths = sorted(
        path for path in case_dir.rglob("*.jsonl") if path.is_file() and _is_transcript_candidate(path)
    )
    for transcript_path in transcript_paths:
        phase = _phase_from_path(transcript_path)
        events, sequence, source_structured, source_markers = _extract_events_from_path(
            path=transcript_path,
            phase=phase,
            sequence_start=sequence_by_phase[phase],
            run_id=run_id,
            case_id=case_id,
        )
        phase_events[phase].extend(events)
        sequence_by_phase[phase] = sequence
        structured_inputs_seen = structured_inputs_seen or source_structured
        unstructured_markers_seen = unstructured_markers_seen or source_markers

    return (
        phase_events["warmup"],
        phase_events["measured"],
        _ExtractionState(
            parse_error=False,
            base_missing=base_missing,
            base_present=base_present,
            structured_inputs_seen=structured_inputs_seen,
            unstructured_markers_seen=unstructured_markers_seen,
        ),
    )


def _is_transcript_candidate(path: Path) -> bool:
    name = path.name
    if name in {"events.warmup.jsonl", "events.measured.jsonl", "proxy.warmup.http.jsonl", "proxy.measured.http.jsonl"}:
        return False
    if name == "conversation.jsonl":
        return True
    return "transcript" in name.lower()


def _phase_from_path(path: Path) -> Literal["warmup", "measured"]:
    lowered_parts = [part.lower() for part in path.parts]
    if "warmup" in lowered_parts:
        return "warmup"
    if "measured" in lowered_parts:
        return "measured"
    lowered_name = path.name.lower()
    if "warmup" in lowered_name:
        return "warmup"
    return "measured"


def _extract_proxy_events(
    *,
    proxy_path: Path,
    run_id: str,
    case_id: str,
    phase: Literal["warmup", "measured"],
    sequence_start: int,
) -> tuple[list[dict[str, Any]], int]:
    if not proxy_path.exists():
        raise FileNotFoundError(str(proxy_path))
    events: list[dict[str, Any]] = []
    sequence = sequence_start
    line_count = 0
    for index, raw_line in enumerate(proxy_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        line_count += 1
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        timestamp = _as_string(payload.get("x_gripprobe_timestamp")) or _utc_now_iso()
        path = _as_string(payload.get("x_gripprobe_path"))
        method = _as_string(payload.get("x_gripprobe_method")).upper() or "UNKNOWN"
        response_status = _to_int(payload.get("x_gripprobe_response_status"))
        if response_status is None:
            response_payload = payload.get("x_gripprobe_response")
            if isinstance(response_payload, dict):
                response_status = _to_int(response_payload.get("x_gripprobe_status"))
        tool_names_raw = payload.get("x_gripprobe_tool_names")
        tool_names: list[str] = []
        if isinstance(tool_names_raw, list):
            for value in tool_names_raw:
                if isinstance(value, str) and value.strip():
                    tool_names.append(value.strip())
        tool_call_ids = _strings_from_list(payload.get("x_gripprobe_tool_call_ids"))
        call_count = _to_int(payload.get("x_gripprobe_tool_call_count"))
        result_count = _to_int(payload.get("x_gripprobe_tool_result_count"))
        call_count = call_count or 0
        result_count = result_count or 0
        latency_ms = _to_int(payload.get("x_gripprobe_duration_ms"))
        if call_count > len(tool_names):
            tool_names.extend(["unknown"] * (call_count - len(tool_names)))
        for offset, tool_name in enumerate(tool_names):
            events.append(_build_proxy_event(
                event_type="tool_call_start",
                run_id=run_id,
                case_id=case_id,
                phase=phase,
                sequence=sequence,
                source_tier="A",
                status="started",
                timestamp=timestamp,
                raw_artifact_ref=f"{proxy_path.name}:{index}",
                tool_name=tool_name,
                tool_call_id=_known_or_none(tool_call_ids[offset]) if offset < len(tool_call_ids) else None,
                method=method,
                path=path,
                response_status=response_status,
                latency_ms=latency_ms,
                evidence_mode=None,
            ))
            sequence += 1
        result_names = _strings_from_list(payload.get("x_gripprobe_tool_result_names"))
        result_ids = _strings_from_list(payload.get("x_gripprobe_tool_result_ids"))
        if result_count > len(result_names):
            fallback_name = tool_names[0] if tool_names else "unknown"
            result_names.extend([fallback_name] * (result_count - len(result_names)))
        for offset, result_name in enumerate(result_names[: max(result_count, 0)]):
            events.append(_build_proxy_event(
                event_type="tool_call_result",
                run_id=run_id,
                case_id=case_id,
                phase=phase,
                sequence=sequence,
                source_tier="A",
                status="success",
                timestamp=timestamp,
                raw_artifact_ref=f"{proxy_path.name}:{index}",
                tool_name=result_name,
                tool_call_id=_known_or_none(result_ids[offset]) if offset < len(result_ids) else None,
                method=method,
                path=path,
                response_status=response_status,
                latency_ms=latency_ms,
                evidence_mode=None,
            ))
            sequence += 1
        nonstructured_count = _to_int(payload.get("x_gripprobe_tool_call_nonstructured_count")) or 0
        nonstructured_names = _strings_from_list(payload.get("x_gripprobe_tool_names_nonstructured"))
        nonstructured_call_ids = _strings_from_list(payload.get("x_gripprobe_tool_call_ids_nonstructured"))
        if nonstructured_count > len(nonstructured_names):
            nonstructured_names.extend(["unknown"] * (nonstructured_count - len(nonstructured_names)))
        for offset, tool_name in enumerate(nonstructured_names):
            events.append(_build_proxy_event(
                event_type="tool_call_start",
                run_id=run_id,
                case_id=case_id,
                phase=phase,
                sequence=sequence,
                source_tier="C",
                status="started",
                timestamp=timestamp,
                raw_artifact_ref=f"{proxy_path.name}:{index}",
                tool_name=tool_name,
                tool_call_id=nonstructured_call_ids[offset] if offset < len(nonstructured_call_ids) else None,
                method=method,
                path=path,
                response_status=response_status,
                latency_ms=latency_ms,
                evidence_mode="proxy_nonstructured",
            ))
            sequence += 1
    return events, line_count


def _strings_from_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _known_or_none(value: str) -> str | None:
    stripped = value.strip()
    if not stripped or stripped.lower() == "unknown":
        return None
    return stripped


def _build_proxy_event(
    *,
    event_type: Literal["tool_call_start", "tool_call_result"],
    run_id: str,
    case_id: str,
    phase: Literal["warmup", "measured"],
    sequence: int,
    source_tier: Literal["A", "C"],
    status: str,
    timestamp: str,
    raw_artifact_ref: str,
    tool_name: str,
    tool_call_id: str | None,
    method: str,
    path: str,
    response_status: int | None,
    latency_ms: int | None,
    evidence_mode: str | None,
) -> dict[str, Any]:
    event_payload = {
        "tool_name": tool_name,
        "http_method": method,
        "http_path": path,
        "response_status": response_status,
        "evidence_mode": evidence_mode,
    }
    return {
        "event_type": event_type,
        "run_id": run_id,
        "case_id": case_id,
        "phase": phase,
        "event_id": f"{phase}-{sequence:04d}",
        "trace_id": phase,
        "tool_call_id": tool_call_id,
        "response_id": None,
        "source_tier": source_tier,
        "payload": _sanitize_obj({key: value for key, value in event_payload.items() if value is not None}),
        "timestamp": _sanitize_text(timestamp),
        "sequence": sequence,
        "source": "proxy",
        "status": status,
        "latency_ms": latency_ms,
        "exit_code": None,
        "error_type": None,
        "raw_artifact_ref": raw_artifact_ref,
        "redaction_status": "redacted",
    }


def _extract_events_from_path(
    *,
    path: Path,
    phase: Literal["warmup", "measured"],
    sequence_start: int,
    run_id: str,
    case_id: str,
) -> tuple[list[dict[str, Any]], int, bool, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    events: list[dict[str, Any]] = []
    sequence = sequence_start
    structured_inputs_seen = False
    unstructured_markers_seen = False
    previous_nonempty_line = ""
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        event: dict[str, Any] | None = None
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                structured_inputs_seen = True
                event = _event_from_json_payload(
                    payload=payload,
                    run_id=run_id,
                    case_id=case_id,
                    phase=phase,
                    sequence=sequence,
                    raw_artifact_ref=f"{path.name}:{index}",
                )
        if event is None:
            text_event = _event_from_text_line(
                line=line,
                previous_line=previous_nonempty_line,
                run_id=run_id,
                case_id=case_id,
                phase=phase,
                sequence=sequence,
                raw_artifact_ref=f"{path.name}:{index}",
            )
            if text_event is not None:
                unstructured_markers_seen = True
                event = text_event
        if event is not None:
            events.append(event)
            sequence += 1
        previous_nonempty_line = line
    return events, sequence, structured_inputs_seen, unstructured_markers_seen


def _event_from_json_payload(
    *,
    payload: dict[str, Any],
    run_id: str,
    case_id: str,
    phase: Literal["warmup", "measured"],
    sequence: int,
    raw_artifact_ref: str,
) -> dict[str, Any] | None:
    event_type: str | None = None
    source_tier = "B"
    status = "unknown"
    tool_name = _as_string(payload.get("tool_name")) or _as_string(payload.get("tool"))
    tool_call_id = _as_string(payload.get("tool_call_id")) or _as_string(payload.get("call_id"))
    response_id = _as_string(payload.get("response_id")) or _as_string(payload.get("id"))
    payload_type = _as_string(payload.get("type")).lower()
    recipient_name = _as_string(payload.get("recipient_name"))

    if recipient_name:
        event_type = "tool_call_start"
        status = "started"
        if not tool_name and "." in recipient_name:
            tool_name = recipient_name.rsplit(".", 1)[-1]
    elif payload_type in {"tool_call", "tool_use", "function_call", "command_execution"}:
        event_type = "tool_call_start"
        status = "started"
    elif payload_type in {"tool_result", "function_result", "command_result", "command_execution_result", "tool_output"}:
        event_type = "tool_call_result"
        status = _normalize_status(payload.get("status"), payload.get("success"), payload.get("exit_code"))
    elif payload_type in {"message", "response", "completion", "assistant_message", "model_response"}:
        event_type = "model_response"
    elif _as_string(payload.get("role")).lower() in {"assistant", "model"}:
        event_type = "model_response"

    if event_type is None:
        return None

    event_payload: dict[str, Any] = {
        "type": payload_type or None,
        "tool_name": tool_name,
        "recipient_name": recipient_name,
        "role": _as_string(payload.get("role")) or None,
        "content_excerpt": _excerpt(_as_string(payload.get("content"))),
        "message_excerpt": _excerpt(_as_string(payload.get("message"))),
        "error": _excerpt(_as_string(payload.get("error"))),
    }
    event_payload = {key: value for key, value in event_payload.items() if value not in {None, ""}}
    exit_code = _to_int(payload.get("exit_code"))
    latency_ms = _to_int(payload.get("latency_ms"))
    timestamp = (
        _as_string(payload.get("timestamp"))
        or _as_string(payload.get("created_at"))
        or _as_string(payload.get("time"))
        or _utc_now_iso()
    )

    return {
        "event_type": event_type,
        "run_id": run_id,
        "case_id": case_id,
        "phase": phase,
        "event_id": f"{phase}-{sequence:04d}",
        "trace_id": phase,
        "tool_call_id": tool_call_id,
        "response_id": response_id,
        "source_tier": source_tier,
        "payload": _sanitize_obj(event_payload),
        "timestamp": _sanitize_text(timestamp),
        "sequence": sequence,
        "source": "agent_output",
        "status": status,
        "latency_ms": latency_ms,
        "exit_code": exit_code,
        "error_type": _as_string(payload.get("error_type")) or None,
        "raw_artifact_ref": raw_artifact_ref,
        "redaction_status": "redacted",
    }


def _event_from_text_line(
    *,
    line: str,
    previous_line: str,
    run_id: str,
    case_id: str,
    phase: Literal["warmup", "measured"],
    sequence: int,
    raw_artifact_ref: str,
) -> dict[str, Any] | None:
    ran_command_match = _RAN_COMMAND_PATTERN.search(line)
    if ran_command_match and (line.lower().startswith("system:") or previous_line.lower() == "system:"):
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="tool_call_result",
            status="success",
            tool_name="shell",
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
            evidence_mode="system_ran_command",
        )

    recipient_match = _RECIPIENT_PATTERN.search(line)
    if recipient_match:
        recipient_name = recipient_match.group(1)
        tool_name = recipient_name.rsplit(".", 1)[-1] if "." in recipient_name else recipient_name
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="tool_call_start",
            status="started",
            tool_name=tool_name,
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
        )

    if _is_known_echo_noise(line):
        return None

    call_match = _TOOL_CALL_ID_PATTERN.search(line)
    if call_match:
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="tool_call_start",
            status="started",
            tool_name=call_match.group(1).lower(),
            tool_call_id=call_match.group(2),
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
        )

    continue_match = _CONTINUE_TOOL_CALL_PATTERN.search(line)
    if continue_match:
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="tool_call_start",
            status="started",
            tool_name=continue_match.group(1).lower(),
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
        )

    if any(marker in line for marker in ("Applied edit to", "Creating empty file", "Added ")):
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="tool_call_result",
            status="success",
            tool_name="edit",
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
        )

    if re.search(r"\b(DONE|FAIL)\b", line):
        return _build_text_event(
            run_id=run_id,
            case_id=case_id,
            phase=phase,
            sequence=sequence,
            event_type="model_response",
            status="unknown",
            raw_artifact_ref=raw_artifact_ref,
            line=line,
            source_tier="C",
        )

    return None


def _build_text_event(
    *,
    run_id: str,
    case_id: str,
    phase: Literal["warmup", "measured"],
    sequence: int,
    event_type: Literal["tool_call_start", "tool_call_result", "model_response"],
    status: str,
    raw_artifact_ref: str,
    line: str,
    source_tier: Literal["C"],
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    evidence_mode: str | None = None,
) -> dict[str, Any]:
    exit_code_match = _EXIT_CODE_PATTERN.search(line)
    exit_code = int(exit_code_match.group(1)) if exit_code_match else None
    normalized_status = status
    if event_type == "tool_call_result" and exit_code is not None:
        if exit_code == 124:
            normalized_status = "timeout"
        elif exit_code == 0:
            normalized_status = "success"
        else:
            normalized_status = "error"
    return {
        "event_type": event_type,
        "run_id": run_id,
        "case_id": case_id,
        "phase": phase,
        "event_id": f"{phase}-{sequence:04d}",
        "trace_id": phase,
        "tool_call_id": tool_call_id,
        "response_id": None,
        "source_tier": source_tier,
        "payload": _sanitize_obj(
            {key: value for key, value in {
                "tool_name": tool_name,
                "line_excerpt": _excerpt(line),
                "evidence_mode": evidence_mode,
            }.items() if value is not None}
        ),
        "timestamp": _utc_now_iso(),
        "sequence": sequence,
        "source": "wrapper",
        "status": normalized_status,
        "latency_ms": None,
        "exit_code": exit_code,
        "error_type": None,
        "raw_artifact_ref": raw_artifact_ref,
        "redaction_status": "redacted",
    }


def _drop_result_fallbacks_when_structured_result_present(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    has_structured_result = any(
        event.get("event_type") == "tool_call_result" and event.get("source_tier") in {"A", "B"}
        for event in events
    )
    if not has_structured_result:
        return events
    return [
        event
        for event in events
        if not (
            event.get("event_type") == "tool_call_result"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("evidence_mode") == "system_ran_command"
        )
    ]


def _deduplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str, str, str], int] = {}
    for event in events:
        key = _event_dedup_key(event)
        if key not in index_by_key:
            index_by_key[key] = len(deduped)
            deduped.append(event)
            continue
        existing_index = index_by_key[key]
        if _event_precedence(event) > _event_precedence(deduped[existing_index]):
            deduped[existing_index] = event
    return deduped


def _event_dedup_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    phase = _as_string(event.get("phase")) or "unknown"
    event_type = _as_string(event.get("event_type")) or "unknown"
    tool_name = _event_tool_name(event)
    call_id = _as_string(event.get("tool_call_id")).strip()
    if call_id:
        return (phase, tool_name, call_id, event_type)
    return (phase, tool_name, _event_fallback_dedup_token(event), event_type)


def _event_tool_name(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if isinstance(payload, dict):
        value = payload.get("tool_name")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        recipient = payload.get("recipient_name")
        if isinstance(recipient, str) and recipient.strip():
            return recipient.rsplit(".", 1)[-1].strip().lower()
    return "unknown"


def _event_fallback_dedup_token(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if isinstance(payload, dict):
        for key in ("line_excerpt", "content_excerpt", "message_excerpt", "recipient_name", "evidence_mode"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return f"fallback:{key}:{value.strip().lower()}"
    return f"fallback:tool:{_event_tool_name(event)}"


def _event_precedence(event: dict[str, Any]) -> tuple[int, int]:
    tier_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
    source_rank = {"proxy": 3, "agent_output": 2, "wrapper": 1}
    return (
        tier_rank.get(_as_string(event.get("source_tier")), 0),
        source_rank.get(_as_string(event.get("source")), 0),
    )


def _renumber_events(events: list[dict[str, Any]]) -> None:
    phase = _as_string(events[0].get("phase")) if events else ""
    for sequence, event in enumerate(events, start=1):
        event["sequence"] = sequence
        event_phase = _as_string(event.get("phase")) or phase or "unknown"
        event["event_id"] = f"{event_phase}-{sequence:04d}"


def _is_known_echo_noise(line: str) -> bool:
    lowered = line.lower()
    if "auto-title" in lowered or "auto_title" in lowered:
        return True
    return ("\"title\"" in lowered or "'title'" in lowered) and _TOOL_CALL_ID_PATTERN.search(line) is not None


def _capture_status(state: _ExtractionState) -> TelemetryCaptureStatus:
    if state.parse_error:
        return "wrapper_parse_error"
    measured_missing = "measured.stdout" in state.base_missing and "measured.stderr" in state.base_missing
    if measured_missing:
        return "missing"
    if state.base_missing:
        return "partial"
    return "collected"


def _derive_tool_event_verdict(
    *,
    cli_agent_id: str,
    event_capture_status: TelemetryCaptureStatus,
    tool_call_count: int,
    tool_result_count: int,
    telemetry_proxy_mode: TelemetryProxyMode,
    telemetry_proxy_status: TelemetryProxyStatus,
) -> tuple[ToolEventVerdict, ToolEventVerdictReason]:
    if event_capture_status == "wrapper_parse_error":
        return "tool_event_inconclusive", "wrapper_parse_error"
    if event_capture_status == "missing":
        return "tool_event_inconclusive", "capture_missing"
    if tool_call_count > 0 or tool_result_count > 0:
        return "confirmed_tool_use", "none"
    if telemetry_proxy_mode == "force" and telemetry_proxy_status == "error":
        return "tool_event_inconclusive", "proxy_error"
    if cli_agent_id not in _PARSER_CAPABLE_CLI_AGENTS:
        return "tool_event_not_observable", "parser_not_capable_for_shell"
    return "no_tool_event_observed", "structured_event_absent"


def _proxy_status_for_mode(mode: TelemetryProxyMode) -> tuple[TelemetryProxyStatus, str | None]:
    if mode == "off":
        return "skipped", "disabled"
    if mode == "auto":
        return "skipped", "unsupported_backend"
    return "error", "unsupported_backend"


def _capture_skip_reason(event_capture_status: TelemetryCaptureStatus) -> str | None:
    if event_capture_status == "wrapper_parse_error":
        return "wrapper_parse_error"
    if event_capture_status == "missing":
        return "capture_missing"
    return None


def _highest_source_tier(events: list[dict[str, Any]]) -> str:
    tier_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
    best = "none"
    best_score = 0
    for event in events:
        tier = str(event.get("source_tier") or "")
        score = tier_rank.get(tier, 0)
        if score > best_score:
            best_score = score
            best = tier
    return best


def _detect_retry_loop(tool_call_events: list[dict[str, Any]]) -> bool:
    names = []
    for event in tool_call_events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            names.append(tool_name)
    if len(names) < 3:
        return False
    for index in range(len(names) - 2):
        if names[index] == names[index + 1] == names[index + 2]:
            return True
    return False


def _invoked_confidence(verdict: ToolEventVerdict) -> float:
    if verdict == "confirmed_tool_use":
        return 1.0
    if verdict == "no_tool_event_observed":
        return 0.0
    if verdict == "tool_event_not_observable":
        return 0.2
    return 0.1


def _normalize_status(status: object, success: object, exit_code: object) -> str:
    raw = _as_string(status).lower()
    if raw in {"started", "success", "error", "timeout", "unknown"}:
        return raw
    if isinstance(success, bool):
        return "success" if success else "error"
    exit_value = _to_int(exit_code)
    if exit_value is None:
        return "unknown"
    if exit_value == 124:
        return "timeout"
    if exit_value == 0:
        return "success"
    return "error"


def _sanitize_text(value: str) -> str:
    sanitized = value
    home = str(Path.home())
    if home and home != "/":
        sanitized = sanitized.replace(home, "$HOME")
    sanitized = _USERNAME_PATH_RE.sub("$HOME", sanitized)
    sanitized = _WINDOWS_USERNAME_PATH_RE.sub("$HOME", sanitized)
    username = Path.home().name
    if username:
        sanitized = re.sub(
            rf"(?<![A-Za-z0-9_.-]){re.escape(username)}(?![A-Za-z0-9_.-])",
            "$USER",
            sanitized,
        )
    sanitized = _BEARER_TOKEN_RE.sub("Bearer [redacted]", sanitized)
    sanitized = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1\2[redacted]", sanitized)
    sanitized = _SENSITIVE_QUERY_PARAM_RE.sub(r"\1[redacted]", sanitized)
    return sanitized


def _sanitize_obj(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_obj(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_obj(item) for key, item in value.items()}
    return value


def _excerpt(value: str, max_length: int = 240) -> str:
    if not value:
        return ""
    cleaned = _sanitize_text(value.strip())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3] + "..."


def _as_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        path.write_text("", encoding="utf-8")
        return
    lines = [json.dumps(_sanitize_obj(event), ensure_ascii=False) for event in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize_obj(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
