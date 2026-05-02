from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from gripprobe.aggregate import aggregate_reports, discover_run_dirs
from gripprobe.cli import build_parser


def _write_case(run_dir: Path, case_id: str, title: str, status: str) -> None:
    case_dir = run_dir / "cases" / case_id
    reports_cases_dir = run_dir / "reports" / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    reports_cases_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "run_id": run_dir.name,
        "shell": "gptme",
        "model": {
            "id": "local_qwen2_5_7b",
            "label": "local/qwen2.5:7b",
            "family": "qwen",
            "size_class": "small",
            "quantization": None,
            "backend": "ollama",
            "model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "845dbda0ea48",
        },
        "format": "markdown",
        "test": title.lower().replace(" ", "_"),
        "title": title,
        "status": status,
        "trajectory": "clean",
        "invoked": "yes",
        "match_percent": 100,
        "timings": {"warmup_seconds": 1.0, "measured_seconds": 2.0},
        "logs": {
            "prompt": "prompt.txt",
            "warmup_stdout": "warmup.stdout",
            "warmup_stderr": "warmup.stderr",
            "measured_stdout": "measured.stdout",
            "measured_stderr": "measured.stderr",
        },
        "metadata": {
            "test_tags": ["sanity"] if title == "Case One" else [],
        },
    }
    (case_dir / "case.json").write_text(json.dumps(payload), encoding="utf-8")
    (case_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    (case_dir / "expected.txt").write_text("ok\n", encoding="utf-8")
    (case_dir / "observed.txt").write_text("ok\n", encoding="utf-8")
    (reports_cases_dir / f"{case_id}.html").write_text("<html>detail</html>", encoding="utf-8")
    (run_dir / "reports" / "summary.html").write_text("<html>summary</html>", encoding="utf-8")
    (run_dir / "reports" / "summary.md").write_text("# Summary\n", encoding="utf-8")


def _tbody_row_count(summary_html: str) -> int:
    match = re.search(r"<tbody>(.*?)</tbody>", summary_html, flags=re.DOTALL)
    if not match:
        return 0
    return match.group(1).count("<tr")


def test_aggregate_reports_builds_combined_output(tmp_path: Path) -> None:
    run_a = tmp_path / "runs" / "run-a"
    run_b = tmp_path / "runs" / "run-b"
    _write_case(run_a, "case-1", "Case One", "PASS")
    _write_case(run_b, "case-1", "Case Two", "FAIL")

    output_dir, results = aggregate_reports([run_a, run_b], tmp_path / "aggregate")

    assert output_dir == (tmp_path / "aggregate").resolve()
    assert len(results) == 2
    assert (output_dir / "reports" / "summary.html").exists()
    assert (output_dir / "reports" / "summary.md").exists()
    assert (output_dir / "source_reports" / "run-a" / "summary.html").exists()
    assert (output_dir / "source_reports" / "run-b" / "cases" / "case-1.html").exists()
    assert (output_dir / "cases" / "run-a__case-1" / "case.json").exists()
    assert (output_dir / "cases" / "run-b__case-1" / "case.json").exists()

    case_a = json.loads((output_dir / "cases" / "run-a__case-1" / "case.json").read_text(encoding="utf-8"))
    case_b = json.loads((output_dir / "cases" / "run-b__case-1" / "case.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "aggregate_manifest.json").read_text(encoding="utf-8"))
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")
    summary_md = (output_dir / "reports" / "summary.md").read_text(encoding="utf-8")

    assert case_a["case_id"] == "run-a__case-1"
    assert case_a["metadata"]["source_case_id"] == "case-1"
    assert case_b["case_id"] == "run-b__case-1"
    assert manifest["cases"] == 2
    assert _tbody_row_count(summary_html) == 1
    assert "source_reports/run-b/summary.html" in summary_html
    assert "cases/case-00001.html" in summary_html
    assert "Case One" in summary_html
    assert "Case Two" in summary_html
    assert "model-meta" in summary_html
    assert "845dbda" in summary_html
    assert "845dbda0ea48" not in summary_html
    assert "GripProbe Compatibility Report" in summary_html
    assert "Failure Colors" in summary_html
    assert "Aggregate Metrics" in summary_html
    assert "Scope" in summary_html
    assert "Hardware Profiles" in summary_html
    assert "Methodology" not in summary_html
    assert "Status codes:" not in summary_html
    assert "Resume behavior:" not in summary_html
    assert "id='model-filter'" in summary_html
    assert "<label for='model-filter'>Model</label>" in summary_html
    assert "Suite id:" not in summary_html
    assert "Test tags:" not in summary_html
    assert "<strong>Score</strong>" in summary_html
    assert "<strong>Typical Time</strong>" in summary_html
    assert "<strong>Outliers</strong>" in summary_html
    assert "generated at " in summary_html
    assert "git commit " in summary_html
    assert "<td class='agg-fail-soft'" in summary_html
    assert "# GripProbe Compatibility Report" in summary_md
    assert "## Reproducibility" in summary_md
    assert "## Methodology" not in summary_md
    assert "- Suite id:" not in summary_md
    assert "- Test tags in report:" not in summary_md
    assert "Resume behavior:" not in summary_md


def test_discover_run_dirs_finds_case_directories(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_a = runs_root / "run-a"
    run_b = runs_root / "run-b"
    ignored = runs_root / "not-a-run"
    _write_case(run_a, "case-1", "Case One", "PASS")
    _write_case(run_b, "case-2", "Case Two", "FAIL")
    ignored.mkdir(parents=True, exist_ok=True)

    discovered = discover_run_dirs(runs_root)

    assert discovered == [run_a.resolve(), run_b.resolve()]


def test_discover_run_dirs_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Runs root does not exist"):
        discover_run_dirs(tmp_path / "missing")


def test_aggregate_reports_cli_accepts_runs_root(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    run_a = runs_root / "run-a"
    run_b = runs_root / "run-b"
    _write_case(run_a, "case-1", "Case One", "PASS")
    _write_case(run_b, "case-1", "Case Two", "FAIL")

    parser = build_parser()
    ns = parser.parse_args(
        [
            "aggregate-reports",
            "--runs-root",
            str(runs_root),
            "--output-dir",
            str(tmp_path / "aggregate"),
        ]
    )

    assert ns.cmd == "aggregate-reports"
    assert ns.runs_root == str(runs_root)
    assert ns.run_dirs is None


def test_aggregate_reports_formats_run_time_and_pass_cell_time(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "20260420T202823Z"
    _write_case(run_dir, "case-1", "Case One", "PASS")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "2026-04-20 20:28" in summary_html
    assert "2026-04-20 20:28 UTC" not in summary_html
    assert "<span class='cell-time'>2.0s</span>" in summary_html


def test_aggregate_reports_places_sanity_tests_first(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    _write_case(run_dir, "case-2", "Case Two", "PASS")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert summary_html.index("<th>Case One</th>") < summary_html.index("<th>Case Two</th>")


def test_aggregate_reports_keeps_different_formats_on_separate_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    payload = json.loads((run_dir / "cases" / "case-1" / "case.json").read_text(encoding="utf-8"))
    payload["case_id"] = "case-2"
    payload["format"] = "tool"
    payload["title"] = "Case Two"
    payload["test"] = "case_two"
    case_dir = run_dir / "cases" / "case-2"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps(payload), encoding="utf-8")
    (case_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    (case_dir / "expected.txt").write_text("ok\n", encoding="utf-8")
    (case_dir / "observed.txt").write_text("ok\n", encoding="utf-8")
    reports_cases_dir = run_dir / "reports" / "cases"
    reports_cases_dir.mkdir(parents=True, exist_ok=True)
    (reports_cases_dir / "case-2.html").write_text("<html>detail</html>", encoding="utf-8")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "<th>Format<span class='sort-controls'>" in summary_html
    assert "<th>Score<span class='sort-controls'>" in summary_html
    assert "<th>Typical Time<span class='sort-controls'>" in summary_html
    assert "<th>Outliers<span class='sort-controls'>" in summary_html
    assert summary_html.index("<th>Runs</th>") > summary_html.index("<th>Case Two</th>")
    assert "class='runs-meta'" in summary_html
    assert "<th>Backend</th>" not in summary_html
    assert "<th>Hash</th>" not in summary_html
    assert _tbody_row_count(summary_html) == 2
    assert ">markdown</td>" in summary_html
    assert ">tool</td>" in summary_html


def test_aggregate_reports_sanitizes_source_report_private_values(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    source_case_html = run_dir / "reports" / "cases" / "case-1.html"
    source_case_html.write_text(
        "<html><body>"
        "GET http://source-host:11434/api/ps "
        "ssh source-host cat /proc/loadavg "
        f"{Path.home()}/work/private "
        "/home/source-user/work/private "
        "/Users/source-user/work/private"
        "</body></html>",
        encoding="utf-8",
    )

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    copied_html = (output_dir / "source_reports" / "run-a" / "cases" / "case-1.html").read_text(encoding="utf-8")

    assert "http://source-host:11434" not in copied_html
    assert "ssh source-host " not in copied_html
    assert str(Path.home()) not in copied_html
    assert "/home/source-user" not in copied_html
    assert "/Users/source-user" not in copied_html
    assert "http://ollama-host:11434" in copied_html
    assert "ssh ollama-host" in copied_html
    assert "$HOME/work/private" in copied_html


def test_aggregate_reports_sanitizes_case_artifacts_and_detail_pages(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "FAIL")
    case_dir = run_dir / "cases" / "case-1"
    (case_dir / "expected.txt").write_text(
        "/home/source-user/work/private\n/Users/source-user/work/private\n",
        encoding="utf-8",
    )
    (case_dir / "observed.txt").write_text("mismatch\n", encoding="utf-8")
    (case_dir / "measured.stdout").write_text(
        "trace: /home/source-user/work/private\n",
        encoding="utf-8",
    )

    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    case_payload["metadata"]["failure_reason"] = "path leak at /home/source-user/work/private and /Users/source-user/work/private"
    (case_dir / "case.json").write_text(json.dumps(case_payload), encoding="utf-8")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    detail_html = (output_dir / "reports" / "cases" / "case-00001.html").read_text(encoding="utf-8")
    aggregate_case_json = (output_dir / "cases" / "run-a__case-1" / "case.json").read_text(encoding="utf-8")

    assert "/home/source-user" not in detail_html
    assert "/Users/source-user" not in detail_html
    assert "$HOME/work/private" in detail_html
    assert "/home/source-user" not in aggregate_case_json
    assert "/Users/source-user" not in aggregate_case_json


def test_aggregate_reports_ignores_dangling_symlink_in_case_dir(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink unsupported on this platform")

    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    broken_link = run_dir / "cases" / "case-1" / "gptme-logs" / "missing-workspace"
    broken_link.parent.mkdir(parents=True, exist_ok=True)
    broken_link.symlink_to(run_dir / "cases" / "case-1" / "does-not-exist")

    output_dir, results = aggregate_reports([run_dir], tmp_path / "aggregate")

    assert len(results) == 1
    assert (output_dir / "cases" / "run-a__case-1" / "case.json").exists()


def test_aggregate_reports_marks_and_filters_extended_rows(tmp_path: Path) -> None:
    run_a = tmp_path / "runs" / "run-a"
    run_b = tmp_path / "runs" / "run-b"
    _write_case(run_a, "case-1", "Case One", "PASS")
    _write_case(run_b, "case-1", "Case Two", "PASS")

    case_b_path = run_b / "cases" / "case-1" / "case.json"
    case_b = json.loads(case_b_path.read_text(encoding="utf-8"))
    case_b["format"] = "tool"
    case_b["metadata"]["test_tags"] = ["non_sanity"]
    case_b_path.write_text(json.dumps(case_b), encoding="utf-8")

    output_dir, _ = aggregate_reports([run_a, run_b], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "include-partial-runs" in summary_html
    assert "id='model-filter'" in summary_html
    assert "<option value='all'>all</option>" in summary_html
    assert "id='shell-filter'" in summary_html
    assert "<option value='all'>all</option>" in summary_html
    assert "modelFilterSelect.addEventListener(\"change\", applyRowFilters);" in summary_html
    assert "shellFilterSelect.addEventListener(\"change\", applyRowFilters);" in summary_html
    assert "Show partial (sanity-only) runs in addition to extended test runs" in summary_html
    assert "id='include-partial-runs' type='checkbox'" in summary_html
    assert "<table id='aggregate-table'>" in summary_html
    assert 'document.querySelector("#aggregate-table tbody")' in summary_html
    assert 'document.querySelectorAll("#aggregate-table tbody tr")' in summary_html
    assert "?.addEventListener" not in summary_html
    assert "onclick=\"sortRows(" in summary_html
    assert "data-sort-key='shell'" not in summary_html
    assert "<script src='summary.js'></script>" not in summary_html
    assert "data-extended='yes'" in summary_html
    assert "data-extended='no'" in summary_html


def test_aggregate_reports_computes_weighted_score_typical_time_and_outliers(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    _write_case(run_dir, "case-2", "Case Two", "FAIL")

    case_2_path = run_dir / "cases" / "case-2" / "case.json"
    case_2 = json.loads(case_2_path.read_text(encoding="utf-8"))
    case_2["timings"]["measured_seconds"] = 4.0
    case_2_path.write_text(json.dumps(case_2), encoding="utf-8")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "data-score='0.4444'" in summary_html
    assert ">44.4%</td>" in summary_html
    assert "data-typical='3.0000'" in summary_html
    assert ">3.0s</td>" in summary_html
    assert "data-outliers='0.0000'" in summary_html
    assert ">0/2</td>" in summary_html


def test_aggregate_reports_counts_outliers_by_test_baseline(tmp_path: Path) -> None:
    run_a = tmp_path / "runs" / "run-a"
    run_b = tmp_path / "runs" / "run-b"
    run_c = tmp_path / "runs" / "run-c"
    for run_dir in (run_a, run_b, run_c):
        _write_case(run_dir, "case-1", "Case One", "PASS")
        _write_case(run_dir, "case-2", "Case Two", "PASS")

    for run_dir, shell in ((run_a, "gptme"), (run_b, "continue-cli"), (run_c, "opencode")):
        for case_id in ("case-1", "case-2"):
            path = run_dir / "cases" / case_id / "case.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["shell"] = shell
            if run_dir == run_c and case_id == "case-1":
                payload["timings"]["measured_seconds"] = 10.0
            else:
                payload["timings"]["measured_seconds"] = 2.0
            path.write_text(json.dumps(payload), encoding="utf-8")

    output_dir, _ = aggregate_reports([run_a, run_b, run_c], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "data-shell='opencode'" in summary_html
    assert "data-outliers='0.5000'" in summary_html
    assert ">1/2</td>" in summary_html


def test_aggregate_reports_renders_hardware_profile_cards_from_yaml(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")
    case_path = run_dir / "cases" / "case-1" / "case.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["metadata"]["hardware_profile_id"] = "benchmark_a100"
    case_path.write_text(json.dumps(payload), encoding="utf-8")

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "hardware_profiles.yaml").write_text(
        "profiles:\n"
        "  - id: benchmark_a100\n"
        "    label: Benchmark A100\n"
        "    cpu: AMD EPYC 7F52\n"
        "    gpu: NVIDIA A100 80GB\n"
        "    ram: 512GB\n"
        "    notes: Dedicated benchmark host\n",
        encoding="utf-8",
    )

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate", root=tmp_path)
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "Hardware Profiles" in summary_html
    assert "benchmark_a100" in summary_html
    assert "AMD EPYC 7F52" in summary_html
    assert "NVIDIA A100 80GB" in summary_html
    assert "512GB" in summary_html
    assert "Dedicated benchmark host" in summary_html


def test_aggregate_reports_uses_default_profile_id_from_profiles_yaml(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "PASS")

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "hardware_profiles.yaml").write_text(
        "profiles:\n"
        "  - id: default1\n"
        "    label: Default\n"
        "    cpu: CPU-A\n"
        "    gpu: GPU-A\n"
        "    ram: 64GB\n"
        "  - id: lab_b\n"
        "    label: Lab B\n"
        "    cpu: CPU-B\n"
        "    gpu: GPU-B\n"
        "    ram: 128GB\n",
        encoding="utf-8",
    )

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate", root=tmp_path)
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "data-hw='default1'" in summary_html
    assert "<span class='hw-meta'>default1</span>" not in summary_html
    assert "default1" in summary_html


def test_aggregate_reports_shows_hw_meta_only_when_multiple_profiles_present(tmp_path: Path) -> None:
    run_a = tmp_path / "runs" / "run-a"
    run_b = tmp_path / "runs" / "run-b"
    _write_case(run_a, "case-1", "Case One", "PASS")
    _write_case(run_b, "case-1", "Case Two", "PASS")

    case_b_path = run_b / "cases" / "case-1" / "case.json"
    payload_b = json.loads(case_b_path.read_text(encoding="utf-8"))
    payload_b["metadata"]["hardware_profile_id"] = "lab_b"
    case_b_path.write_text(json.dumps(payload_b), encoding="utf-8")

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "hardware_profiles.yaml").write_text(
        "profiles:\n"
        "  - id: default1\n"
        "    label: Default\n"
        "    cpu: CPU-A\n"
        "    gpu: GPU-A\n"
        "    ram: 64GB\n"
        "  - id: lab_b\n"
        "    label: Lab B\n"
        "    cpu: CPU-B\n"
        "    gpu: GPU-B\n"
        "    ram: 128GB\n",
        encoding="utf-8",
    )

    output_dir, _ = aggregate_reports([run_a, run_b], tmp_path / "aggregate", root=tmp_path)
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "data-hw='default1'" in summary_html
    assert "data-hw='lab_b'" in summary_html
    assert "<span class='hw-meta'>default1</span>" in summary_html
    assert "<span class='hw-meta'>lab_b</span>" in summary_html


def test_aggregate_reports_uses_backend_free_case_detail_links_and_reason_text(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "run-a"
    _write_case(run_dir, "case-1", "Case One", "TOOL_UNSUPPORTED")
    case_path = run_dir / "cases" / "case-1" / "case.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["metadata"]["failure_reason"] = "tool unsupported by backend"
    case_path.write_text(json.dumps(payload), encoding="utf-8")

    output_dir, _ = aggregate_reports([run_dir], tmp_path / "aggregate")
    summary_html = (output_dir / "reports" / "summary.html").read_text(encoding="utf-8")

    assert "__ollama__" not in summary_html
    assert "tool unsupported by backend" not in summary_html
    assert "reason=tool unsupported" in summary_html
