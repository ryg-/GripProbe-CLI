from __future__ import annotations

import json
from pathlib import Path

from gripprobe.runner import run
from tests.conftest import ExplodingAdapter



def test_run_persists_harness_error(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: ExplodingAdapter(shell_spec))

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-harness-error",
    )

    assert len(results) == 1
    assert results[0].status == "HARNESS_ERROR"
    assert results[0].model.backend == "ollama"

    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    summary_md = (run_dir / "reports" / "summary.md").read_text(encoding="utf-8")

    assert case["status"] == "HARNESS_ERROR"
    assert case["invoked"] == "no"
    assert case["model"]["model_hash"] == "845dbda0ea48"
    assert case["metadata"]["error"] == "simulated adapter failure"
    assert "| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48 | markdown | Shell PWD | HARNESS_ERROR |" in summary_md
