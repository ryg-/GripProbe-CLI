from __future__ import annotations

import json
from pathlib import Path

from gripprobe.aggregate import aggregate_reports


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
        "metadata": {},
    }
    (case_dir / "case.json").write_text(json.dumps(payload), encoding="utf-8")
    (case_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    (case_dir / "expected.txt").write_text("ok\n", encoding="utf-8")
    (case_dir / "observed.txt").write_text("ok\n", encoding="utf-8")
    (reports_cases_dir / f"{case_id}.html").write_text("<html>detail</html>", encoding="utf-8")
    (run_dir / "reports" / "summary.html").write_text("<html>summary</html>", encoding="utf-8")
    (run_dir / "reports" / "summary.md").write_text("# Summary\n", encoding="utf-8")


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

    assert case_a["case_id"] == "run-a__case-1"
    assert case_a["metadata"]["source_case_id"] == "case-1"
    assert case_b["case_id"] == "run-b__case-1"
    assert manifest["cases"] == 2
