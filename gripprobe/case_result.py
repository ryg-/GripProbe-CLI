from __future__ import annotations

from typing import Any, Literal

from gripprobe.models import CaseDefinition, CaseLogs, CaseModelInfo, CaseResult, CaseTimings, ModelSpec, TestSpec


CaseStatus = Literal[
    "PASS",
    "FAIL",
    "TIMEOUT",
    "NO_TOOL_CALL",
    "TOOL_UNSUPPORTED",
    "SHELL_ERROR",
    "HARNESS_ERROR",
    "SKIPPED",
]
ToolInvocation = Literal["yes", "no", "maybe"]
Trajectory = Literal["clean", "recovered", "violated"]


DEFAULT_LOGS = CaseLogs(
    prompt="prompt.txt",
    warmup_stdout="warmup.stdout",
    warmup_stderr="warmup.stderr",
    measured_stdout="measured.stdout",
    measured_stderr="measured.stderr",
)


def build_case_model_info(case: CaseDefinition, model_spec: ModelSpec) -> CaseModelInfo:
    return CaseModelInfo(
        id=case.model_id,
        label=case.model_label,
        family=model_spec.family,
        size_class=model_spec.size_class,
        quantization=case.quantization,
        backend=case.backend_id,
        model_id=case.backend_model_id,
        shell_model_id=case.shell_model_id,
        model_hash=case.model_hash,
    )


def build_case_logs() -> CaseLogs:
    return DEFAULT_LOGS.model_copy(deep=True)


def build_case_result(
    *,
    case: CaseDefinition,
    model_spec: ModelSpec,
    test_spec: TestSpec,
    status: CaseStatus,
    trajectory: Trajectory = "clean",
    invoked: ToolInvocation,
    match_percent: int,
    warmup_seconds: float,
    measured_seconds: float,
    metadata: dict[str, Any],
) -> CaseResult:
    metadata = {**metadata}
    metadata.setdefault("test_tags", list(test_spec.tags))
    return CaseResult(
        case_id=case.case_id,
        run_id=case.run_id,
        shell=case.shell_label,
        model=build_case_model_info(case, model_spec),
        format=case.tool_format,
        test=case.test_id,
        title=test_spec.title,
        status=status,
        trajectory=trajectory,
        invoked=invoked,
        match_percent=match_percent,
        timings=CaseTimings(
            warmup_seconds=round(warmup_seconds, 3),
            measured_seconds=round(measured_seconds, 3),
        ),
        logs=build_case_logs(),
        metadata=metadata,
    )
