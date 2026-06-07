from __future__ import annotations

import json
from pathlib import Path

from gripprobe.models import CaseLogs, CaseModelInfo, CaseResult, CaseTimings
from gripprobe.reporters.html_report import (
    _render_telemetry_viewer_script,
    write_case_detail_pages,
    write_html_summary,
)


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
                    "failure_reason": "answered without invoking tool at /home/source-user/work/private",
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
    (case_dir / "model.modelfile").write_text(
        "FROM qwen2.5:7b\nPARAMETER temperature 0.2\n",
        encoding="utf-8",
    )

    result = CaseResult(
        case_id="case-1",
        run_id="run-1",
        cli_agent_id="gptme",
        cli_agent="gptme",
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
            "warmup_command": "cat /home/source-user/work/private/task.txt",
            "measured_command": "tool --measured",
            "failure_reason": "summary reason path /home/source-user/work/private",
        },
    )

    write_html_summary([result], reports_dir / "summary.html")

    detail_html = (reports_dir / "cases" / "case-1.html").read_text(encoding="utf-8")
    assert "<html lang='en'>" in detail_html
    assert "$HOME/.local/bin/gptme" not in detail_html
    assert "[hidden in HTML]" in detail_html
    assert "Runtime Snapshots" in detail_html
    assert "cat /proc/loadavg" in detail_html
    assert "Trajectory Hints" in detail_html
    assert "Run Comparison" in detail_html
    assert "CLI Agent Commands" in detail_html
    assert "tool --measured" in detail_html
    assert "CLI Agent Version:" in detail_html
    assert "gptme unknown" in detail_html
    assert "Failure Reason:" in detail_html
    assert "answered without invoking tool" in detail_html
    assert "/home/source-user" not in detail_html
    assert "$HOME/work/private" in detail_html
    assert "strongly_diverged" in detail_html
    assert "Model Modelfile (Ollama)" in detail_html
    assert "FROM qwen2.5:7b" in detail_html
    assert detail_html.rfind("Model Modelfile (Ollama)") > detail_html.rfind("Raw Artifacts")
    assert ".timeout-artifact{" not in detail_html
    assert ".unsupported{" not in detail_html
    assert ".invoked-maybe{" not in detail_html
    assert ".match-none{" not in detail_html
    summary_html = (reports_dir / "summary.html").read_text(encoding="utf-8")
    assert "<html lang='en'>" in summary_html
    assert "<th>CLI Agent</th>" in summary_html
    assert "gptme unknown" in summary_html
    assert "<th>Reason</th>" in summary_html
    assert "<th>Command</th>" not in summary_html
    assert "/home/source-user" not in summary_html
    assert "$HOME/work/private" in summary_html
    assert "GET http://127.0.0.1:11434/api/ps" not in summary_html
    assert "GET http://ollama-host:11434/api/ps" in summary_html
    assert "qwen3:8b 100%" in summary_html


