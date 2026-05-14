from __future__ import annotations

import json
from pathlib import Path

from gripprobe.runner import run
from tests.conftest import FakeSuccessAdapter


def test_run_force_proxy_mode_collects_proxy_for_ollama_backend(monkeypatch, specs_root: Path) -> None:
    class _FakeProxy:
        artifact_relpath = "artifacts/proxy.http.jsonl"

        def __init__(self, *, case_dir: Path, upstream_base_url: str) -> None:
            self.case_dir = case_dir
            self.base_url = "http://127.0.0.1:19080"
            self.upstream_base_url = upstream_base_url

        def start(self) -> None:
            artifacts = self.case_dir / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "proxy.http.jsonl").write_text("", encoding="utf-8")

        def stop(self) -> None:
            return

    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeSuccessAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr("gripprobe.runner._collect_shell_runtime_metadata", lambda executable: {})
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})
    monkeypatch.setattr("gripprobe.runner._create_ollama_telemetry_proxy", lambda case_dir, upstream_base_url: _FakeProxy(case_dir=case_dir, upstream_base_url=upstream_base_url))

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
    assert results[0].status == "PASS"
    assert results[0].invoked == "yes"
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
    assert metadata["telemetry_proxy_ollama_host"].startswith("http://127.0.0.1:")
    assert metadata["telemetry_proxy_openai_base_url"].endswith("/v1")
    assert metadata["telemetry_proxy_artifact_path"] == "artifacts/proxy.http.jsonl"
    assert metadata["telemetry_proxy_http_path"] == "artifacts/proxy.http.jsonl"
    assert metadata["telemetry_events_warmup_path"] == "artifacts/events.warmup.jsonl"
    assert metadata["telemetry_events_measured_path"] == "artifacts/events.measured.jsonl"
    assert metadata["telemetry_events_summary_path"] == "artifacts/events.summary.json"

    assert (case_dir / "artifacts" / "events.warmup.jsonl").exists()
    assert (case_dir / "artifacts" / "events.measured.jsonl").exists()
    assert (case_dir / "artifacts" / "events.summary.json").exists()
    assert (case_dir / "artifacts" / "proxy.http.jsonl").exists()

    detail_html = (run_dir / "reports" / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd.html").read_text(
        encoding="utf-8"
    )
    assert "<h2>Telemetry</h2>" in detail_html
    assert "Tool Event Verdict" in detail_html
    assert "Telemetry Artifacts" in detail_html
    assert "artifacts/events.warmup.jsonl" in detail_html
    assert "artifacts/events.measured.jsonl" in detail_html
    assert "artifacts/proxy.http.jsonl" in detail_html
