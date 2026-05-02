from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from statistics import median

from gripprobe.models import CaseResult, HardwareProfileSpec
from gripprobe.reporters.html_report import write_case_detail_pages
from gripprobe.results import write_json
from gripprobe.spec_loader import load_hardware_profiles

SANITY_WEIGHT = 0.8
DEFAULT_TEST_WEIGHT = 1.0
OUTLIER_FACTOR = 2.5
DEFAULT_HARDWARE_PROFILE_ID = "unspecified"
_SANITIZED_TEXT_SUFFIXES = {
    ".html",
    ".md",
    ".json",
    ".txt",
    ".stdout",
    ".stderr",
    ".jsonl",
    ".toml",
    ".yaml",
    ".yml",
    ".log",
}


def _prefixed_case_id(run_id: str, case_id: str) -> str:
    return f"{run_id}__{case_id}"


def _copy_case_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore_case_items(dir_path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            # Runtime directories are debug-only and may contain root-owned lock files.
            if name == "runtime":
                ignored.add(name)
                continue
            path = Path(dir_path) / name
            try:
                if path.is_symlink():
                    continue
            except OSError:
                ignored.add(name)
                continue
            if not os.access(path, os.R_OK):
                ignored.add(name)
        return ignored

    shutil.copytree(
        src,
        dst,
        ignore_dangling_symlinks=True,
        ignore=_ignore_case_items,
    )


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


def _sanitize_user_paths(text: str) -> str:
    sanitized = re.sub(r"(?<![\w$])/(?:home|Users)/[^/\s\"'<>:]+", "$HOME", text)
    sanitized = re.sub(r"(?<![\w$])[A-Za-z]:\\+Users\\+[^\\/\s\"'<>:]+", "$HOME", sanitized)
    return sanitized


def _sanitize_local_username(text: str) -> str:
    username = Path.home().name
    if not username:
        return text
    return re.sub(rf"(?<![A-Za-z0-9_.-]){re.escape(username)}(?![A-Za-z0-9_.-])", "$USER", text)


def _sanitize_report_text(text: str) -> str:
    sanitized = _sanitize_user_paths(text)
    sanitized = _sanitize_local_username(sanitized)
    sanitized = re.sub(r"https?://[^/\s\"'<>:]+:11434", "http://ollama-host:11434", sanitized)
    sanitized = re.sub(r"\bssh\s+[^/\s\"'<>:]+", "ssh ollama-host", sanitized)
    return sanitized


def _sanitize_tree_text_files(root_dir: Path) -> None:
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SANITIZED_TEXT_SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = _sanitize_report_text(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")


def _sanitize_source_reports(reports_root: Path) -> None:
    _sanitize_tree_text_files(reports_root)


def _sanitize_case_result(result: CaseResult) -> CaseResult:
    def _sanitize_value(value: object) -> object:
        if isinstance(value, str):
            return _sanitize_report_text(value)
        if isinstance(value, list):
            return [_sanitize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: _sanitize_value(item) for key, item in value.items()}
        return value

    payload = result.model_dump()
    sanitized_payload = _sanitize_value(payload)
    if not isinstance(sanitized_payload, dict):
        return result
    return CaseResult.model_validate(sanitized_payload)


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
    severity = _worst_failure_severity(items)
    return f"agg-fail-{severity}"


def _failure_severity(item: CaseResult) -> str:
    if item.status in {"HARNESS_ERROR", "SHELL_ERROR"}:
        return "critical"
    if item.status == "TIMEOUT":
        return "error"
    reason = item.metadata.get("failure_reason")
    if item.status in {"TOOL_UNSUPPORTED", "NO_TOOL_CALL"} or reason == "tool unsupported by backend":
        return "behavioral"
    return "soft"


def _worst_failure_severity(items: list[CaseResult]) -> str:
    rank = {"soft": 0, "behavioral": 1, "error": 2, "critical": 3}
    worst = "soft"
    for item in items:
        if item.status == "PASS":
            continue
        severity = _failure_severity(item)
        if rank[severity] > rank[worst]:
            worst = severity
    return worst


def _aggregate_cell_label(items: list[CaseResult]) -> str:
    return "PASS" if any(item.status == "PASS" for item in items) else "FAIL"


def _display_failure_reason(value: object) -> str:
    text = str(value or "-")
    if text == "tool unsupported by backend":
        return "tool unsupported"
    return text


def _source_summary_relpath(output_dir: Path, run_id: str) -> str:
    target = output_dir / "source_reports" / run_id / "summary.html"
    return escape(os.path.relpath(target, output_dir / "reports"))


def _format_run_id_time(run_id: str) -> str:
    try:
        parsed = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return run_id
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_duration(seconds: float) -> str:
    return f"{seconds:.1f}s"


def _short_hash(value: str) -> str:
    raw = value.strip()
    if not raw or raw == "unknown":
        return raw
    if raw.startswith("sha256:"):
        raw = raw.split(":", 1)[1]
    return raw if len(raw) <= 7 else raw[:7]


def _hardware_profile_id(item: CaseResult, default_profile_id: str = DEFAULT_HARDWARE_PROFILE_ID) -> str:
    raw = item.metadata.get("hardware_profile_id")
    if not isinstance(raw, str):
        return default_profile_id
    value = raw.strip()
    return value or default_profile_id


def _load_hardware_profile_data(root: Path | None) -> tuple[dict[str, HardwareProfileSpec], str]:
    if root is None:
        return {}, DEFAULT_HARDWARE_PROFILE_ID
    profiles = load_hardware_profiles(root)
    if not profiles:
        return {}, DEFAULT_HARDWARE_PROFILE_ID
    return {profile.id: profile for profile in profiles}, profiles[0].id


def _render_hardware_cards(profile_ids: list[str], profile_map: dict[str, HardwareProfileSpec]) -> str:
    if not profile_ids:
        return ""
    cards: list[str] = []
    for profile_id in profile_ids:
        profile = profile_map.get(profile_id)
        if profile is None:
            cards.append(
                "<div class='hw-card'>"
                f"<h4>{escape(profile_id)}</h4>"
                "<table>"
                "<tr><th>CPU</th><td>unknown</td></tr>"
                "<tr><th>GPU</th><td>unknown</td></tr>"
                "<tr><th>RAM</th><td>unknown</td></tr>"
                "</table>"
                "<p class='hw-note'>No matching profile in specs/hardware_profiles.yaml</p>"
                "</div>"
            )
            continue
        notes_html = f"<p class='hw-note'>{escape(profile.notes)}</p>" if profile.notes else ""
        cards.append(
            "<div class='hw-card'>"
            f"<h4>{escape(profile.id)}</h4>"
            "<table>"
            f"<tr><th>CPU</th><td>{escape(profile.cpu)}</td></tr>"
            f"<tr><th>GPU</th><td>{escape(profile.gpu)}</td></tr>"
            f"<tr><th>RAM</th><td>{escape(profile.ram)}</td></tr>"
            "</table>"
            f"{notes_html}"
            "</div>"
        )
    warning = (
        "<p class='hw-warning'>Timings span multiple hardware profiles; compare across rows with care.</p>"
        if len(profile_ids) > 1
        else ""
    )
    return (
        "<aside class='hardware-summary'>"
        "<div class='hardware-title'>Hardware Profiles</div>"
        f"{warning}"
        "<div class='hw-cards'>"
        f"{''.join(cards)}"
        "</div>"
        "</aside>"
    )


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


def _render_scope_summary(shells: list[str], formats: list[str]) -> str:
    shell_text = ", ".join(shells) if shells else "none"
    format_text = ", ".join(formats) if formats else "none"
    return (
        "<aside class='scope-summary'>"
        "<div class='scope-title'>Scope</div>"
        "<table>"
        f"<tr><th>Shells</th><td>{escape(shell_text)}</td></tr>"
        f"<tr><th>Formats</th><td>{escape(format_text)}</td></tr>"
        "</table>"
        "</aside>"
    )


def _git_commit_sha(root: Path | None) -> str:
    if root is None:
        return "unknown"
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = (probe.stdout or "").strip()
    return value or "unknown"


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


def _write_aggregate_markdown_summary(
    results: list[CaseResult],
    path: Path,
    *,
    generated_at: str,
    commit_sha: str,
    shells: list[str],
    models: list[str],
    formats: list[str],
    hardware_profile_ids: list[str],
    hardware_profiles_relpath: str | None,
) -> None:
    lines = [
        "# GripProbe Compatibility Report",
        "",
        "## Reproducibility",
        f"- Shells: `{', '.join(shells) if shells else 'none'}`",
        f"- Models: `{', '.join(models) if models else 'none'}`",
        f"- Formats: `{', '.join(formats) if formats else 'none'}`",
        f"- Hardware profile id: `{', '.join(hardware_profile_ids) if hardware_profile_ids else 'unspecified'}`",
    ]
    if hardware_profiles_relpath:
        lines.append(f"- Hardware profile spec: [{hardware_profiles_relpath}]({hardware_profiles_relpath})")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Shell | Model | Backend | Hash | Format | Test | Status | Reason | Trajectory | Invoked | Match | Warmup (s) | Measured (s) |",
            "|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for item in results:
        lines.append(
            f"| {item.shell} | {item.model.label} | {item.model.backend} | {item.model.model_hash} | {item.format} | {item.title} | {item.status} | {item.metadata.get('failure_reason') or ''} | {item.trajectory} | {item.invoked} | {item.match_percent} | {item.timings.warmup_seconds} | {item.timings.measured_seconds} |"
        )
    lines.extend(
        [
            "",
            f"generated at {generated_at} | git commit {commit_sha}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_aggregate_html_summary(
    results: list[CaseResult],
    output_dir: Path,
    hardware_profile_map: dict[str, HardwareProfileSpec] | None = None,
    default_hardware_profile_id: str = DEFAULT_HARDWARE_PROFILE_ID,
    tests_doc_relpath: str | None = None,
    generated_at: str | None = None,
    commit_sha: str = "unknown",
    hardware_profiles_relpath: str | None = None,
) -> None:
    reports_dir = output_dir / "reports"
    cases_dir = output_dir / "cases"
    detail_filenames = {
        item.case_id: f"case-{index:05d}.html"
        for index, item in enumerate(results, start=1)
    }
    detail_links = write_case_detail_pages(
        results,
        reports_dir,
        cases_dir,
        detail_filenames=detail_filenames,
        show_artifacts=False,
        show_runtime_snapshots=False,
        show_case_json=False,
    )

    tests = sorted({item.title for item in results}, key=lambda title: _test_sort_key(title, results))
    grouped: dict[tuple[str, str, str, str, str], list[CaseResult]] = defaultdict(list)
    for item in results:
        grouped[
            (
                item.shell,
                item.model.label,
                item.model.model_hash,
                item.format,
                _hardware_profile_id(item, default_hardware_profile_id),
            )
        ].append(item)

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

    profile_ids = sorted({_hardware_profile_id(item, default_hardware_profile_id) for item in results})
    show_model_profile_meta = len(profile_ids) > 1
    hardware_cards_html = _render_hardware_cards(profile_ids, hardware_profile_map or {})
    tests_doc_link_html = ""
    if tests_doc_relpath:
        tests_doc_link_html = (
            "<p class='tests-doc-link-line'>"
            f"<a href='{escape(tests_doc_relpath)}'>Test descriptions</a>"
            "</p>"
        )
    shell_filter_options = "".join(
        [
            "<option value='all'>all</option>",
            *[f"<option value='{escape(shell)}'>{escape(shell)}</option>" for shell in sorted({item.shell for item in results})],
        ]
    )
    model_filter_options = "".join(
        [
            "<option value='all'>all</option>",
            *[
                f"<option value='{escape(model)}'>{escape(model)}</option>"
                for model in sorted({item.model.label for item in results})
            ],
        ]
    )

    rows: list[str] = []
    for group_key in sorted(grouped):
        shell, model_label, model_hash, tool_format, hardware_profile_id = group_key
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
        hw_meta_html = f"<span class='hw-meta'>{escape(hardware_profile_id)}</span>" if show_model_profile_meta else ""
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
                f"reason={_display_failure_reason(item.metadata.get('failure_reason'))}, {item.trajectory}, "
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
            f"data-hw='{escape(hardware_profile_id)}' "
            f"data-extended='{'yes' if has_extended_set else 'no'}' "
            f"data-score='{score:.4f}' "
            f"data-typical='{typical_time:.4f}' "
            f"data-outliers='{outlier_rate:.4f}'>"
            f"<td><a href='{group_link}'>{escape(shell)}</a></td>"
            f"<td><a href='{group_link}'>{escape(model_label)}"
            f"<span class='model-meta'>{escape(_short_hash(model_hash))}</span>"
            f"{hw_meta_html}"
            "</a></td>"
            f"<td>{escape(tool_format)}</td>"
            f"<td>{score * 100:.1f}%</td>"
            f"<td>{_format_duration(typical_time)}</td>"
            f"<td>{outlier_count}/{outlier_total}</td>"
            f"{''.join(cells)}"
            f"<td class='runs-meta'>{run_links}</td>"
            "</tr>"
        )

    header_tests = "".join(f"<th>{escape(title)}</th>" for title in tests)
    generated_at_value = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    shells_value = sorted({item.shell for item in results})
    models_value = sorted({item.model.label for item in results})
    formats_value = sorted({item.format for item in results})
    hardware_ids_value = sorted({_hardware_profile_id(item, default_hardware_profile_id) for item in results})
    scope_summary_html = _render_scope_summary(shells_value, formats_value)

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>GripProbe Compatibility Report</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111;font-size:14px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.4rem;text-align:left;vertical-align:top}}
th{{background:#ece8dc;position:sticky;top:0;font-size:.92rem}}
a{{color:#0b57d0;text-decoration:none;font-weight:600}}
a:hover{{text-decoration:underline}}
.agg-all-pass{{background:#b9e8c2}}
.agg-mixed{{background:#fff0cc}}
.agg-fail-soft{{background:#e8ddc7}}
.agg-fail-behavioral{{background:#f6d5b2}}
.agg-fail-error{{background:#f3b3b3}}
.agg-fail-critical{{background:#e48686}}
.empty{{background:#f3f1eb;color:#777;text-align:center}}
.meta{{color:#555;margin-bottom:1rem;font-size:.9rem}}
.cell-time{{display:block;font-size:.75rem;font-weight:500;color:#26492d;margin-top:.12rem}}
.model-meta{{display:block;font-size:.68rem;font-weight:500;color:#666;margin-top:.18rem;word-break:break-all}}
.hw-meta{{display:block;font-size:.68rem;font-weight:500;color:#666;margin-top:.18rem;word-break:break-all}}
.runs-meta{{font-size:.68rem;font-weight:500;color:#666;line-height:1.35}}
.sort-controls{{display:inline-flex;gap:.2rem;margin-left:.35rem;vertical-align:middle}}
.sort-btn{{border:1px solid #c9c3b4;background:#f7f3e8;color:#555;border-radius:4px;padding:0 .22rem;font-size:.66rem;line-height:1.15;cursor:pointer}}
.sort-btn:hover{{background:#efe6d3;color:#222}}
.controls{{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 1rem 0;color:#333}}
.controls .meta{{flex:0 0 100%;margin:0 0 .15rem 0}}
.controls input{{margin:0}}
.controls select{{border:1px solid #c9c3b4;background:#fff;border-radius:4px;padding:.12rem .25rem;font-size:.85rem}}
.row-hidden{{display:none}}
.page-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:1.2rem}}
.head-side{{display:flex;align-items:flex-start;gap:.8rem}}
.context-side{{display:flex;align-items:flex-start;gap:.8rem}}
.hardware-side{{display:flex;flex-direction:column;gap:.35rem}}
.tests-doc-link-line{{margin:.05rem 0 0 .1rem;font-size:.78rem}}
.legend{{border:1px solid #d7d1c3;background:#faf7ef;border-radius:8px;padding:.45rem .6rem;min-width:250px}}
.legend-title{{font-size:.75rem;font-weight:700;color:#444;margin-bottom:.28rem;text-transform:uppercase;letter-spacing:.02em}}
.legend-row{{display:flex;align-items:flex-start;gap:.45rem;font-size:.75rem;color:#444;line-height:1.35;margin:.12rem 0}}
.legend-row-text{{display:flex;flex-direction:column;gap:.1rem}}
.legend-sub{{font-size:.66rem;color:#666;line-height:1.25}}
.legend-swatch{{display:inline-block;width:12px;height:12px;border:1px solid #bdb7aa;border-radius:2px;flex:0 0 auto}}
.legend-pass{{background:#b9e8c2}}
.legend-mixed{{background:#fff0cc}}
.legend-soft{{background:#e8ddc7}}
.legend-behavioral{{background:#f6d5b2}}
.legend-error{{background:#f3b3b3}}
.legend-critical{{background:#e48686}}
.legend-metrics-title{{margin-top:.55rem}}
.legend-metric{{font-size:.68rem;color:#555;line-height:1.35;margin:.16rem 0}}
.hardware-summary{{border:1px solid #d7d1c3;background:#faf7ef;border-radius:8px;padding:.45rem .6rem;min-width:300px}}
.hardware-title{{font-size:.75rem;font-weight:700;color:#444;margin-bottom:.28rem;text-transform:uppercase;letter-spacing:.02em}}
.hw-warning{{font-size:.72rem;color:#855a00;margin:.2rem 0 .45rem 0}}
.hw-cards{{display:grid;gap:.45rem}}
.hw-card{{border:1px solid #ddd6c7;border-radius:6px;background:#fffdf7;padding:.35rem .45rem}}
.hw-card h4{{margin:.1rem 0 .28rem 0;font-size:.76rem}}
.hw-card table{{border-collapse:collapse;width:100%;font-size:.72rem}}
.hw-card th,.hw-card td{{text-align:left;padding:.08rem .2rem;border:none;vertical-align:top}}
.hw-card th{{color:#555;width:48px;font-weight:700}}
.hw-note{{font-size:.68rem;color:#666;margin:.25rem 0 0 0}}
.generated-at{{margin-top:1rem;color:#666;font-size:.84rem}}
.scope-summary,.models-summary{{border:1px solid #d7d1c3;background:#faf7ef;border-radius:8px;padding:.45rem .6rem;min-width:230px}}
.scope-title,.models-title{{font-size:.75rem;font-weight:700;color:#444;margin-bottom:.28rem;text-transform:uppercase;letter-spacing:.02em}}
.scope-summary table,.models-summary table{{border-collapse:collapse;width:100%;font-size:.72rem}}
.scope-summary th,.scope-summary td,.models-summary td{{text-align:left;padding:.08rem .2rem;border:none;vertical-align:top}}
.scope-summary th{{color:#555;width:54px;font-weight:700}}
.models-summary table{{display:block;max-height:180px;overflow:auto}}
.models-summary tr{{display:table;width:100%;table-layout:fixed}}
</style></head><body>
<div class='page-head'>
<div>
<h1>GripProbe Compatibility Report</h1>
</div>
<div class='head-side'>
<div class='context-side'>
{scope_summary_html}
<div class='hardware-side'>
{hardware_cards_html}
{tests_doc_link_html}
</div>
</div>
<aside class='legend'>
<div class='legend-title'>Failure Colors</div>
<div class='legend-row'><span class='legend-swatch legend-pass'></span><span class='legend-row-text'><span>PASS</span></span></div>
<div class='legend-row'><span class='legend-swatch legend-mixed'></span><span class='legend-row-text'><span>MIXED</span><span class='legend-sub'>Group has at least one PASS and at least one failure for the same test cell.</span></span></div>
<div class='legend-row'><span class='legend-swatch legend-soft'></span><span class='legend-row-text'><span>SOFT FAIL</span><span class='legend-sub'>Output shape/content mismatch after execution.</span></span></div>
<div class='legend-row'><span class='legend-swatch legend-behavioral'></span><span class='legend-row-text'><span>BEHAVIORAL FAIL</span><span class='legend-sub'>No tool call / tool unsupported / behavior-level policy mismatch.</span></span></div>
<div class='legend-row'><span class='legend-swatch legend-error'></span><span class='legend-row-text'><span>ERROR FAIL</span><span class='legend-sub'>Execution-level failure such as timeout.</span></span></div>
<div class='legend-row'><span class='legend-swatch legend-critical'></span><span class='legend-row-text'><span>CRITICAL FAIL</span><span class='legend-sub'>Harness or shell-level error, highest severity.</span></span></div>
<div class='legend-title legend-metrics-title'>Aggregate Metrics</div>
<div class='legend-metric'><strong>Score</strong>: normalized weighted pass ratio across visible tests (sanity tests use lower weight than non-sanity).</div>
<div class='legend-metric'><strong>Typical Time</strong>: median measured time across representative results in the row.</div>
<div class='legend-metric'><strong>Outliers</strong>: count of tests in the row where time is above baseline median × {OUTLIER_FACTOR:.1f}.</div>
</aside>
</div>
</div>
<div class='controls'>
<p class='meta'>One row per shell/model/hash/format group. Test cells link to a concrete case detail page. Group links open the source run summary.</p>
<label for='model-filter'>Model</label>
<select id='model-filter'>
{model_filter_options}
</select>
<label for='shell-filter'>Shell</label>
<select id='shell-filter'>
{shell_filter_options}
</select>
<input id='include-partial-runs' type='checkbox' />
<label for='include-partial-runs'>Show partial (sanity-only) runs in addition to extended test runs</label>
</div>
<table id='aggregate-table'>
<thead><tr>
<th>Shell<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('shell', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('shell', 'desc')">▼</button></span></th>
<th>Model<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('model', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('model', 'desc')">▼</button></span></th>
<th>Format<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('format', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('format', 'desc')">▼</button></span></th>
<th>Score<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('score', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('score', 'desc')">▼</button></span></th>
<th>Typical Time<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('typical', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('typical', 'desc')">▼</button></span></th>
<th>Outliers<span class='sort-controls'><button type='button' class='sort-btn' onclick="sortRows('outliers', 'asc')">▲</button><button type='button' class='sort-btn' onclick="sortRows('outliers', 'desc')">▼</button></span></th>
{header_tests}<th>Runs</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
<p class='generated-at'>generated at {escape(generated_at_value)} | git commit {escape(commit_sha)}</p>
<script>
function sortRows(key, direction) {{
  var tbody = document.querySelector("#aggregate-table tbody");
  if (!tbody) return;
  var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  rows.sort(function(a, b) {{
    if (key === "score" || key === "typical" || key === "outliers") {{
      var av = Number(a.getAttribute("data-" + key) || "0");
      var bv = Number(b.getAttribute("data-" + key) || "0");
      var cmpNum = av - bv;
      return direction === "asc" ? cmpNum : -cmpNum;
    }}
    var avs = String(a.getAttribute("data-" + key) || "").toLowerCase();
    var bvs = String(b.getAttribute("data-" + key) || "").toLowerCase();
    var cmp = avs.localeCompare(bvs, undefined, {{ numeric: true, sensitivity: "base" }});
    return direction === "asc" ? cmp : -cmp;
  }});
  rows.forEach(function(row) {{ tbody.appendChild(row); }});
  applyRowFilters();
}}

function applyRowFilters() {{
  var includePartialRuns = document.getElementById("include-partial-runs");
  var includePartial = Boolean(includePartialRuns && includePartialRuns.checked);
  var modelFilter = document.getElementById("model-filter");
  var selectedModel = String((modelFilter && modelFilter.value) || "all");
  var shellFilter = document.getElementById("shell-filter");
  var selectedShell = String((shellFilter && shellFilter.value) || "all");
  var rows = Array.prototype.slice.call(document.querySelectorAll("#aggregate-table tbody tr"));
  rows.forEach(function(row) {{
    var hasExtended = (row.getAttribute("data-extended") || "no") === "yes";
    var rowModel = String(row.getAttribute("data-model") || "");
    var modelMatches = selectedModel === "all" || rowModel === selectedModel;
    var rowShell = String(row.getAttribute("data-shell") || "");
    var shellMatches = selectedShell === "all" || rowShell === selectedShell;
    row.classList.toggle("row-hidden", (!includePartial && !hasExtended) || !shellMatches || !modelMatches);
  }});
}}

var includePartialRunsCheckbox = document.getElementById("include-partial-runs");
if (includePartialRunsCheckbox) {{
  includePartialRunsCheckbox.addEventListener("change", applyRowFilters);
}}
var shellFilterSelect = document.getElementById("shell-filter");
if (shellFilterSelect) {{
  shellFilterSelect.addEventListener("change", applyRowFilters);
}}
var modelFilterSelect = document.getElementById("model-filter");
if (modelFilterSelect) {{
  modelFilterSelect.addEventListener("change", applyRowFilters);
}}
applyRowFilters();
</script>
</body></html>"""
    (reports_dir / "summary.html").write_text(html, encoding="utf-8")


def aggregate_reports(run_dirs: list[Path], output_dir: Path, root: Path | None = None) -> tuple[Path, list[CaseResult]]:
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
            _sanitize_tree_text_files(aggregate_case_dir)
            aggregate_result = result.model_copy(
                update={
                    "case_id": aggregate_case_id,
                    "run_id": run_dir.name,
                    "metadata": {
                        **result.metadata,
                        "source_case_id": result.case_id,
                    },
                }
            )
            aggregate_result = _sanitize_case_result(aggregate_result)
            write_json(aggregate_case_dir / "case.json", aggregate_result.model_dump())
            aggregated_results.append(aggregate_result)

    resolved_root = root.resolve() if root is not None else None
    hardware_profile_map, default_hardware_profile_id = _load_hardware_profile_data(resolved_root)

    tests_doc_relpath: str | None = None
    hardware_profiles_relpath: str | None = None
    if resolved_root is not None:
        tests_doc_path = resolved_root / "docs" / "tests.md"
        if tests_doc_path.exists():
            tests_doc_relpath = os.path.relpath(tests_doc_path, reports_dir)
        hardware_profiles_path = resolved_root / "specs" / "hardware_profiles.yaml"
        if hardware_profiles_path.exists():
            hardware_profiles_relpath = os.path.relpath(hardware_profiles_path, reports_dir)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    shells = sorted({item.shell for item in aggregated_results})
    models = sorted({item.model.label for item in aggregated_results})
    formats = sorted({item.format for item in aggregated_results})
    hardware_profile_ids = sorted({_hardware_profile_id(item, default_hardware_profile_id) for item in aggregated_results})
    commit_sha = _git_commit_sha(resolved_root)

    _write_aggregate_markdown_summary(
        aggregated_results,
        reports_dir / "summary.md",
        generated_at=generated_at,
        commit_sha=commit_sha,
        shells=shells,
        models=models,
        formats=formats,
        hardware_profile_ids=hardware_profile_ids,
        hardware_profiles_relpath=hardware_profiles_relpath,
    )
    write_aggregate_html_summary(
        aggregated_results,
        output_dir,
        hardware_profile_map=hardware_profile_map,
        default_hardware_profile_id=default_hardware_profile_id,
        tests_doc_relpath=tests_doc_relpath,
        generated_at=generated_at,
        commit_sha=commit_sha,
        hardware_profiles_relpath=hardware_profiles_relpath,
    )
    write_json(
        output_dir / "aggregate_manifest.json",
        {
            "run_dirs": [_sanitize_report_text(str(path.resolve())) for path in run_dirs],
            "runs": [path.name for path in run_dirs],
            "cases": len(aggregated_results),
        },
    )
    return output_dir, aggregated_results
