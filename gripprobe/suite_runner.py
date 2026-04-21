from __future__ import annotations

import time
from pathlib import Path

from gripprobe.models import SuiteSpec
from gripprobe.results import utc_run_id
from gripprobe.runner import run
from gripprobe.spec_loader import load_shell_specs, load_suite_specs


def _find_suite(root: Path, suite_name: str) -> SuiteSpec:
    suites = load_suite_specs(root)
    for suite in suites:
        if suite.id == suite_name:
            return suite
    raise ValueError(f"Could not find suite id={suite_name}")


def _resolve_shells(root: Path, suite: SuiteSpec, shell_filter: list[str] | None) -> list[str]:
    if shell_filter:
        return shell_filter
    if suite.shells:
        return list(suite.shells)
    return [shell.id for shell in load_shell_specs(root)]


def _unique_run_id(used: set[str]) -> str:
    while True:
        rid = utc_run_id()
        if rid not in used:
            used.add(rid)
            return rid
        time.sleep(1.05)


def run_suite(
    root: Path,
    suite_name: str,
    shells: list[str] | None = None,
    models: list[str] | None = None,
    tests: list[str] | None = None,
    test_tags: list[str] | None = None,
    formats: list[str] | None = None,
    container_image: str | None = None,
    keep_system_messages: bool = False,
    model_hash: str | None = None,
    metadata: dict[str, str] | None = None,
) -> list[Path]:
    suite = _find_suite(root, suite_name)
    selected_shells = _resolve_shells(root, suite, shells)
    selected_models_source = models if models is not None else suite.models
    selected_models = list(selected_models_source or [])
    if not selected_models:
        raise ValueError(f"Suite {suite.id} does not define any models")

    selected_tests_source = tests if tests is not None else suite.tests
    selected_test_tags_source = test_tags if test_tags is not None else suite.test_tags
    selected_formats_source = formats if formats is not None else suite.formats
    selected_tests = list(selected_tests_source or []) or None
    selected_test_tags = list(selected_test_tags_source or []) or None
    selected_formats = list(selected_formats_source or []) or None
    merged_metadata = {**suite.metadata, **(metadata or {})}

    run_dirs: list[Path] = []
    used_run_ids: set[str] = set()
    for shell_name in selected_shells:
        for model_name in selected_models:
            run_dir, _ = run(
                root,
                shell_name=shell_name,
                model_name=model_name,
                backend_name=suite.backend,
                run_id=_unique_run_id(used_run_ids),
                tests_filter=selected_tests,
                test_tags_filter=selected_test_tags,
                formats_filter=selected_formats,
                container_image=container_image,
                keep_system_messages=keep_system_messages,
                model_hash=model_hash,
                run_metadata=merged_metadata,
                progress=lambda line: print(line, flush=True),
            )
            run_dirs.append(run_dir)
    return run_dirs
