from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path

from gripprobe.models import ModelSpec, ShellSpec, SuiteSpec, TestSpec
from gripprobe.results import utc_run_id
from gripprobe.runner import run
from gripprobe.spec_loader import load_model_specs, load_shell_specs, load_suite_specs, load_test_specs

SuiteRunKey = tuple[str, str, str, tuple[str, ...], tuple[str, ...]]
SuiteCaseKey = tuple[str, str, str, str, str]


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


def _model_alias_map(root: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for model in load_model_specs(root):
        aliases[model.id] = model.id
        aliases[model.label] = model.id
    return aliases


def _canonical_model_id(model_name: str, aliases: dict[str, str]) -> str:
    return aliases.get(model_name, model_name)


def _resolve_effective_formats(
    shell_id: str,
    model_name: str,
    formats_filter: list[str] | None,
    shell_by_id: dict[str, ShellSpec],
    model_by_id: dict[str, ModelSpec],
    aliases: dict[str, str],
) -> tuple[str, ...]:
    if formats_filter is not None:
        return tuple(formats_filter)
    model_id = _canonical_model_id(model_name, aliases)
    shell_spec = shell_by_id.get(shell_id)
    model_spec = model_by_id.get(model_id)
    if shell_spec is None or model_spec is None:
        return ()
    shared = [fmt for fmt in model_spec.supported_formats if fmt in shell_spec.supported_formats]
    return tuple(shared or shell_spec.supported_formats)


def _filter_tests_by_selection(tests: list[TestSpec], selected: list[str] | None) -> list[TestSpec]:
    if not selected:
        return tests
    wanted = set(selected)
    return [test for test in tests if test.id in wanted or test.title in wanted]


def _filter_tests_by_tags(tests: list[TestSpec], selected_tags: list[str] | None) -> list[TestSpec]:
    if not selected_tags:
        return tests
    wanted = set(selected_tags)
    return [test for test in tests if wanted.intersection(test.tags)]


def _resolve_selected_tests(
    all_tests: list[TestSpec],
    tests_filter: list[str] | None,
    test_tags_filter: list[str] | None,
) -> list[TestSpec]:
    selected = _filter_tests_by_selection(all_tests, tests_filter)
    return _filter_tests_by_tags(selected, test_tags_filter)


def _effective_test_ids_for_format(
    tests: list[TestSpec],
    shell_id: str,
    tool_format: str,
) -> tuple[str, ...]:
    test_ids: list[str] = []
    for test in tests:
        if test.supported_shells and shell_id not in test.supported_shells:
            continue
        if test.supported_formats and tool_format not in test.supported_formats:
            continue
        test_ids.append(test.id)
    return tuple(test_ids)


def _manifest_run_key(payload: dict[str, object], aliases: dict[str, str]) -> SuiteRunKey | None:
    shell = payload.get("shell")
    model = payload.get("model")
    backend = payload.get("backend")
    formats = payload.get("formats")
    if not isinstance(shell, str) or not isinstance(model, str) or not isinstance(backend, str):
        return None
    if not isinstance(formats, list) or not all(isinstance(item, str) for item in formats):
        return None
    tests = payload.get("tests")
    if not isinstance(tests, list) or not all(isinstance(item, str) for item in tests):
        return None
    return (
        shell,
        _canonical_model_id(model, aliases),
        backend,
        tuple(formats),
        tuple(tests),
    )


def _read_json_dict(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _case_key_from_case_json(payload: dict[str, object], aliases: dict[str, str]) -> SuiteCaseKey | None:
    shell = payload.get("shell")
    tool_format = payload.get("format")
    test_id = payload.get("test")
    model_payload = payload.get("model")
    if not isinstance(shell, str) or not isinstance(tool_format, str) or not isinstance(test_id, str):
        return None
    if not isinstance(model_payload, dict):
        return None
    model_id = model_payload.get("id")
    backend = model_payload.get("backend")
    if not isinstance(model_id, str) or not isinstance(backend, str):
        return None
    return (
        shell,
        _canonical_model_id(model_id, aliases),
        backend,
        tool_format,
        test_id,
    )


def _expand_manifest_run_key_to_case_keys(run_key: SuiteRunKey) -> set[SuiteCaseKey]:
    shell, model, backend, formats, tests = run_key
    keys: set[SuiteCaseKey] = set()
    for tool_format in formats:
        for test_id in tests:
            keys.add((shell, model, backend, tool_format, test_id))
    return keys


def _load_completed_case_keys(root: Path, aliases: dict[str, str]) -> set[SuiteCaseKey]:
    runs_root = root / "results" / "runs"
    if not runs_root.exists():
        return set()
    completed: set[SuiteCaseKey] = set()
    for run_dir in sorted(runs_root.glob("*")):
        run_case_keys: set[SuiteCaseKey] = set()
        for case_json_path in sorted((run_dir / "cases").glob("*/case.json")):
            case_payload = _read_json_dict(case_json_path)
            if case_payload is None:
                continue
            key = _case_key_from_case_json(case_payload, aliases)
            if key is not None:
                run_case_keys.add(key)
        if run_case_keys:
            completed.update(run_case_keys)
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _read_json_dict(manifest_path)
        if manifest is None:
            continue
        run_key = _manifest_run_key(manifest, aliases)
        if run_key is not None:
            completed.update(_expand_manifest_run_key_to_case_keys(run_key))
    return completed


def _unique_run_id(used: set[str]) -> str:
    while True:
        rid = utc_run_id()
        if rid not in used:
            used.add(rid)
            return rid
        time.sleep(1.05)


def _select_items(
    cli_items: list[str] | None,
    entry_items: Iterable[str] | None,
    suite_items: Iterable[str] | None,
) -> list[str] | None:
    source = cli_items if cli_items is not None else (entry_items if entry_items else suite_items)
    values = list(source or [])
    return values or None


def _missing_tests_by_format(
    *,
    shell_id: str,
    model_name: str,
    backend_name: str,
    formats: tuple[str, ...],
    selected_tests: list[TestSpec],
    completed_case_keys: set[SuiteCaseKey],
    aliases: dict[str, str],
) -> dict[str, list[str]]:
    model_id = _canonical_model_id(model_name, aliases)
    missing: dict[str, list[str]] = {}
    for tool_format in formats:
        test_ids = _effective_test_ids_for_format(selected_tests, shell_id, tool_format)
        if not test_ids:
            continue
        missing_tests = [
            test_id
            for test_id in test_ids
            if (shell_id, model_id, backend_name, tool_format, test_id) not in completed_case_keys
        ]
        if missing_tests:
            missing[tool_format] = missing_tests
    return missing


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
    resume_suite: bool = False,
) -> list[Path]:
    suite = _find_suite(root, suite_name)
    all_tests = load_test_specs(root)
    model_aliases = _model_alias_map(root)
    model_by_id = {model.id: model for model in load_model_specs(root)}
    shell_by_id = {shell.id: shell for shell in load_shell_specs(root)}
    completed_case_keys = _load_completed_case_keys(root, model_aliases) if resume_suite else set()

    run_dirs: list[Path] = []
    used_run_ids: set[str] = set()
    if suite.matrix:
        selected_entries = list(suite.matrix)
        if shells:
            selected_shells = set(shells)
            selected_entries = [entry for entry in selected_entries if entry.shell in selected_shells]
        if models:
            selected_models = set(models)
            selected_entries = [entry for entry in selected_entries if entry.model in selected_models]
        if not selected_entries:
            raise ValueError(f"Suite {suite.id} matrix has no entries after shell/model filters")

        for entry in selected_entries:
            selected_tests = _select_items(tests, entry.tests, suite.tests)
            selected_test_tags = _select_items(test_tags, entry.test_tags, suite.test_tags)
            selected_test_specs = _resolve_selected_tests(all_tests, selected_tests, selected_test_tags)
            selected_backend = entry.backend or suite.backend
            selected_formats = _select_items(
                formats,
                [entry.format] if entry.format else None,
                suite.formats,
            )
            effective_formats = _resolve_effective_formats(
                entry.shell,
                entry.model,
                selected_formats,
                shell_by_id,
                model_by_id,
                model_aliases,
            )
            merged_metadata = {**suite.metadata, **entry.metadata, **(metadata or {})}
            if resume_suite:
                missing_by_format = _missing_tests_by_format(
                    shell_id=entry.shell,
                    model_name=entry.model,
                    backend_name=selected_backend,
                    formats=effective_formats,
                    selected_tests=selected_test_specs,
                    completed_case_keys=completed_case_keys,
                    aliases=model_aliases,
                )
                if not missing_by_format:
                    total_effective_tests = sum(
                        len(_effective_test_ids_for_format(selected_test_specs, entry.shell, tool_format))
                        for tool_format in effective_formats
                    )
                    print(
                        "SKIP "
                        f"shell={entry.shell} "
                        f"model={entry.model} "
                        f"backend={selected_backend} "
                        f"formats={','.join(effective_formats)} "
                        f"tests={total_effective_tests} "
                        "reason=resume-suite",
                        flush=True,
                    )
                    continue
                for tool_format, missing_tests in missing_by_format.items():
                    run_dir, _ = run(
                        root,
                        shell_name=entry.shell,
                        model_name=entry.model,
                        backend_name=selected_backend,
                        run_id=_unique_run_id(used_run_ids),
                        tests_filter=missing_tests,
                        test_tags_filter=None,
                        formats_filter=[tool_format],
                        container_image=container_image,
                        keep_system_messages=keep_system_messages,
                        model_hash=model_hash,
                        run_metadata=merged_metadata,
                        progress=lambda line: print(line, flush=True),
                    )
                    run_dirs.append(run_dir)
                    model_id = _canonical_model_id(entry.model, model_aliases)
                    for test_id in missing_tests:
                        completed_case_keys.add((entry.shell, model_id, selected_backend, tool_format, test_id))
                continue
            run_dir, _ = run(
                root,
                shell_name=entry.shell,
                model_name=entry.model,
                backend_name=selected_backend,
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

    selected_shells = _resolve_shells(root, suite, shells)
    selected_models_source = models if models is not None else suite.models
    selected_models = list(selected_models_source or [])
    if not selected_models:
        raise ValueError(f"Suite {suite.id} does not define any models")

    selected_tests = _select_items(tests, None, suite.tests)
    selected_test_tags = _select_items(test_tags, None, suite.test_tags)
    selected_test_specs = _resolve_selected_tests(all_tests, selected_tests, selected_test_tags)
    selected_formats = _select_items(formats, None, suite.formats)
    merged_metadata = {**suite.metadata, **(metadata or {})}

    for shell_name in selected_shells:
        for model_name in selected_models:
            effective_formats = _resolve_effective_formats(
                shell_name,
                model_name,
                selected_formats,
                shell_by_id,
                model_by_id,
                model_aliases,
            )
            if resume_suite:
                missing_by_format = _missing_tests_by_format(
                    shell_id=shell_name,
                    model_name=model_name,
                    backend_name=suite.backend,
                    formats=effective_formats,
                    selected_tests=selected_test_specs,
                    completed_case_keys=completed_case_keys,
                    aliases=model_aliases,
                )
                if not missing_by_format:
                    total_effective_tests = sum(
                        len(_effective_test_ids_for_format(selected_test_specs, shell_name, tool_format))
                        for tool_format in effective_formats
                    )
                    print(
                        "SKIP "
                        f"shell={shell_name} "
                        f"model={model_name} "
                        f"backend={suite.backend} "
                        f"formats={','.join(effective_formats)} "
                        f"tests={total_effective_tests} "
                        "reason=resume-suite",
                        flush=True,
                    )
                    continue
                for tool_format, missing_tests in missing_by_format.items():
                    run_dir, _ = run(
                        root,
                        shell_name=shell_name,
                        model_name=model_name,
                        backend_name=suite.backend,
                        run_id=_unique_run_id(used_run_ids),
                        tests_filter=missing_tests,
                        test_tags_filter=None,
                        formats_filter=[tool_format],
                        container_image=container_image,
                        keep_system_messages=keep_system_messages,
                        model_hash=model_hash,
                        run_metadata=merged_metadata,
                        progress=lambda line: print(line, flush=True),
                    )
                    run_dirs.append(run_dir)
                    model_id = _canonical_model_id(model_name, model_aliases)
                    for test_id in missing_tests:
                        completed_case_keys.add((shell_name, model_id, suite.backend, tool_format, test_id))
                continue
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