def test_html_summary_omits_unused_css_selectors(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)

    result = CaseResult(
        case_id="case-timeout",
        run_id="run-1",
        cli_agent_id="continue-cli",
        cli_agent="continue-cli",
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
        title="Timeout Case",
        status="TIMEOUT",
        trajectory="clean",
        invoked="no",
        match_percent=0,
        timings=CaseTimings(warmup_seconds=1.0, measured_seconds=2.0),
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
    summary_html = (reports_dir / "summary.html").read_text(encoding="utf-8")

    assert ".grid{" not in summary_html
    assert ".panel{" not in summary_html
    assert ".panel h3,.panel h4{" not in summary_html
    assert ".pass{" not in summary_html
    assert ".fail{" not in summary_html
    assert ".notool{" not in summary_html
    assert ".unsupported{" not in summary_html
    assert ".skipped{" not in summary_html
    assert ".traj-violated{" not in summary_html
    assert ".invoked-maybe{" not in summary_html
    assert ".match-partial{" not in summary_html

    assert ".badge{" in summary_html
    assert ".timeout{" in summary_html
    assert ".traj-clean{" in summary_html
    assert ".invoked-no{" in summary_html
    assert ".match-none{" in summary_html


def test_detail_uses_raw_case_json_override_for_metadata_blocks(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    cases_dir = tmp_path / "cases"
    reports_dir.mkdir(parents=True)
    (cases_dir / "case-1").mkdir(parents=True)

    result = CaseResult(
        case_id="case-1",
        run_id="run-1",
        cli_agent_id="gptme",
        cli_agent="gptme",
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
        status="FAIL",
        trajectory="recovered",
        invoked="yes",
        match_percent=0,
        timings=CaseTimings(warmup_seconds=0.1, measured_seconds=0.2),
        logs=CaseLogs(
            prompt="prompt.txt",
            warmup_stdout="warmup.stdout",
            warmup_stderr="warmup.stderr",
            measured_stdout="measured.stdout",
            measured_stderr="measured.stderr",
        ),
        metadata={"failure_reason": "from result metadata"},
    )

    raw_case_json = json.dumps(
        {
            "metadata": {
                "failure_reason": "from raw case json",
                "run_consistency": "strongly_diverged",
                "run_1_status": "PASS",
                "run_2_status": "FAIL",
                "trajectory_reasons": ["raw trajectory reason"],
            }
        }
    )

    write_case_detail_pages(
        [result],
        reports_dir,
        cases_dir,
        case_json_by_case_id={"case-1": raw_case_json},
        show_case_json=False,
    )

    detail_html = (reports_dir / "cases" / "case-1.html").read_text(encoding="utf-8")
    assert "Failure Reason:" in detail_html
    assert "from raw case json" in detail_html
    assert "from result metadata" not in detail_html
    assert "Run Comparison" in detail_html
    assert "strongly_diverged" in detail_html
    assert "Trajectory Hints" in detail_html
    assert "raw trajectory reason" in detail_html


def test_detail_telemetry_artifact_links_omitted_when_absent(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    cases_dir = tmp_path / "cases"
    case_dir = cases_dir / "case-telemetry"
    reports_dir.mkdir(parents=True)
    case_dir.mkdir(parents=True)

    result = CaseResult(
        case_id="case-telemetry",
        run_id="run-1",
        cli_agent_id="aider",
        cli_agent="aider",
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
        title="Telemetry Case",
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
    raw_case_json = json.dumps({"metadata": {"event_capture_status": "collected"}})
    write_case_detail_pages(
        [result],
        reports_dir,
        cases_dir,
        case_json_by_case_id={"case-telemetry": raw_case_json},
        show_case_json=False,
    )

    detail_html = (reports_dir / "cases" / "case-telemetry.html").read_text(encoding="utf-8")
    assert "<h2>Telemetry</h2>" in detail_html
    assert "Telemetry Preview" not in detail_html
    assert "Telemetry Artifacts" not in detail_html
    assert "artifacts/events.warmup.jsonl" not in detail_html
    assert "artifacts/events.measured.jsonl" not in detail_html
    assert "artifacts/proxy.warmup.http.jsonl" not in detail_html
    assert "artifacts/proxy.measured.http.jsonl" not in detail_html
    assert "Open Interactive Viewer" not in detail_html
    assert "gripprobeOpenTelemetryViewer" not in detail_html


def test_detail_telemetry_preview_truncation_and_viewer_markup(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    cases_dir = tmp_path / "cases"
    case_dir = cases_dir / "case-telemetry-preview"
    artifacts_dir = case_dir / "artifacts"
    reports_dir.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)

    warmup_lines = "\n".join(json.dumps({"entry": idx, "phase": "warmup"}) for idx in range(55))
    measured_lines = "\n".join(json.dumps({"entry": idx, "phase": "measured"}) for idx in range(2))
    proxy_lines = json.dumps(
        {
            "x_gripprobe_timestamp": "2026-05-14T18:58:15+00:00",
            "x_gripprobe_method": "POST",
            "x_gripprobe_path": "/api/show",
            "x_gripprobe_duration_ms": 549,
            "x_gripprobe_response_status": 200,
            "x_gripprobe_tool_call_count": 0,
            "x_gripprobe_tool_call_nonstructured_count": 1,
            "x_gripprobe_tool_result_count": 0,
        }
    )
    summary_payload = json.dumps({"phase": "measured", "ok": True})

    (artifacts_dir / "events.warmup.jsonl").write_text(warmup_lines + "\n", encoding="utf-8")
    (artifacts_dir / "events.measured.jsonl").write_text(measured_lines + "\n", encoding="utf-8")
    (artifacts_dir / "proxy.warmup.http.jsonl").write_text(proxy_lines + "\n", encoding="utf-8")
    (artifacts_dir / "proxy.measured.http.jsonl").write_text(proxy_lines + "\n", encoding="utf-8")
    (artifacts_dir / "events.summary.json").write_text(summary_payload, encoding="utf-8")

    result = CaseResult(
        case_id="case-telemetry-preview",
        run_id="run-1",
        cli_agent_id="aider",
        cli_agent="aider",
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
        title="Telemetry Preview Case",
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
    raw_case_json = json.dumps(
        {
            "metadata": {
                "event_capture_status": "collected",
                "telemetry_proxy_tool_call_nonstructured_count": 1,
            }
        }
    )
    write_case_detail_pages(
        [result],
        reports_dir,
        cases_dir,
        case_json_by_case_id={"case-telemetry-preview": raw_case_json},
        show_case_json=False,
    )

    detail_html = (reports_dir / "cases" / "case-telemetry-preview.html").read_text(encoding="utf-8")
    assert "<h2>Telemetry</h2>" in detail_html
    assert "Telemetry Preview" in detail_html
    assert "events.summary.json" in detail_html
    assert "&quot;phase&quot;: &quot;measured&quot;" in detail_html
    assert "&quot;ok&quot;: true" in detail_html
    assert "&quot;method&quot;: &quot;POST&quot;" in detail_html
    assert "&quot;path&quot;: &quot;/api/show&quot;" in detail_html
    assert "&quot;response_status&quot;: 200" in detail_html
    assert "&quot;tool_call_nonstructured_count&quot;: 1" in detail_html
    assert "Proxy Non-Structured Tool Calls" in detail_html
    assert "artifacts/events.warmup.jsonl" in detail_html
    assert "artifacts/proxy.warmup.http.jsonl" in detail_html
    assert "artifacts/proxy.measured.http.jsonl" in detail_html
    assert "Showing first 50 of 55 line(s)." in detail_html
    assert "Open Interactive Viewer" in detail_html
    assert "gripprobeOpenTelemetryViewer" in detail_html
    assert "window.open('about:blank', '_blank')" in detail_html
    assert "viewer v5" in detail_html
    assert "function normalizeBodyExcerpt" in detail_html
    assert "function formatViewerValue" in detail_html
    assert "function classifyViewerEntry" in detail_html
    assert "function renderJsonlRows" in detail_html
    assert "function extractToolCallIds" in detail_html
    assert "function summarizeRow" in detail_html


def test_telemetry_viewer_parses_body_excerpt_before_decoding_escapes() -> None:
    script = _render_telemetry_viewer_script()
    normalize_start = script.index("function normalizeBodyExcerpt(value)")
    normalize_end = script.index("function normalizeForView(node)")
    normalize_body = script[normalize_start:normalize_end]

    raw_json_parse = normalize_body.index("var parsed=tryParseJsonString(value);")
    raw_sse_parse = normalize_body.index("var sseParsed=tryParseSseStream(value);")
    escaped_decode = normalize_body.index("var decoded=decodeEscapedExcerpt(value);")
    decoded_json_parse = normalize_body.index("parsed=tryParseJsonString(decoded);")
    decoded_sse_parse = normalize_body.index("sseParsed=tryParseSseStream(decoded);")

    assert raw_json_parse < escaped_decode
    assert raw_sse_parse < escaped_decode
    assert escaped_decode < decoded_json_parse
    assert escaped_decode < decoded_sse_parse


def test_transcript_role_and_tool_markdown_highlighting(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    cases_dir = tmp_path / "cases"
    case_dir = cases_dir / "case-transcript-highlight"
    reports_dir.mkdir(parents=True)
    case_dir.mkdir(parents=True)

    conversation = [
        {"role": "user", "content": "Please list files"},
        {"role": "assistant", "content": "```tool\n{\"tool_call\":\"ls\"}\n```"},
        {"role": "tool", "content": "{\"ok\": true}"},
    ]
    (case_dir / "conversation.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in conversation) + "\n",
        encoding="utf-8",
    )

    result = CaseResult(
        case_id="case-transcript-highlight",
        run_id="run-1",
        cli_agent_id="aider",
        cli_agent="aider",
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
        title="Transcript Highlight Case",
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

    write_case_detail_pages([result], reports_dir, cases_dir, show_case_json=False)
    detail_html = (reports_dir / "cases" / "case-transcript-highlight.html").read_text(encoding="utf-8")

    assert "class='message msg-user'" in detail_html
    assert "class='message msg-llm msg-tool-md'" in detail_html
    assert "class='message msg-tool'" in detail_html
    assert ".message.msg-user{" in detail_html
    assert ".message.msg-llm{" in detail_html
    assert ".message.msg-tool{" in detail_html
    assert ".message.msg-tool-md{" in detail_html
