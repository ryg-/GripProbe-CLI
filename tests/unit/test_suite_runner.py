from __future__ import annotations

import json
from pathlib import Path

from gripprobe.suite_runner import run_suite


def test_run_suite_runs_all_shells_by_default(monkeypatch, specs_root: Path) -> None:
    calls: list[tuple[str, str, str | None, tuple[str, ...] | None]] = []

    def _fake_run(
        root,
        shell_name,
        model_name,
        backend_name,
        run_id=None,
        tests_filter=None,
        test_tags_filter=None,
        formats_filter=None,
        container_image=None,
        keep_system_messages=False,
        model_hash=None,
        run_metadata=None,
        progress=None,
    ):
        calls.append(
            (
                shell_name,
                model_name,
                run_id,
                tuple(formats_filter or ()),
            )
        )
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="default_cli_matrix",
        models=["local/qwen2.5:7b"],
        shells=None,
    )

    assert len(run_dirs) == 4
    assert {shell for shell, _, _, _ in calls} == {"aider", "continue-cli", "gptme", "opencode"}
    assert all(model == "local/qwen2.5:7b" for _, model, _, _ in calls)
    assert all(formats == ("tool",) for _, _, _, formats in calls)


def test_run_suite_respects_explicit_shell_filter(monkeypatch, specs_root: Path) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_run(
        root,
        shell_name,
        model_name,
        backend_name,
        run_id=None,
        tests_filter=None,
        test_tags_filter=None,
        formats_filter=None,
        container_image=None,
        keep_system_messages=False,
        model_hash=None,
        run_metadata=None,
        progress=None,
    ):
        calls.append((shell_name, model_name))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_suite(
        specs_root,
        suite_name="default_cli_matrix",
        models=["local/qwen2.5:7b", "local/qwen3:8b"],
        shells=["continue-cli"],
    )

    assert calls == [
        ("continue-cli", "local/qwen2.5:7b"),
        ("continue-cli", "local/qwen3:8b"),
    ]


def test_run_suite_matrix_runs_only_explicit_combinations(monkeypatch, specs_root: Path) -> None:
    calls: list[tuple[str, str, tuple[str, ...] | None]] = []

    def _fake_run(
        root,
        shell_name,
        model_name,
        backend_name,
        run_id=None,
        tests_filter=None,
        test_tags_filter=None,
        formats_filter=None,
        container_image=None,
        keep_system_messages=False,
        model_hash=None,
        run_metadata=None,
        progress=None,
    ):
        calls.append((shell_name, model_name, tuple(formats_filter or ())))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="aggregate_full_passed_matrix",
        shells=None,
        models=None,
    )

    assert len(run_dirs) == 13
    assert len(calls) == 13
    assert ("continue-cli", "local/qwen2.5:7b", ("markdown",)) in calls
    assert ("continue-cli", "local/ministral-3:8b", ("tool",)) in calls
    assert ("gptme", "local/qwen2.5:7b", ("tool",)) in calls
    assert ("gptme", "local/mistral-nemo:12b", ("tool",)) in calls


def test_run_suite_resume_skips_completed_matrix_entries(monkeypatch, specs_root: Path) -> None:
    expected_non_sanity_tests = [
        "patch_file_prepared",
        "python_file",
        "python_file_de",
        "python_file_ru",
        "save_file",
        "shell_date_de",
        "shell_date_ru",
        "shell_file",
        "web_nonce_proof",
    ]
    completed_manifest = specs_root / "results" / "runs" / "20260423T131238Z" / "manifest.json"
    completed_manifest.parent.mkdir(parents=True, exist_ok=True)
    completed_manifest.write_text(
        json.dumps(
            {
                "shell": "continue-cli",
                "model": "local_qwen2_5_7b",
                "backend": "ollama",
                "formats": ["markdown"],
                "tests": expected_non_sanity_tests,
                "run_metadata": {"suite": "aggregate_full_passed_matrix"},
            }
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def _fake_run(
        root,
        shell_name,
        model_name,
        backend_name,
        run_id=None,
        tests_filter=None,
        test_tags_filter=None,
        formats_filter=None,
        container_image=None,
        keep_system_messages=False,
        model_hash=None,
        run_metadata=None,
        progress=None,
    ):
        calls.append((shell_name, model_name, tuple(formats_filter or ())))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="aggregate_full_passed_matrix",
        resume_suite=True,
    )

    assert len(run_dirs) == 12
    assert len(calls) == 12
    assert ("continue-cli", "local/qwen2.5:7b", ("markdown",)) not in calls


def test_run_suite_resume_does_not_skip_when_completed_tests_differ(monkeypatch, specs_root: Path) -> None:
    completed_manifest = specs_root / "results" / "runs" / "20260423T131238Z" / "manifest.json"
    completed_manifest.parent.mkdir(parents=True, exist_ok=True)
    completed_manifest.write_text(
        json.dumps(
            {
                "shell": "continue-cli",
                "model": "local_qwen2_5_7b",
                "backend": "ollama",
                "formats": ["markdown"],
                "tests": [
                    "patch_file_prepared",
                    "python_file",
                ],
                "run_metadata": {"suite": "aggregate_full_passed_matrix"},
            }
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def _fake_run(
        root,
        shell_name,
        model_name,
        backend_name,
        run_id=None,
        tests_filter=None,
        test_tags_filter=None,
        formats_filter=None,
        container_image=None,
        keep_system_messages=False,
        model_hash=None,
        run_metadata=None,
        progress=None,
    ):
        calls.append((shell_name, model_name, tuple(formats_filter or ())))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="aggregate_full_passed_matrix",
        resume_suite=True,
    )

    assert len(run_dirs) == 13
    assert len(calls) == 13
    assert ("continue-cli", "local/qwen2.5:7b", ("markdown",)) in calls
