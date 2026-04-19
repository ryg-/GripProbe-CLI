from __future__ import annotations

import json
from pathlib import Path

from gripprobe.runner import run
from tests.conftest import FakeSuccessAdapter, FakeTimeoutAdapter



def test_run_writes_case_and_manifest(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeSuccessAdapter(shell_spec))

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-success",
    )

    assert len(results) == 1
    assert results[0].status == "PASS"

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    summary_md = (run_dir / "reports" / "summary.md").read_text(encoding="utf-8")

    assert manifest["backend"] == "ollama"
    assert manifest["model_hash"] == "845dbda0ea48"
    assert case["status"] == "PASS"
    assert case["model"]["backend"] == "ollama"
    assert case["model"]["model_hash"] == "845dbda0ea48"
    assert "| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48 | markdown | Shell PWD | PASS |" in summary_md



def test_run_timeout_persists_timeout_case(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeTimeoutAdapter(shell_spec))

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-timeout",
    )

    assert len(results) == 1
    assert results[0].status == "TIMEOUT"

    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    summary_html = (run_dir / "reports" / "summary.html").read_text(encoding="utf-8")
    detail_html = (run_dir / "reports" / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd.html").read_text(encoding="utf-8")

    assert case["status"] == "TIMEOUT"
    assert case["invoked"] == "no"
    assert case["metadata"]["measured_exit_code"] == 124
    assert "TIMEOUT" in summary_html
    assert "badge timeout" in summary_html
    assert "details</a>" in summary_html
    assert "Tool / Process Output" in detail_html
