from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from gripprobe.adapters.base import AdapterError
from gripprobe.adapters.continue_cli import ContinueCliAdapter
from gripprobe.adapters.gptme import GptmeAdapter
from gripprobe.case_result import build_case_result
from gripprobe.models import BackendSpec, CaseDefinition, CaseResult, ModelSpec, ShellSpec, TestSpec
from gripprobe.reporters.html_report import write_html_summary
from gripprobe.reporters.markdown import write_markdown_summary
from gripprobe.results import create_run_paths, write_json
from gripprobe.spec_loader import load_model_specs, load_shell_specs, load_test_specs


DEFAULT_BACKEND = "ollama"


def _find_one(items, attr: str, value: str):
    for item in items:
        if getattr(item, attr) == value or getattr(item, "label", None) == value:
            return item
    raise ValueError(f"Could not find {attr}={value}")


def _prepare_workspace(path: Path, test_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for file in path.iterdir():
        if file.is_file() or file.is_symlink():
            file.unlink()
        elif file.is_dir():
            shutil.rmtree(file)
    if test_id == "patch_file":
        (path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")


def _adapter_for(shell_spec: ShellSpec):
    if shell_spec.id == "gptme":
        return GptmeAdapter(shell_spec)
    if shell_spec.id == "continue-cli":
        return ContinueCliAdapter(shell_spec)
    raise ValueError(f"Unsupported shell adapter: {shell_spec.id}")


def _filter_tests(tests: list[TestSpec], selected: Iterable[str] | None) -> list[TestSpec]:
    if not selected:
        return tests
    wanted = set(selected)
    return [test for test in tests if test.id in wanted or test.title in wanted]


def _filter_formats(formats: list[str], selected: Iterable[str] | None) -> list[str]:
    if not selected:
        return formats
    wanted = set(selected)
    return [fmt for fmt in formats if fmt in wanted]


def _select_backend(model_spec: ModelSpec, backend_name: str) -> BackendSpec:
    for backend in model_spec.backends:
        if backend.id == backend_name:
            return backend
    available = ", ".join(backend.id for backend in model_spec.backends) or "<none>"
    raise ValueError(
        f"Model {model_spec.id} does not define backend={backend_name}. Available: {available}"
    )


def _harness_error_result(case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec, message: str) -> CaseResult:
    return build_case_result(
        case=case,
        model_spec=model_spec,
        test_spec=test_spec,
        status="HARNESS_ERROR",
        invoked="no",
        match_percent=0,
        warmup_seconds=0.0,
        measured_seconds=0.0,
        metadata={"error": message, "model_hash": case.model_hash},
    )


def run(
    root: Path,
    shell_name: str,
    model_name: str,
    backend_name: str = DEFAULT_BACKEND,
    run_id: str | None = None,
    tests_filter: list[str] | None = None,
    formats_filter: list[str] | None = None,
    container_image: str | None = None,
) -> tuple[Path, list[CaseResult]]:
    tests = load_test_specs(root)
    models = load_model_specs(root)
    shells = load_shell_specs(root)

    model_spec: ModelSpec = _find_one(models, "label", model_name)
    shell_spec: ShellSpec = _find_one(shells, "id", shell_name)
    backend = _select_backend(model_spec, backend_name)
    adapter = _adapter_for(shell_spec)
    run_paths = create_run_paths(root, run_id=run_id)

    results: list[CaseResult] = []
    tests = _filter_tests(tests, tests_filter)
    formats = [fmt for fmt in model_spec.supported_formats if fmt in shell_spec.supported_formats] or shell_spec.supported_formats
    formats = _filter_formats(formats, formats_filter)

    for tool_format in formats:
        for test_spec in tests:
            if test_spec.supported_shells and shell_spec.id not in test_spec.supported_shells:
                continue
            if test_spec.supported_formats and tool_format not in test_spec.supported_formats:
                continue
            case_id = f"{shell_spec.id}__{model_spec.id}__{backend.id}__{tool_format}__{test_spec.id}"
            case_dir = run_paths.cases_dir / case_id
            workspace_dir = case_dir / "workspace"
            _prepare_workspace(workspace_dir, test_spec.id)
            case = CaseDefinition(
                case_id=case_id,
                run_id=run_paths.run_id,
                shell_id=shell_spec.id,
                shell_label=shell_spec.label,
                model_id=model_spec.id,
                model_label=model_spec.label,
                backend_id=backend.id,
                backend_model_id=backend.model_id,
                shell_model_id=backend.shell_model_id,
                model_hash=backend.model_hash,
                quantization=model_spec.quantization,
                tool_format=tool_format,
                test_id=test_spec.id,
                test_title=test_spec.title,
                prompt=test_spec.prompt,
                workspace_dir=workspace_dir,
                case_dir=case_dir,
                allowed_tools=test_spec.allowed_tools,
                container_image=container_image or shell_spec.container_image,
            )
            try:
                result = adapter.run_case(case, model_spec, test_spec)
            except AdapterError as exc:
                result = _harness_error_result(case, model_spec, test_spec, str(exc))
            write_json(case_dir / "case.json", result.model_dump())
            results.append(result)

    write_markdown_summary(results, run_paths.reports_dir / "summary.md")
    write_html_summary(results, run_paths.reports_dir / "summary.html")
    write_json(
        run_paths.run_dir / "manifest.json",
        {
            "run_id": run_paths.run_id,
            "shell": shell_spec.id,
            "model": model_spec.id,
            "backend": backend.id,
            "model_hash": backend.model_hash,
            "cases": len(results),
            "formats": formats,
            "tests": [test.id for test in tests],
            "container_image": container_image or shell_spec.container_image,
        },
    )
    return run_paths.run_dir, results
