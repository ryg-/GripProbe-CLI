from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from gripprobe.runner import run


pytestmark = pytest.mark.real_e2e


DEFAULT_SHELL = "gptme"
DEFAULT_MODEL = "local/qwen2.5:7b"
DEFAULT_BACKEND = "ollama"
DEFAULT_TEST = "shell_pwd"
DEFAULT_FORMAT = "markdown"
DEFAULT_TIMEOUT_SECONDS = 60


@pytest.fixture()
def real_specs_root(specs_root: Path) -> Path:
    shell_name = os.environ.get("GRIPPROBE_REAL_SHELL", DEFAULT_SHELL)
    timeout_seconds = int(os.environ.get("GRIPPROBE_REAL_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    openai_base_url = os.environ.get("GRIPPROBE_OPENAI_BASE_URL")

    shell_spec_path = specs_root / "specs" / "shells" / f"{shell_name}.yaml"
    data = yaml.safe_load(shell_spec_path.read_text(encoding="utf-8")) or {}
    data["timeout_seconds"] = timeout_seconds
    if openai_base_url:
        data.setdefault("env", {})["OPENAI_BASE_URL"] = openai_base_url
    shell_spec_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return specs_root


@pytest.mark.skipif(
    os.environ.get("GRIPPROBE_RUN_REAL_E2E") != "1",
    reason="real e2e is opt-in; set GRIPPROBE_RUN_REAL_E2E=1",
)
def test_real_local_model_shell_pwd(real_specs_root: Path) -> None:
    shell_name = os.environ.get("GRIPPROBE_REAL_SHELL", DEFAULT_SHELL)
    model_name = os.environ.get("GRIPPROBE_REAL_MODEL", DEFAULT_MODEL)
    backend_name = os.environ.get("GRIPPROBE_REAL_BACKEND", DEFAULT_BACKEND)

    run_dir, results = run(
        real_specs_root,
        shell_name=shell_name,
        model_name=model_name,
        backend_name=backend_name,
        tests_filter=[os.environ.get("GRIPPROBE_REAL_TEST", DEFAULT_TEST)],
        formats_filter=[os.environ.get("GRIPPROBE_REAL_FORMAT", DEFAULT_FORMAT)],
        run_id="run-real-local-model",
    )

    assert len(results) == 1
    result = results[0]
    assert result.status == "PASS"
    assert result.invoked == "yes"
    assert result.match_percent == 100

    case_dir = run_dir / "cases" / result.case_id
    case_json = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    pwd_output = (case_dir / "workspace" / "pwd-output.txt").read_text(encoding="utf-8").strip()

    assert case_json["status"] == "PASS"
    assert case_json["model"]["backend"] == backend_name
    assert manifest["backend"] == backend_name
    assert pwd_output == str(case_dir / "workspace")
