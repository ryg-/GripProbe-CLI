from __future__ import annotations

import json
from pathlib import Path

from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings
from gripprobe.reporters.html_report import write_html_summary


def test_html_detail_hides_shell_executable_path(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    case_dir = tmp_path / "cases" / "case-1"
    case_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "shell_executable_path": "$HOME/.local/bin/gptme",
                    "shell_version": "gptme v0.31.0",
                    "run_consistency": "strongly_diverged",
                    "run_1_status": "NO_TOOL_CALL",
                    "run_2_status": "TIMEOUT",
                    "run_1_profile": {"invoked": "maybe", "tool_attempt_count": 0},
                    "run_2_profile": {"invoked": "yes", "tool_attempt_count": 5, "loop_detected": True},
                    "trajectory_reasons": ["contradictory completion text detected (both DONE and FAIL)"],
                }
            }
        ),
        encoding="utf-8",
    )

    result = CaseResult(
        case_id="case-1",
        run_id="run-1",
        shell="gptme",
        model=CaseModelInfo(
            id="m",
            label="m",
            family="fam",
            size_class="small",
            quantization=None,
            backend="ollama",
            model_id="mid",
            shell_model_id="smid",
            model_hash="hash",
        ),
        format="tool",
        test="t",
        title="Title",
        status="PASS",
        trajectory="clean",
        invoked="yes",
        match_percent=100,
        timings=CaseTimings(warmup_seconds=0.1, measured_seconds=0.2),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={},
    )

    write_html_summary([result], reports_dir / "summary.html")

    detail_html = (reports_dir / "cases" / "case-1.html").read_text(encoding="utf-8")
    assert "$HOME/.local/bin/gptme" not in detail_html
    assert "[hidden in HTML]" in detail_html
    assert "Trajectory Hints" in detail_html
    assert "Run Comparison" in detail_html
    assert "strongly_diverged" in detail_html
