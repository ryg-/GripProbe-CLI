from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from gripprobe.models import CaseResult
from gripprobe.reporters.html_report import write_case_detail_pages
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


def discover_run_dirs(runs_root: Path) -> list[Path]:
    root = runs_root.resolve()
    if not root.exists():
        raise ValueError(f"Runs root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Runs root is not a directory: {root}")
    return sorted(
        path.resolve()
        for path in root.iterdir()
        if path.is_dir() and (path / "cases").exists()
    )


def _aggregate_cell_class(items: list[CaseResult]) -> str:
    statuses = {item.status for item in items}
    if statuses == {"PASS"}:
        return "agg-all-pass"
    if "PASS" in statuses:
        return "agg-mixed"
    return "agg-none-pass"


def _aggregate_cell_label(items: list[CaseResult]) -> str:
    return "PASS" if any(item.status == "PASS" for item in items) else "FAIL"


def _source_summary_relpath(output_dir: Path, run_id: str) -> str:
    target = output_dir / "source_reports" / run_id / "summary.html"
    return escape(os.path.relpath(target, output_dir / "reports"))


def _format_run_id_time(run_id: str) -> str:
    try:
        parsed = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return run_id
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _format_duration(seconds: float) -> str:
    return f"{seconds:.1f}s"


def _test_sort_key(title: str, results: list[CaseResult]) -> tuple[int, str]:
    for item in results:
        if item.title == title:
            tags = item.metadata.get("test_tags", [])
            if isinstance(tags, list) and "sanity" in tags:
                return (0, title)
    return (1, title)


def write_aggregate_html_summary(results: list[CaseResult], output_dir: Path) -> None:
    reports_dir = output_dir / "reports"
    cases_dir = output_dir / "cases"
    detail_links = write_case_detail_pages(results, reports_dir, cases_dir)

    tests = sorted({item.title for item in results}, key=lambda title: _test_sort_key(title, results))
    grouped: dict[tuple[str, str, str, str, str], list[CaseResult]] = defaultdict(list)
    for item in results:
        grouped[(item.shell, item.model.label, item.model.backend, item.model.model_hash, item.format)].append(item)

    rows: list[str] = []
    for group_key in sorted(grouped):
        shell, model_label, backend, model_hash, tool_format = group_key
        items = grouped[group_key]
        by_test: dict[str, list[CaseResult]] = defaultdict(list)
        for item in items:
            by_test[item.title].append(item)
        run_ids = sorted({str(item.run_id) for item in items})
        primary_run_id = run_ids[-1]
        group_link = _source_summary_relpath(output_dir, primary_run_id)
        run_links = ", ".join(
            f"<a href='{_source_summary_relpath(output_dir, run_id)}'>{escape(_format_run_id_time(run_id))}</a>"
            for run_id in run_ids
        )
        cells = []
        for test_title in tests:
            test_items = by_test.get(test_title, [])
            if not test_items:
                cells.append("<td class='empty'>-</td>")
                continue
            primary_item = next((item for item in test_items if item.status == "PASS"), test_items[0])
            detail_rel = escape(detail_links[primary_item.case_id])
            cell_class = _aggregate_cell_class(test_items)
            label = _aggregate_cell_label(test_items)
            pass_time_html = (
                f"<span class='cell-time'>{escape(_format_duration(primary_item.timings.measured_seconds))}</span>"
                if label == "PASS"
                else ""
            )
            tooltip = " | ".join(
                f"{item.run_id} ({_format_run_id_time(str(item.run_id))}): {item.status}, "
                f"reason={item.metadata.get('failure_reason', '-')}, {item.trajectory}, "
                f"invoked={item.invoked}, match={item.match_percent}%, measured={_format_duration(item.timings.measured_seconds)}"
                for item in test_items
            )
            cells.append(
                f"<td class='{cell_class}' title='{escape(tooltip)}'>"
                f"<a href='{detail_rel}'>{label}{pass_time_html}</a>"
                "</td>"
            )
        rows.append(
            "<tr>"
            f"<td><a href='{group_link}'>{escape(shell)}</a></td>"
            f"<td><a href='{group_link}'>{escape(model_label)}</a></td>"
            f"<td>{escape(backend)}</td>"
            f"<td>{escape(model_hash)}</td>"
            f"<td>{escape(tool_format)}</td>"
            f"<td>{run_links}</td>"
            f"{''.join(cells)}"
            "</tr>"
        )

    header_tests = "".join(f"<th>{escape(title)}</th>" for title in tests)
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>GripProbe Aggregate Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem;text-align:left;vertical-align:top}}
th{{background:#ece8dc;position:sticky;top:0}}
a{{color:#0b57d0;text-decoration:none;font-weight:600}}
a:hover{{text-decoration:underline}}
.agg-all-pass{{background:#b9e8c2}}
.agg-mixed{{background:#fff0cc}}
.agg-none-pass{{background:#f9d7d7}}
.empty{{background:#f3f1eb;color:#777;text-align:center}}
.meta{{color:#555;margin-bottom:1rem}}
.cell-time{{display:block;font-size:.8rem;font-weight:500;color:#26492d;margin-top:.15rem}}
</style></head><body>
<h1>GripProbe Aggregate Summary</h1>
<p class='meta'>One row per shell/model/backend/hash/format group. Test cells link to a concrete case detail page. Group links open the source run summary.</p>
<table>
<thead><tr><th>Shell</th><th>Model</th><th>Backend</th><th>Hash</th><th>Format</th><th>Runs</th>{header_tests}</tr></thead>
<tbody>
{''.join(rows)}
</tbody></table></body></html>"""
    (reports_dir / "summary.html").write_text(html, encoding="utf-8")


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
    write_aggregate_html_summary(aggregated_results, output_dir)
    write_json(
        output_dir / "aggregate_manifest.json",
        {
            "run_dirs": [str(path.resolve()) for path in run_dirs],
            "runs": [path.name for path in run_dirs],
            "cases": len(aggregated_results),
        },
    )
    return output_dir, aggregated_results
