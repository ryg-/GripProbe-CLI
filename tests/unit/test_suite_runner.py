from __future__ import annotations

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
