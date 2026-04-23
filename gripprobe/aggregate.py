from __future__ import annotations

import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from statistics import median

from gripprobe.models import CaseResult
from gripprobe.reporters.html_report import write_case_detail_pages
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import write_json

SANITY_WEIGHT = 0.8
DEFAULT_TEST_WEIGHT = 1.0
OUTLIER_FACTOR = 2.5


def _prefixed_case_id(run_id: str, case_id: str) -> str:
    return f"{run_id}__{case_id}"


def _copy_case_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore_dangling_symlinks=True)


def _copy_source_reports(run_dir: Path, output_dir: Path) -> None:
    reports_dir = run_dir / "reports"
    if not reports_dir.exists():
        return
    target_root = output_dir / "source_reports" / run_dir.name
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(reports_dir, target_root, ignore_dangling_symlinks=True)
    _strip_sections_from_source_reports(target_root)
    _sanitize_source_reports(target_root)


def _strip_named_section_from_html(html_path: Path, heading: str) -> None:
    text = html_path.read_text(encoding="utf-8")
    marker = f"<h2>{heading}</h2>"
    start = text.find(marker)
    if start == -1:
        return
    section_start = text.rfind("<section>", 0, start)
    section_end = text.find("</section>", start)
    if section_start == -1 or section_end == -1:
        return
    updated = text[:section_start] + text[section_end + len("</section>"):]
    html_path.write_text(updated, encoding="utf-8")


def _strip_sections_from_source_reports(reports_root: Path) -> None:
    cases_dir = reports_root / "cases"
    if not cases_dir.exists():
        return
    for html_path in cases_dir.glob("*.html"):
        _strip_named_section_from_html(html_path, "Raw Artifacts")
        _strip_named_section_from_html(html_path, "Runtime Snapshots")
        _strip_named_section_from_html(html_path, "Case JSON")


def _sanitize_report_text(text: str) -> str:
    home = str(Path.home())
    username = Path.home().name
    sanitized = text.replace(home, "$HOME")
    sanitized = re.sub(r"https?://[^/\s\"'<>:]+:11434", "http://ollama-host:11434", sanitized)
    sanitized = re.sub(r"\bssh\s+[^/\s\"'<>:]+", "ssh ollama-host", sanitized)
    sanitized = sanitized.replace(username, "$USER")
    return sanitized


