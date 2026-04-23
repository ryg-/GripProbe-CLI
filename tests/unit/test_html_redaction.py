from __future__ import annotations

import json
from pathlib import Path

from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings
from gripprobe.reporters.html_report import write_html_summary


def test_html_detail_hides_shell_executable_path(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "run_metadata": {
                    "runtime_snapshots": {
                        "run_started": {
                            "captured_at": "2026-04-21T12:49:21+02:00",
                            "probes": {
                                "ollama_ps": {
                                    "status": "ok",
                                    "command": "GET http://127.0.0.1:11434/api/ps",
                                    "stdout": "qwen3:8b 100%",
                                }
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    case_dir = tmp_path / "cases" / "case-1"
    case_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "shell_executable_path": "$HOME/.local/bin/gptme",
                    "shell_version": "gptme v0.31.0",
                    "failure_reason": "answered without invoking tool",
                    "runtime_snapshots": {
                        "before": {
                            "captured_at": "2026-04-21T12:49:21+02:00",
                            "probes": {
                                "loadavg": {
                                    "status": "ok",
                                    "command": "cat /proc/loadavg",
                                    "stdout": "1.00 2.00 3.00",
                                }
                            },
                        }
                    },
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
        metadata={
            "warmup_command": "tool --warmup",
            "measured_command": "tool --measured",
        },
    )

    write_html_summary([result], reports_dir / "summary.html")

    detail_html = (reports_dir / "cases" / "case-1.html").read_text(encoding="utf-8")
    assert "$HOME/.local/bin/gptme" not in detail_html
    assert "[hidden in HTML]" in detail_html
    assert "Runtime Snapshots" in detail_html
    assert "cat /proc/loadavg" in detail_html
    assert "Trajectory Hints" in detail_html
    assert "Run Comparison" in detail_html
    assert "Shell Commands" in detail_html
    assert "tool --measured" in detail_html
    assert "Failure Reason:" in detail_html
    assert "answered without invoking tool" in detail_html
    assert "strongly_diverged" in detail_html
    summary_html = (reports_dir / "summary.html").read_text(encoding="utf-8")
    assert "<th>Reason</th>" in summary_html
    assert "<th>Command</th>" not in summary_html
    assert "GET http://127.0.0.1:11434/api/ps" in summary_html
    assert "qwen3:8b 100%" in summary_html
