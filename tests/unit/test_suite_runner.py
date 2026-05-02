from __future__ import annotations

import json
from pathlib import Path

from gripprobe.spec_loader import load_suite_specs
from gripprobe.suite_runner import run_suite


def _suite_matrix_size(specs_root: Path, suite_id: str) -> int:
    suites = load_suite_specs(specs_root)
    for suite in suites:
        if suite.id == suite_id:
            return len(suite.matrix)
    raise AssertionError(f"missing suite {suite_id}")


def _write_case_json(
    run_dir: Path,
    *,
    shell: str,
    model_id: str,
    backend: str,
    tool_format: str,
    test_id: str,
) -> None:
    case_dir = run_dir / "cases" / f"{shell}__{model_id}__{backend}__{tool_format}__{test_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "shell": shell,
                "format": tool_format,
                "test": test_id,
                "model": {"id": model_id, "backend": backend},
            }
        ),
        encoding="utf-8",
    )


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

    expected_size = _suite_matrix_size(specs_root, "aggregate_full_passed_matrix")
    assert len(run_dirs) == expected_size
    assert len(calls) == expected_size
    assert ("continue-cli", "local/qwen2.5:7b", ("markdown",)) in calls
    assert ("continue-cli", "local/qwen3.5:9b", ("markdown",)) in calls
    assert ("continue-cli", "local/aravhawk/qwen3.5-opus-4.6-text:9b", ()) in calls
    assert ("continue-cli", "local/cryptidbleh/gemma4-claude-opus-4.6:latest", ("markdown",)) in calls
    assert ("continue-cli", "local/ministral-3:8b", ("tool",)) in calls
    assert ("gptme", "local/qwen2.5:7b", ("tool",)) in calls
    assert ("gptme", "local/qwen3.5:9b", ("tool",)) in calls
    assert ("gptme", "local/aravhawk/qwen3.5-opus-4.6-text:9b", ("tool",)) in calls
    assert ("gptme", "local/cryptidbleh/gemma4-claude-opus-4.6:latest", ("tool",)) in calls
    assert ("gptme", "local/mistral-nemo:12b", ("tool",)) in calls


def test_run_suite_resume_skips_completed_matrix_entries(monkeypatch, specs_root: Path) -> None:
    expected_non_sanity_tests = [
        "json_rank_from_file",
        "patch_file_prepared",
        "python_file",
        "python_file_de",
        "python_file_ru",
        "save_file",
        "shell_date_de",
        "shell_date_ru",
        "shell_file",
        "web_fetch_json_raw",
        "web_nonce_proof",
        "web_search_json_ranked",
        "weekly_plan_next_week",
    ]
    completed_run_dir = specs_root / "results" / "runs" / "20260423T131238Z"
    completed_manifest = completed_run_dir / "manifest.json"
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
    for test_id in expected_non_sanity_tests:
        _write_case_json(
            completed_run_dir,
            shell="continue-cli",
            model_id="local_qwen2_5_7b",
            backend="ollama",
            tool_format="markdown",
            test_id=test_id,
        )

    calls: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []

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
        calls.append((shell_name, model_name, tuple(formats_filter or ()), tuple(tests_filter or ())))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="aggregate_full_passed_matrix",
        resume_suite=True,
    )

    assert len(run_dirs) == len(calls)
    assert len(calls) > 0
    assert not any(
        shell == "continue-cli" and model == "local/qwen2.5:7b" and formats == ("markdown",)
        for shell, model, formats, _tests in calls
    )


def test_run_suite_resume_does_not_skip_when_completed_tests_differ(monkeypatch, specs_root: Path) -> None:
    completed_run_dir = specs_root / "results" / "runs" / "20260423T131238Z"
    completed_manifest = completed_run_dir / "manifest.json"
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
    _write_case_json(
        completed_run_dir,
        shell="continue-cli",
        model_id="local_qwen2_5_7b",
        backend="ollama",
        tool_format="markdown",
        test_id="patch_file_prepared",
    )
    _write_case_json(
        completed_run_dir,
        shell="continue-cli",
        model_id="local_qwen2_5_7b",
        backend="ollama",
        tool_format="markdown",
        test_id="python_file",
    )

    calls: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []

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
        calls.append((shell_name, model_name, tuple(formats_filter or ()), tuple(tests_filter or ())))
        return Path(root) / "results" / "runs" / str(run_id), []

    monkeypatch.setattr("gripprobe.suite_runner.run", _fake_run)

    run_dirs = run_suite(
        specs_root,
        suite_name="aggregate_full_passed_matrix",
        resume_suite=True,
    )

    assert len(run_dirs) == len(calls)
    assert len(calls) > 0

    qwen25_call = next(
        (
            call
            for call in calls
            if call[0] == "continue-cli" and call[1] == "local/qwen2.5:7b" and call[2] == ("markdown",)
        ),
        None,
    )
    assert qwen25_call is not None
    assert "patch_file_prepared" not in qwen25_call[3]
    assert "python_file" not in qwen25_call[3]
    assert len(qwen25_call[3]) > 0