def _sanitize_source_reports(reports_root: Path) -> None:
    for path in reports_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".html", ".md", ".json", ".txt"}:
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = _sanitize_report_text(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


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


def _has_extended_test_tags(item: CaseResult) -> bool:
    tags = item.metadata.get("test_tags", [])
    return isinstance(tags, list) and "non_sanity" in tags


def _is_sanity_case(item: CaseResult) -> bool:
    tags = item.metadata.get("test_tags", [])
    return isinstance(tags, list) and "sanity" in tags


def _test_weight(test_items: list[CaseResult]) -> float:
    if any(_is_sanity_case(item) for item in test_items):
        return SANITY_WEIGHT
    return DEFAULT_TEST_WEIGHT


def _representative_case(test_items: list[CaseResult]) -> CaseResult:
    return next((item for item in test_items if item.status == "PASS"), test_items[0])


def _group_score(by_test: dict[str, list[CaseResult]]) -> float:
    if not by_test:
        return 0.0
    weighted_pass_sum = 0.0
    weight_sum = 0.0
    for test_items in by_test.values():
        if not test_items:
            continue
        weight = _test_weight(test_items)
        representative = _representative_case(test_items)
        if representative.status == "PASS":
            weighted_pass_sum += weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return weighted_pass_sum / weight_sum


def _group_typical_time_and_outliers(
    by_test: dict[str, list[CaseResult]],
    baseline_medians_by_test: dict[str, float],
) -> tuple[float, int, int]:
    representative_times: list[tuple[str, float]] = []
    for test_title, test_items in by_test.items():
        if not test_items:
            continue
        representative = _representative_case(test_items)
        representative_times.append((test_title, representative.timings.measured_seconds))
    if not representative_times:
        return 0.0, 0, 0
    typical_time = median(value for _, value in representative_times)
    outliers = 0
    for test_title, value in representative_times:
        baseline = baseline_medians_by_test.get(test_title, 0.0)
        if baseline > 0 and value > baseline * OUTLIER_FACTOR:
            outliers += 1
    return typical_time, outliers, len(representative_times)


def write_aggregate_html_summary(results: list[CaseResult], output_dir: Path) -> None:
    reports_dir = output_dir / "reports"
    cases_dir = output_dir / "cases"
    detail_links = write_case_detail_pages(
        results,
        reports_dir,
        cases_dir,
        show_artifacts=False,
        show_runtime_snapshots=False,
        show_case_json=False,
    )

    tests = sorted({item.title for item in results}, key=lambda title: _test_sort_key(title, results))
    grouped: dict[tuple[str, str, str, str, str], list[CaseResult]] = defaultdict(list)
    for item in results:
        grouped[(item.shell, item.model.label, item.model.backend, item.model.model_hash, item.format)].append(item)

    grouped_by_test: dict[tuple[str, str, str, str, str], dict[str, list[CaseResult]]] = {}
    representative_time_samples_by_test: dict[str, list[float]] = defaultdict(list)
    for group_key, items in grouped.items():
        by_test: dict[str, list[CaseResult]] = defaultdict(list)
        for item in items:
            by_test[item.title].append(item)
        grouped_by_test[group_key] = by_test
        for test_title, test_items in by_test.items():
            representative = _representative_case(test_items)
            representative_time_samples_by_test[test_title].append(representative.timings.measured_seconds)

    baseline_medians_by_test = {
        test_title: median(samples)
        for test_title, samples in representative_time_samples_by_test.items()
        if samples
    }

    rows: list[str] = []
    for group_key in sorted(grouped):
        shell, model_label, backend, model_hash, tool_format = group_key
        items = grouped[group_key]
        has_extended_set = any(_has_extended_test_tags(item) for item in items)
        by_test = grouped_by_test[group_key]
        score = _group_score(by_test)
        typical_time, outlier_count, outlier_total = _group_typical_time_and_outliers(by_test, baseline_medians_by_test)
        outlier_rate = (outlier_count / outlier_total) if outlier_total else 0.0
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
            primary_item = _representative_case(test_items)
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
            "<tr "
            f"data-shell='{escape(shell)}' "
            f"data-model='{escape(model_label)}' "
            f"data-format='{escape(tool_format)}' "
            f"data-extended='{'yes' if has_extended_set else 'no'}' "
            f"data-score='{score:.4f}' "
            f"data-typical='{typical_time:.4f}' "
            f"data-outliers='{outlier_rate:.4f}'>"
            f"<td><a href='{group_link}'>{escape(shell)}</a></td>"
            f"<td><a href='{group_link}'>{escape(model_label)}"
            f"<span class='model-meta'>{escape(model_hash)}</span>"
            "</a></td>"
            f"<td>{escape(backend)}</td>"
            f"<td>{escape(tool_format)}</td>"
            f"<td>{score * 100:.1f}%</td>"
            f"<td>{_format_duration(typical_time)}</td>"
            f"<td>{outlier_count}/{outlier_total}</td>"
            f"<td>{run_links}</td>"
            f"{''.join(cells)}"
            "</tr>"
        )

    header_tests = "".join(f"<th>{escape(title)}</th>" for title in tests)
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>GripProbe Aggregate Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111;font-size:14px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.4rem;text-align:left;vertical-align:top}}
th{{background:#ece8dc;position:sticky;top:0;font-size:.92rem}}
a{{color:#0b57d0;text-decoration:none;font-weight:600}}
a:hover{{text-decoration:underline}}
.agg-all-pass{{background:#b9e8c2}}
.agg-mixed{{background:#fff0cc}}
.agg-none-pass{{background:#f9d7d7}}
.empty{{background:#f3f1eb;color:#777;text-align:center}}
.meta{{color:#555;margin-bottom:1rem;font-size:.9rem}}
.cell-time{{display:block;font-size:.75rem;font-weight:500;color:#26492d;margin-top:.12rem}}
.model-meta{{display:block;font-size:.68rem;font-weight:500;color:#666;margin-top:.18rem;word-break:break-all}}
.sort-controls{{display:inline-flex;gap:.2rem;margin-left:.35rem;vertical-align:middle}}
.sort-btn{{border:1px solid #c9c3b4;background:#f7f3e8;color:#555;border-radius:4px;padding:0 .22rem;font-size:.66rem;line-height:1.15;cursor:pointer}}
.sort-btn:hover{{background:#efe6d3;color:#222}}
.controls{{display:flex;align-items:center;gap:.5rem;margin:.6rem 0 1rem 0;color:#333}}
.controls input{{margin:0}}
.row-hidden{{display:none}}
</style></head><body>
<h1>GripProbe Aggregate Summary</h1>
<p class='meta'>One row per shell/model/backend/hash/format group. Test cells link to a concrete case detail page. Group links open the source run summary.</p>
<div class='controls'>
<input id='hide-no-extended' type='checkbox' />
<label for='hide-no-extended'>Hide rows without extended test set (non_sanity)</label>
</div>
<table>
<thead><tr>
<th>Shell<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('shell', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('shell', 'desc')">▼</button></span></th>
<th>Model<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('model', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('model', 'desc')">▼</button></span></th>
<th>Backend</th>
<th>Format<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('format', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('format', 'desc')">▼</button></span></th>
<th>Score<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('score', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('score', 'desc')">▼</button></span></th>
<th>Typical Time<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('typical', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('typical', 'desc')">▼</button></span></th>
<th>Outliers<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('outliers', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('outliers', 'desc')">▼</button></span></th>
<th>Runs</th>{header_tests}</tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
<script>
function sortRows(key, direction) {{
  const tbody = document.querySelector("tbody");
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll("tr"));
  rows.sort((a, b) => {{
    if (key === "score" || key === "typical" || key === "outliers") {{
      const av = Number(a.dataset[key] || "0");
      const bv = Number(b.dataset[key] || "0");
      const cmp = av - bv;
      return direction === "asc" ? cmp : -cmp;
    }}
    const av = (a.dataset[key] || "").toLowerCase();
    const bv = (b.dataset[key] || "").toLowerCase();
    const cmp = av.localeCompare(bv, undefined, {{ numeric: true, sensitivity: "base" }});
    return direction === "asc" ? cmp : -cmp;
  }});
  rows.forEach((row) => tbody.appendChild(row));
  applyRowFilters();
}}

function applyRowFilters() {{
  const hideNoExtended = document.getElementById("hide-no-extended");
  const shouldHide = Boolean(hideNoExtended && hideNoExtended.checked);
  const rows = Array.from(document.querySelectorAll("tbody tr"));
  rows.forEach((row) => {{
    const hasExtended = (row.dataset.extended || "no") === "yes";
    row.classList.toggle("row-hidden", shouldHide && !hasExtended);
  }});
}}

document.getElementById("hide-no-extended")?.addEventListener("change", applyRowFilters);
applyRowFilters();
</script>
</body></html>"""
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
