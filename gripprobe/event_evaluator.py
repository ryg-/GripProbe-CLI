from __future__ import annotations

from typing import Any

from gripprobe.models import CaseResult


def apply_event_evaluation(result: CaseResult) -> None:
    """Normalize case verdict fields from process, validator, and telemetry evidence."""
    metadata = dict(result.metadata)
    final_status, reason_code, reason_text = _evaluate_status(result, metadata)
    artifact_match = _artifact_match(result)
    tool_invocation_match = _tool_invocation_match(metadata)
    strict_pass_score = 1.0 if final_status == "PASS" else 0.0
    overall_score = 1.0 if final_status == "PASS" else 0.8 if final_status == "PASS_WITH_POLICY_VIOLATION" else 0.0

    result.status = final_status
    if final_status != "HARNESS_ERROR":
        result.invoked = _invoked_from_tool_verdict(metadata)
        result.trajectory = _trajectory_from_events(result, metadata)
    result.metadata = {
        **metadata,
        "verdict_source": "event_evaluator",
        "artifact_match": artifact_match,
        "tool_invocation_match": tool_invocation_match,
        "protocol_match": _protocol_match(metadata),
        "strict_pass_score": strict_pass_score,
        "overall_score": overall_score,
        "evaluator_reason_code": reason_code,
        "evaluator_reason_text": reason_text,
        "failure_reason": None if final_status == "PASS" else reason_code,
    }


def _evaluate_status(result: CaseResult, metadata: dict[str, Any]) -> tuple[str, str, str]:
    current_status = result.status
    measured_exit_code = _to_int(metadata.get("measured_exit_code"))
    validators_pass = _validators_pass(result)
    verdict = str(metadata.get("tool_event_verdict") or "tool_event_inconclusive")
    verdict_reason = str(metadata.get("tool_event_verdict_reason") or "source_parse_inconclusive")
    capture_status = str(metadata.get("event_capture_status") or "")

    if current_status == "TIMEOUT" or measured_exit_code == 124:
        return "TIMEOUT", "timeout", "measured process timed out"
    if current_status == "HARNESS_ERROR":
        return "HARNESS_ERROR", _existing_or("harness_error", metadata), "GripProbe infrastructure failed"
    if capture_status in {"missing", "wrapper_parse_error"}:
        reason = "capture_missing" if capture_status == "missing" else "wrapper_parse_error"
        return "HARNESS_ERROR", reason, "mandatory wrapper telemetry capture failed"
    if current_status == "SHELL_ERROR":
        return "SHELL_ERROR", _existing_or("process_error", metadata), "CLI agent process failed"
    if measured_exit_code not in {None, 0}:
        return "SHELL_ERROR", "nonzero_exit", "CLI agent process exited non-zero"
    if current_status == "TOOL_UNSUPPORTED":
        return "TOOL_UNSUPPORTED", _existing_or("backend_tool_unsupported", metadata), "required tool capability is unsupported"

    if validators_pass and verdict == "confirmed_tool_use":
        return "PASS", "none", "validators passed and required tool evidence was confirmed"
    if validators_pass and verdict in {
        "no_tool_event_observed",
        "tool_event_not_observable",
        "tool_event_inconclusive",
    }:
        return (
            "PASS_WITH_POLICY_VIOLATION",
            _policy_reason(verdict, verdict_reason),
            "validators passed, but required tool evidence is missing or inconclusive",
        )
    if not validators_pass and verdict == "no_tool_event_observed":
        return "NO_TOOL_CALL", "no_tool_call_observed", "validators failed and no observable tool event was found"
    if not validators_pass and verdict == "confirmed_tool_use":
        return "FAIL", "artifact_mismatch_after_success", "validators failed after observed tool execution"
    if not validators_pass and verdict == "tool_event_not_observable":
        return "FAIL", "artifact_mismatch_tool_event_not_observable", "validators failed and tool evidence was not observable"
    if not validators_pass and verdict == "tool_event_inconclusive":
        if verdict_reason in {"capture_missing", "wrapper_parse_error"}:
            return "HARNESS_ERROR", verdict_reason, "mandatory telemetry evidence is unavailable"
        return "FAIL", "artifact_mismatch_tool_event_inconclusive", "validators failed with inconclusive tool evidence"

    return "FAIL", "artifact_mismatch", "validators failed"


def _validators_pass(result: CaseResult) -> bool:
    if result.status == "PASS":
        return True
    if result.status == "PASS_WITH_POLICY_VIOLATION":
        return True
    if result.status == "TIMEOUT":
        return bool(result.metadata.get("artifact_reached_before_timeout"))
    return result.match_percent >= 100


def _artifact_match(result: CaseResult) -> float:
    return max(0.0, min(1.0, float(result.match_percent) / 100.0))


def _tool_invocation_match(metadata: dict[str, Any]) -> float:
    return 1.0 if metadata.get("tool_event_verdict") == "confirmed_tool_use" else 0.0


def _protocol_match(metadata: dict[str, Any]) -> float | None:
    if metadata.get("telemetry_proxy_status") != "collected":
        return None
    if metadata.get("telemetry_source_tier") == "A" and metadata.get("tool_event_verdict") == "confirmed_tool_use":
        return 1.0
    return 0.0


def _invoked_from_tool_verdict(metadata: dict[str, Any]) -> str:
    verdict = metadata.get("tool_event_verdict")
    if verdict == "confirmed_tool_use":
        return "yes"
    if verdict == "no_tool_event_observed":
        return "no"
    return "maybe"


def _trajectory_from_events(result: CaseResult, metadata: dict[str, Any]) -> str:
    if metadata.get("telemetry_retry_loop_detected"):
        return "violated" if result.status in {"FAIL", "NO_TOOL_CALL"} else "recovered"
    if result.status == "TIMEOUT":
        return "recovered" if metadata.get("artifact_reached_before_timeout") else "violated"
    return result.trajectory


def _policy_reason(verdict: str, verdict_reason: str) -> str:
    if verdict == "no_tool_event_observed":
        return "no_tool_call_observed"
    if verdict == "tool_event_not_observable":
        return verdict_reason or "parser_not_capable_for_shell"
    return verdict_reason or "source_parse_inconclusive"


def _existing_or(default: str, metadata: dict[str, Any]) -> str:
    existing = metadata.get("failure_reason")
    return str(existing) if existing else default


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
