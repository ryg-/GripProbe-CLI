from __future__ import annotations

import json
import shutil
from pathlib import Path

from gripprobe.models import CaseResult
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import write_json


def _prefixed_case_id(run_id: str, case_id: str) -> str:
    return f"{run_id}__{case_id}"


def _copy_case_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _copy_source_reports(run_dir: Path, output_dir: Path) -> None:
    reports_dir = run_dir / "reports"
    if not reports_dir.exists():
        return
    target_root = output_dir / "source_reports" / run_dir.name
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(reports_dir, target_root)


def aggregate_reports(run_dirs: list[Path], output_dir: Path) -> tuple[Path, list[CaseResult]]:
    output_dir = output_dir.resolve()
    cases_dir = output_dir / "cases"
    reports_dir = output_dir / "reports"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    aggregated_results: list[CaseResult] = []
    for run_dir in [path.resolve() for path in run_dirs]:
        _copy_source_reports(run_dir, output_dir)
        source_cases_dir = run_dir / "cases"
        if not source_cases_dir.exists():
            continue
        for case_dir in sorted(path for path in source_cases_dir.iterdir() if path.is_dir()):
            case_json = case_dir / "case.json"
            if not case_json.exists():
                continue
            result = CaseResult.model_validate(json.loads(case_json.read_text(encoding="utf-8")))
            aggregate_case_id = _prefixed_case_id(run_dir.name, result.case_id)
            aggregate_case_dir = cases_dir / aggregate_case_id
            _copy_case_dir(case_dir, aggregate_case_dir)
            aggregate_result = result.model_copy(
                update={
                    "case_id": aggregate_case_id,
                    "run_id": run_dir.name,
                    "metadata": {
                        **result.metadata,
                        "source_run_dir": str(run_dir),
                        "source_case_id": result.case_id,
                    },
                }
            )
            write_json(aggregate_case_dir / "case.json", aggregate_result.model_dump())
            aggregated_results.append(aggregate_result)

    write_markdown_summary(aggregated_results, reports_dir / "summary.md")
    write_html_summary(aggregated_results, reports_dir / "summary.html")
    write_json(
        output_dir / "aggregate_manifest.json",
        {
            "run_dirs": [str(path.resolve()) for path in run_dirs],
            "runs": [path.name for path in run_dirs],
            "cases": len(aggregated_results),
        },
    )
    return output_dir, aggregated_results
