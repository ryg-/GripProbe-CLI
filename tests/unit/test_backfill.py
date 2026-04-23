from __future__ import annotations

import json
from pathlib import Path

from gripprobe.backfill import backfill_model_hashes_for_run


def test_backfill_model_hashes_updates_run_manifest_and_cases(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "results" / "runs" / "run-a"
    case_dir = run_dir / "cases" / "gptme__local_qwen2_5_7b__ollama__tool__shell_pwd"
    case_dir.mkdir(parents=True)

    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-a",
                "shell": "gptme",
                "model": "local_qwen2_5_7b",
                "backend": "ollama",
                "model_hash": "unknown",
                "run_metadata": {},
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "case_id": "gptme__local_qwen2_5_7b__ollama__tool__shell_pwd",
                "run_id": "run-a",
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
                    "model_hash": "unknown",
                },
                "format": "tool",
                "test": "shell_pwd",
                "title": "Shell PWD",
                "status": "PASS",
                "trajectory": "clean",
                "invoked": "yes",
                "match_percent": 100,
                "timings": {"warmup_seconds": 1.0, "measured_seconds": 1.0},
                "logs": {
                    "prompt": "prompt.txt",
                    "warmup_stdout": "warmup.stdout",
                    "warmup_stderr": "warmup.stderr",
                    "measured_stdout": "measured.stdout",
                    "measured_stderr": "measured.stderr",
                },
                "metadata": {
                    "model_hash": "unknown",
                },
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "gripprobe.backfill._fetch_ollama_model_digest",
        lambda model_id: "845dbda0ea48" if model_id == "qwen2.5:7b" else None,
    )

    stats = backfill_model_hashes_for_run(run_dir)

    assert stats == {
        "runs": 1,
        "case_updates": 1,
        "manifest_updates": 1,
    }

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))

    assert manifest["model_hash"] == "845dbda0ea48"
    assert case_payload["model"]["model_hash"] == "845dbda0ea48"
    assert case_payload["metadata"]["model_hash"] == "845dbda0ea48"


def test_backfill_model_hashes_skips_when_digest_is_missing(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "results" / "runs" / "run-b"
    case_dir = run_dir / "cases" / "gptme__local_qwen3_8b__ollama__tool__shell_pwd"
    case_dir.mkdir(parents=True)

    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-b",
                "shell": "gptme",
                "model": "local_qwen3_8b",
                "backend": "ollama",
                "model_hash": "unknown",
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "case_id": "gptme__local_qwen3_8b__ollama__tool__shell_pwd",
                "run_id": "run-b",
                "shell": "gptme",
                "model": {
                    "backend": "ollama",
                    "model_id": "qwen3:8b",
                    "model_hash": "unknown",
                },
                "metadata": {},
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("gripprobe.backfill._fetch_ollama_model_digest", lambda model_id: None)

    stats = backfill_model_hashes_for_run(run_dir)

    assert stats == {
        "runs": 1,
        "case_updates": 0,
        "manifest_updates": 0,
    }
