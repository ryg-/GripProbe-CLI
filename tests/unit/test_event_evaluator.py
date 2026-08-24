from __future__ import annotations

from gripprobe.event_evaluator import apply_event_evaluation
from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings


def _case_result(
    *,
    status: str = "PASS",
    match_percent: int = 100,
    metadata: dict[str, object] | None = None,
) -> CaseResult:
    return CaseResult(
        case_id="case-1",
        run_id="run-1",
        cli_agent_id="codex",
        cli_agent="codex",
        model=CaseModelInfo(
            id="m",
            label="m",
            family="fam",
            size_class="small",
            quantization=None,
            backend="ollama",
            model_id="mid",
            cli_agent_model_id="cid",
            model_hash="hash",
        ),
        format="tool",
        test="t",
        title="Title",
        status=status,  # type: ignore[arg-type]
        trajectory="clean",
        invoked="maybe",
        match_percent=match_percent,
        timings=CaseTimings(warmup_seconds=0.1, measured_seconds=0.2),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={
            "event_capture_status": "collected",
            "tool_event_verdict": "confirmed_tool_use",
            "tool_event_verdict_reason": "none",
            "telemetry_proxy_status": "skipped",
            "telemetry_source_tier": "B",
            **(metadata or {}),
        },
    )


def test_event_evaluator_confirms_full_pass() -> None:
    result = _case_result()

    apply_event_evaluation(result)

    assert result.status == "PASS"
    assert result.invoked == "yes"
    assert result.metadata["strict_pass_score"] == 1.0
    assert result.metadata["overall_score"] == 1.0
    assert result.metadata["failure_reason"] is None


def test_event_evaluator_caps_validator_pass_without_tool_evidence() -> None:
    result = _case_result(
        metadata={
            "tool_event_verdict": "no_tool_event_observed",
            "tool_event_verdict_reason": "structured_event_absent",
        }
    )

    apply_event_evaluation(result)

    assert result.status == "PASS_WITH_POLICY_VIOLATION"
    assert result.invoked == "no"
    assert result.metadata["failure_reason"] == "no_tool_call_observed"
    assert result.metadata["strict_pass_score"] == 0.0
    assert result.metadata["overall_score"] == 0.8


def test_event_evaluator_distinguishes_unobservable_from_no_tool_event() -> None:
    result = _case_result(
        metadata={
            "tool_event_verdict": "tool_event_not_observable",
            "tool_event_verdict_reason": "parser_not_capable_for_shell",
        }
    )

    apply_event_evaluation(result)

    assert result.status == "PASS_WITH_POLICY_VIOLATION"
    assert result.invoked == "maybe"
    assert result.metadata["failure_reason"] == "parser_not_capable_for_shell"


def test_event_evaluator_validator_fail_without_tool_event_is_no_tool_call() -> None:
    result = _case_result(
        status="FAIL",
        match_percent=0,
        metadata={
            "tool_event_verdict": "no_tool_event_observed",
            "tool_event_verdict_reason": "structured_event_absent",
        },
    )

    apply_event_evaluation(result)

    assert result.status == "NO_TOOL_CALL"
    assert result.invoked == "no"
    assert result.metadata["failure_reason"] == "no_tool_call_observed"


def test_event_evaluator_capture_missing_is_harness_error() -> None:
    result = _case_result(
        metadata={
            "event_capture_status": "missing",
            "tool_event_verdict": "tool_event_inconclusive",
            "tool_event_verdict_reason": "capture_missing",
        }
    )

    apply_event_evaluation(result)

    assert result.status == "HARNESS_ERROR"
    assert result.metadata["failure_reason"] == "capture_missing"


def test_event_evaluator_nonzero_exit_is_shell_error_even_when_validators_pass() -> None:
    result = _case_result(metadata={"measured_exit_code": 2})

    apply_event_evaluation(result)

    assert result.status == "SHELL_ERROR"
    assert result.metadata["failure_reason"] == "nonzero_exit"


def test_event_evaluator_marks_force_proxy_without_capture_as_harness_error() -> None:
    result = _case_result(metadata={"telemetry_proxy_status": "error"})

    apply_event_evaluation(result, proxy_required=True)

    assert result.status == "HARNESS_ERROR"
    assert result.invoked == "no"
    assert result.match_percent == 0
    assert result.metadata["failure_reason"] == "proxy_required_but_not_available"
    assert result.metadata["error"] == "telemetry proxy mode=force requires active proxy capture"


def test_event_evaluator_does_not_reject_collected_proxy_in_force_mode() -> None:
    result = _case_result(metadata={"telemetry_proxy_status": "collected"})

    apply_event_evaluation(result, proxy_required=True)

    assert result.status == "PASS"
    assert result.metadata["failure_reason"] is None
