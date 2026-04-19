from __future__ import annotations

import json
from pathlib import Path

from gripprobe.case_result import CaseStatus, ToolInvocation
from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings, ModelSpec
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import strip_system_messages_from_transcripts, write_json
from gripprobe.spec_loader import load_model_specs


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

    if observed and expected and observed == expected:
        return "PASS", "yes"
    if "No tool call detected in last message" in measured_stdout or "No tool call detected in last message" in measured_stderr:
        return "NO_TOOL_CALL", "no"
    if "does not support tools" in measured_stdout or "does not support tools" in measured_stderr:
        return "TOOL_UNSUPPORTED", "no"
    if measured_stdout or measured_stderr or observed or expected:
        return "FAIL", "maybe"
    return "HARNESS_ERROR", "no"


def _fallback_title(test_id: str) -> str:
    return test_id.replace("_", " ").title()


def _load_case_result(case_dir: Path, model_index: dict[str, ModelSpec]) -> CaseResult:
    case_json = case_dir / "case.json"
    if case_json.exists():
        return CaseResult.model_validate(json.loads(case_json.read_text(encoding="utf-8")))

    case_id = case_dir.name
    parts = case_id.split("__")
    if len(parts) < 5:
        raise ValueError(f"Could not parse case_id from directory name: {case_id}")

    shell, model_id, backend, tool_format, test_id = parts[:5]
    run_id = case_dir.parents[2].name
    model_spec = model_index.get(model_id)
    status: CaseStatus
    invoked: ToolInvocation
    status, invoked = _fallback_status(case_dir)
    expected = (case_dir / "expected.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "expected.txt").exists() else ""
    observed = (case_dir / "observed.txt").read_text(encoding="utf-8", errors="replace").strip() if (case_dir / "observed.txt").exists() else ""
    match_percent = 100 if expected and observed and expected == observed else 0

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
            model_hash=backend_spec.model_hash if backend_spec else "unknown",
        ),
        format=tool_format,
        test=test_id,
        title=_fallback_title(test_id),
        status=status,
        invoked=invoked,
        match_percent=match_percent,
        timings=CaseTimings(warmup_seconds=0.0, measured_seconds=0.0),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={"rebuilt": True, "source": "fallback"},
    )
    write_json(case_json, result.model_dump())
    return result


def rebuild_reports(run_dir: Path, keep_system_messages: bool = False) -> tuple[Path, list[CaseResult]]:
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
            results.append(_load_case_result(case_dir, model_index))
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
