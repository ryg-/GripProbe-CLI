from __future__ import annotations

import json
from pathlib import Path

from gripprobe.case_result import build_case_result
from gripprobe.runner import run


def test_run_force_proxy_mode_collects_proxy_for_ollama_backend(monkeypatch, specs_root: Path) -> None:
    proxy_artifacts: list[str] = []

    class _FakeProxy:
        def __init__(self, *, case_dir: Path, upstream_base_url: str, artifact_relpath: str) -> None:
            self.case_dir = case_dir
            self.base_url = "http://127.0.0.1:19080"
            self.upstream_base_url = upstream_base_url
            self.artifact_relpath = artifact_relpath

        def start(self) -> None:
            artifacts = self.case_dir / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            (self.case_dir / self.artifact_relpath).write_text("", encoding="utf-8")
            proxy_artifacts.append(self.artifact_relpath)

        def stop(self) -> None:
            return

    class _PhaseCommandAdapter:
        def __init__(self, shell_spec) -> None:
            self.shell_spec = shell_spec

        def run_command(self, case, args, env, stdout_path, stderr_path, workspace_dir=None):
            stdout_path.write_text(f"{stdout_path.name} ok\n", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return 0, 0.01, "start", "finish"

        def run_case(self, case, model_spec, test_spec):
            case.case_dir.mkdir(parents=True, exist_ok=True)
            (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
            self.run_command(
                case,
                ["warmup"],
                {},
                case.case_dir / "warmup.stdout",
                case.case_dir / "warmup.stderr",
                workspace_dir=case.warmup_workspace_dir,
            )
            self.run_command(
                case,
                ["measured"],
                {},
                case.case_dir / "measured.stdout",
                case.case_dir / "measured.stderr",
                workspace_dir=case.workspace_dir,
            )
            (case.case_dir / "expected.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")
            (case.case_dir / "observed.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")
            (case.workspace_dir / "pwd-output.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")
            return build_case_result(
                case=case,
                model_spec=model_spec,
                test_spec=test_spec,
                status="PASS",
                trajectory="clean",
                invoked="yes",
                match_percent=100,
                warmup_seconds=0.01,
                measured_seconds=0.02,
                metadata={"tool_format": case.tool_format},
            )

    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: _PhaseCommandAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr("gripprobe.runner._collect_shell_runtime_metadata", lambda executable: {})
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})
    monkeypatch.setattr(
        "gripprobe.runner._create_ollama_telemetry_proxy",
        lambda case_dir, upstream_base_url, artifact_relpath="artifacts/proxy.measured.http.jsonl": _FakeProxy(
            case_dir=case_dir,
            upstream_base_url=upstream_base_url,
            artifact_relpath=artifact_relpath,
        ),
    )

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-telemetry",
        telemetry_proxy_mode="force",
    )

    assert len(results) == 1
    assert results[0].status == "PASS_WITH_POLICY_VIOLATION"
    assert results[0].invoked == "no"
    assert results[0].match_percent == 100

    case_dir = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd"
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    metadata = case_payload["metadata"]

    assert metadata["telemetry_proxy_mode"] == "force"
    assert metadata["telemetry_proxy_status"] == "collected"
    assert metadata["telemetry_proxy_skip_reason"] is None
    assert metadata["event_capture_status"] == "collected"
    assert metadata["tool_event_verdict"] == "no_tool_event_observed"
    assert metadata["tool_event_verdict_reason"] == "structured_event_absent"
    assert metadata["verdict_source"] == "event_evaluator"
    assert metadata["strict_pass_score"] == 0.0
    assert metadata["overall_score"] == 0.8
    assert metadata["failure_reason"] == "no_tool_call_observed"
    assert metadata["telemetry_proxy_ollama_host"].startswith("http://127.0.0.1:")
    assert metadata["telemetry_proxy_openai_base_url"].endswith("/v1")
    assert metadata["telemetry_proxy_warmup_ollama_host"].startswith("http://127.0.0.1:")
    assert metadata["telemetry_proxy_warmup_openai_base_url"].endswith("/v1")
    assert metadata["telemetry_proxy_measured_ollama_host"].startswith("http://127.0.0.1:")
    assert metadata["telemetry_proxy_measured_openai_base_url"].endswith("/v1")
    assert metadata["telemetry_proxy_warmup_artifact_path"] == "artifacts/proxy.warmup.http.jsonl"
    assert metadata["telemetry_proxy_measured_artifact_path"] == "artifacts/proxy.measured.http.jsonl"
    assert metadata["telemetry_proxy_warmup_http_path"] == "artifacts/proxy.warmup.http.jsonl"
    assert metadata["telemetry_proxy_measured_http_path"] == "artifacts/proxy.measured.http.jsonl"
    assert metadata["telemetry_proxy_http_paths"] == {
        "warmup": "artifacts/proxy.warmup.http.jsonl",
        "measured": "artifacts/proxy.measured.http.jsonl",
    }
    assert metadata["telemetry_events_warmup_path"] == "artifacts/events.warmup.jsonl"
    assert metadata["telemetry_events_measured_path"] == "artifacts/events.measured.jsonl"
    assert metadata["telemetry_events_summary_path"] == "artifacts/events.summary.json"

    assert (case_dir / "artifacts" / "events.warmup.jsonl").exists()
    assert (case_dir / "artifacts" / "events.measured.jsonl").exists()
    assert (case_dir / "artifacts" / "events.summary.json").exists()
    assert (case_dir / "artifacts" / "proxy.warmup.http.jsonl").exists()
    assert (case_dir / "artifacts" / "proxy.measured.http.jsonl").exists()
    assert proxy_artifacts == ["artifacts/proxy.warmup.http.jsonl", "artifacts/proxy.measured.http.jsonl"]

    detail_html = (run_dir / "reports" / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd.html").read_text(
        encoding="utf-8"
    )
    assert "<h2>Telemetry</h2>" in detail_html
    assert "Telemetry Preview" in detail_html
    assert "Tool Event Verdict" in detail_html
    assert "Telemetry Artifacts" in detail_html
    assert "artifacts/events.warmup.jsonl" in detail_html
    assert "artifacts/events.measured.jsonl" in detail_html
    assert "artifacts/proxy.warmup.http.jsonl" in detail_html
    assert "artifacts/proxy.measured.http.jsonl" in detail_html
    assert "Open Interactive Viewer" in detail_html
    assert "gripprobeOpenTelemetryViewer" in detail_html
    assert "window.open('about:blank', '_blank')" in detail_html
