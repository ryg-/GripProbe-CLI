from __future__ import annotations

import json
from pathlib import Path

from gripprobe.runner import run
from tests.conftest import FakeSuccessAdapter, FakeTimeoutAdapter, FakeTimeoutWithArtifactAdapter



def test_run_writes_case_and_manifest(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeSuccessAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr(
        "gripprobe.runner._collect_shell_runtime_metadata",
        lambda executable: {
            "shell_executable": executable,
            "shell_executable_path": f"/fake/bin/{executable}",
            "shell_version": "gptme vtest",
            "shell_version_exit_code": "0",
            "ollama_context_length": "32768",
        },
    )
    monkeypatch.setattr(
        "gripprobe.runner._collect_runtime_snapshot",
        lambda include_ollama=False: {
            "captured_at": "2026-04-21T12:49:21+02:00",
            "probes": {
                "loadavg": {"status": "ok", "command": "cat /proc/loadavg", "stdout": "1.00 2.00 3.00"},
                "ollama_ps": {"status": "ok", "command": "GET http://127.0.0.1:11434/api/ps", "stdout": "qwen3:8b 100%"},
            },
        },
    )

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-success",
        model_hash="845dbda0ea48",
        run_metadata={"venv": "/tmp/fake-venv"},
    )

    assert len(results) == 1
    assert results[0].status == "PASS"

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    summary_md = (run_dir / "reports" / "summary.md").read_text(encoding="utf-8")
    warmup_workspace = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "workspace-warmup"
    measured_workspace = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "workspace"

    assert manifest["backend"] == "ollama"
    assert manifest["model_hash"] == "845dbda0ea48"
    assert manifest["run_metadata"]["shell_executable"] == "gptme"
    assert manifest["run_metadata"]["shell_executable_path"] == "/fake/bin/gptme"
    assert manifest["run_metadata"]["shell_version"] == "gptme vtest"
    assert manifest["run_metadata"]["ollama_context_length"] == "32768"
    assert manifest["run_metadata"]["venv"] == "/tmp/fake-venv"
    assert manifest["run_metadata"]["runtime_snapshots"]["run_started"]["probes"]["ollama_ps"]["stdout"] == "qwen3:8b 100%"
    assert manifest["run_metadata"]["runtime_snapshots"]["run_finished"]["probes"]["loadavg"]["stdout"] == "1.00 2.00 3.00"
    assert case["status"] == "PASS"
    assert case["model"]["backend"] == "ollama"
    assert case["model"]["model_hash"] == "845dbda0ea48"
    assert case["metadata"]["shell_version"] == "gptme vtest"
    assert case["metadata"]["ollama_context_length"] == "32768"
    assert case["metadata"]["venv"] == "/tmp/fake-venv"
    assert case["metadata"]["runtime_snapshots"]["before"]["probes"]["ollama_ps"]["stdout"] == "qwen3:8b 100%"
    assert case["metadata"]["runtime_snapshots"]["after"]["probes"]["loadavg"]["stdout"] == "1.00 2.00 3.00"
    assert warmup_workspace.exists()
    assert measured_workspace.exists()
    assert warmup_workspace != measured_workspace
    assert "| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48 | markdown | Shell PWD | PASS |" in summary_md


def test_run_emits_progress_lines(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeSuccessAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr("gripprobe.runner._collect_shell_runtime_metadata", lambda executable: {})
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})

    lines: list[str] = []
    run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-progress",
        progress=lines.append,
    )

    assert len(lines) == 6
    assert "START shell=gptme model=local/qwen2.5:7b backend=ollama report=" in lines[0]
    assert "START model=local/qwen2.5:7b backend=ollama format=markdown" in lines[1]
    assert "START model=local/qwen2.5:7b backend=ollama format=markdown test=shell_pwd case=gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" in lines[2]
    assert "DONE model=local/qwen2.5:7b backend=ollama format=markdown test=shell_pwd case=gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd status=PASS" in lines[3]
    assert "DONE model=local/qwen2.5:7b backend=ollama format=markdown cases=1" in lines[4]
    assert "DONE shell=gptme model=local/qwen2.5:7b backend=ollama cases=1 report=" in lines[5]



def test_run_timeout_persists_timeout_case(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeTimeoutAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-timeout",
        model_hash="845dbda0ea48",
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
    assert case["metadata"]["artifact_reached_before_timeout"] is False
    assert "TIMEOUT" in summary_html
    assert "badge timeout" in summary_html
    assert "details</a>" in summary_html
    assert "Tool / Process Output" in detail_html


def test_run_timeout_with_artifact_marks_timeout_as_reached(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeTimeoutWithArtifactAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-timeout-artifact",
        model_hash="845dbda0ea48",
    )

    assert len(results) == 1
    assert results[0].status == "TIMEOUT"
    assert results[0].invoked == "yes"
    assert results[0].match_percent == 100

    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    summary_html = (run_dir / "reports" / "summary.html").read_text(encoding="utf-8")
    detail_html = (run_dir / "reports" / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd.html").read_text(encoding="utf-8")

    assert case["status"] == "TIMEOUT"
    assert case["metadata"]["artifact_reached_before_timeout"] is True
    assert case["match_percent"] == 100
    assert "artifact reached" in summary_html
    assert "artifact reached" in detail_html
    assert "expected workspace artifact was present before the harness timeout elapsed" in detail_html


def test_run_uses_unknown_model_hash_when_not_in_spec_or_cli(monkeypatch, specs_root: Path) -> None:
    monkeypatch.setattr("gripprobe.runner._adapter_for", lambda shell_spec: FakeSuccessAdapter(shell_spec))
    monkeypatch.setattr("gripprobe.runner._collect_shell_runtime_metadata", lambda executable: {})
    monkeypatch.setattr("gripprobe.runner._collect_runtime_snapshot", lambda include_ollama=False: {"captured_at": "now", "probes": {}})
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: None)

    run_dir, results = run(
        specs_root,
        shell_name="gptme",
        model_name="local/qwen2.5:7b",
        backend_name="ollama",
        tests_filter=["shell_pwd"],
        formats_filter=["markdown"],
        run_id="run-unknown-hash",
    )

    assert len(results) == 1
    assert results[0].model.model_hash == "unknown"

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    case_path = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__markdown__shell_pwd" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))

    assert manifest["model_hash"] == "unknown"
    assert case["model"]["model_hash"] == "unknown"
