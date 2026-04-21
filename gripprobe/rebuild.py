from __future__ import annotations

import json
from pathlib import Path

from gripprobe.case_result import CaseStatus, ToolInvocation
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings, ModelSpec
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import strip_system_messages_from_transcripts, write_json
from gripprobe.spec_loader import load_model_specs, load_test_specs
from gripprobe.trace_analysis import (
    RunConsistency,
    Trajectory,
    analyze_trace,
    compare_profiles,
    derive_trajectory,
    explain_trajectory,
    infer_trace_status,
)
from gripprobe.validator_runner import evaluate_validators


def _infer_root_from_run_dir(run_dir: Path) -> Path:
    return run_dir.parents[2]


def _load_model_index(root: Path) -> dict[str, ModelSpec]:
    specs = load_model_specs(root)
    return {spec.id: spec for spec in specs}


def _fallback_status(case_dir: Path) -> tuple[CaseStatus, ToolInvocation]:
    measured_stdout = (case_dir / "measured.stdout").read_text(encoding="utf-8", errors="replace") if (case_dir / "measured.stdout").exists() else ""
    measured_stderr = (case_dir / "measured.stderr").read_text(encoding="utf-8", errors="replace") if (case_dir / "measured.stderr").exists() else ""
    observed = (case_dir / "observed.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "observed.txt").exists() else ""
    expected = (case_dir / "expected.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "expected.txt").exists() else ""
    completion_lines = {line.strip() for line in f"{measured_stdout}\n{measured_stderr}".splitlines() if line.strip() in {"DONE", "FAIL"}}

    if observed and expected and observed == expected:
        return "PASS", "yes"
    if "No tool call detected in last message" in measured_stdout or "No tool call detected in last message" in measured_stderr:
        return "NO_TOOL_CALL", "no"
    if "does not support tools" in measured_stdout or "does not support tools" in measured_stderr:
        return "TOOL_UNSUPPORTED", "no"
    if completion_lines:
        return "FAIL", "no"
    if measured_stdout or measured_stderr or observed or expected:
        return "FAIL", "maybe"
    return "HARNESS_ERROR", "no"


def _fallback_title(test_id: str) -> str:
    return test_id.replace("_", " ").title()


def _build_recomputed_case_result(case_dir: Path, model_index: dict[str, ModelSpec]) -> CaseResult:
    case_json = case_dir / "case.json"
    existing_payload: dict | None = None
    if case_json.exists():
        existing_payload = json.loads(case_json.read_text(encoding="utf-8"))

    case_id = case_dir.name
    parts = case_id.split("__")
    if len(parts) < 5:
        raise ValueError(f"Could not parse case_id from directory name: {case_id}")

    shell, model_id, backend, tool_format, test_id = parts[:5]
    run_id = case_dir.parents[1].name
    model_spec = model_index.get(model_id)
    root = case_dir.parents[4]
    test_index = {spec.id: spec for spec in load_test_specs(root)}
    test_spec = test_index.get(test_id)
    measured_stdout = (case_dir / "measured.stdout").read_text(encoding="utf-8", errors="replace") if (case_dir / "measured.stdout").exists() else ""
    measured_stderr = (case_dir / "measured.stderr").read_text(encoding="utf-8", errors="replace") if (case_dir / "measured.stderr").exists() else ""
    warmup_stdout = (case_dir / "warmup.stdout").read_text(encoding="utf-8", errors="replace") if (case_dir / "warmup.stdout").exists() else ""
    warmup_stderr = (case_dir / "warmup.stderr").read_text(encoding="utf-8", errors="replace") if (case_dir / "warmup.stderr").exists() else ""
    run_1_profile = analyze_trace(warmup_stdout, warmup_stderr)
    run_2_profile = analyze_trace(measured_stdout, measured_stderr)
    no_retry_on_error = test_spec.rules.no_retry_on_error if test_spec else False
    trajectory: Trajectory = derive_trajectory(run_2_profile, no_retry_on_error, measured_stdout, measured_stderr)
    trajectory_reasons = explain_trajectory(
        trajectory,
        run_2_profile,
        no_retry_on_error,
        measured_stdout,
        measured_stderr,
    )
    existing_metadata = existing_payload.get("metadata", {}) if isinstance(existing_payload, dict) else {}
    if not isinstance(existing_metadata, dict):
        existing_metadata = {}
    existing_timings = existing_payload.get("timings", {}) if isinstance(existing_payload, dict) else {}
    if not isinstance(existing_timings, dict):
        existing_timings = {}

    workspace = case_dir / "workspace"
    validators_ok = False
    expected = (case_dir / "expected.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "expected.txt").exists() else ""
    observed = (case_dir / "observed.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "observed.txt").exists() else ""
    if test_spec:
        validators_ok, expected, observed = evaluate_validators(test_spec, workspace)

    measured_exit_code = existing_metadata.get("measured_exit_code")
    warmup_exit_code = existing_metadata.get("warmup_exit_code")
    measured_timed_out = measured_exit_code == 124 or "timeout=true" in measured_stdout or "timeout=true" in measured_stderr
    warmup_timed_out = warmup_exit_code == 124 or "timeout=true" in warmup_stdout or "timeout=true" in warmup_stderr

    status: CaseStatus
    invoked: ToolInvocation
    artifact_reached_before_timeout = False
    if measured_timed_out:
        artifact_reached_before_timeout = validators_ok
        status = "TIMEOUT"
        invoked = run_2_profile.invoked
        match_percent = 100 if validators_ok else 0
    elif validators_ok:
        status = "PASS"
        invoked = "yes"
        match_percent = 100
    else:
        status, invoked = _fallback_status(case_dir)
        match_percent = 100 if expected and observed and expected == observed else 0

    run_1_status = infer_trace_status(run_1_profile, warmup_stdout, warmup_stderr, timed_out=warmup_timed_out)
    run_consistency: RunConsistency = compare_profiles(run_1_profile, run_2_profile, run_1_status, status)

    model_label = model_spec.label if model_spec else model_id
    family = model_spec.family if model_spec else "unknown"
    size_class = model_spec.size_class if model_spec else "unknown"
    quantization = model_spec.quantization if model_spec else None
    backend_spec = None
    if model_spec:
        for item in model_spec.backends:
            if item.id == backend:
                backend_spec = item
                break
    resolved_model_hash = (
        existing_metadata.get("model_hash")
        or (backend_spec.model_hash if backend_spec and backend_spec.model_hash else None)
        or "unknown"
    )

    result = CaseResult(
        case_id=case_id,
        run_id=run_id,
        shell=shell,
        model=CaseModelInfo(
            id=model_id,
            label=model_label,
            family=family,
            size_class=size_class,
            quantization=quantization,
            backend=backend,
            model_id=backend_spec.model_id if backend_spec else model_id,
            shell_model_id=backend_spec.shell_model_id if backend_spec else model_label,
            model_hash=resolved_model_hash,
        ),
        format=tool_format,
        test=test_id,
        title=_fallback_title(test_id),
        status=status,
        trajectory=trajectory,
        invoked=invoked,
        match_percent=match_percent,
        timings=CaseTimings(
            warmup_seconds=float(existing_timings.get("warmup_seconds", 0.0)),
            measured_seconds=float(existing_timings.get("measured_seconds", 0.0)),
        ),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={
            **existing_metadata,
            "rebuilt": True,
            "source": "recomputed" if existing_payload is not None else "fallback",
            "artifact_reached_before_timeout": artifact_reached_before_timeout,
            "failure_reason": infer_failure_reason(status, invoked, measured_stdout, measured_stderr),
            "run_1_status": run_1_status,
            "run_2_status": status,
            "run_1_profile": run_1_profile.as_metadata(),
            "run_2_profile": run_2_profile.as_metadata(),
            "run_consistency": run_consistency,
            "language": test_spec.language if test_spec else "en",
            "rules": test_spec.rules.model_dump() if test_spec else {},
            "test_tags": list(test_spec.tags) if test_spec else [],
            "trajectory_reasons": trajectory_reasons,
        },
    )
    write_json(case_json, result.model_dump())
    return result


def _load_case_result(case_dir: Path, model_index: dict[str, ModelSpec], recompute_case_json: bool = False) -> CaseResult:
    case_json = case_dir / "case.json"
    if case_json.exists() and not recompute_case_json:
        return CaseResult.model_validate(json.loads(case_json.read_text(encoding="utf-8")))
    return _build_recomputed_case_result(case_dir, model_index)


def rebuild_reports(run_dir: Path, keep_system_messages: bool = False, recompute_case_json: bool = False) -> tuple[Path, list[CaseResult]]:
    run_dir = run_dir.resolve()
    root = _infer_root_from_run_dir(run_dir)
    model_index = _load_model_index(root)
    cases_dir = run_dir / "cases"
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if not keep_system_messages:
        strip_system_messages_from_transcripts(cases_dir)

    results: list[CaseResult] = []
    for case_dir in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
        try:
            results.append(_load_case_result(case_dir, model_index, recompute_case_json=recompute_case_json))
        except Exception as exc:
            fallback_case_json = case_dir / "case.json"
            payload = {
                "error": str(exc),
                "case_dir": str(case_dir),
                "rebuilt": True,
                "source": "error",
            }
            write_json(fallback_case_json, payload)
    write_markdown_summary(results, reports_dir / "summary.md")
    write_html_summary(results, reports_dir / "summary.html")
    return run_dir, results
