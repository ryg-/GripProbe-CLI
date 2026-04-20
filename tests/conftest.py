from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gripprobe.adapters.base import AdapterError
from gripprobe.case_result import build_case_result


@pytest.fixture()
def specs_root(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    shutil.copytree(repo_root / "specs", tmp_path / "specs")
    return tmp_path


class FakeSuccessAdapter:
    def __init__(self, shell_spec):
        self.shell_spec = shell_spec

    def run_case(self, case, model_spec, test_spec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
        (case.case_dir / "warmup.stdout").write_text("warmup ok\n", encoding="utf-8")
        (case.case_dir / "warmup.stderr").write_text("", encoding="utf-8")
        (case.case_dir / "measured.stdout").write_text("measured ok\n", encoding="utf-8")
        (case.case_dir / "measured.stderr").write_text("", encoding="utf-8")
        (case.case_dir / "expected.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")
        (case.case_dir / "observed.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")
        (case.workspace_dir / "pwd-output.txt").write_text(str(case.workspace_dir) + "\n", encoding="utf-8")

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status="PASS",
            trajectory="clean",
            invoked="yes",
            match_percent=100,
            warmup_seconds=0.01,
            measured_seconds=0.02,
            metadata={"tool_format": case.tool_format},
        )


class FakeTimeoutAdapter:
    def __init__(self, shell_spec):
        self.shell_spec = shell_spec

    def run_case(self, case, model_spec, test_spec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
        (case.case_dir / "warmup.stdout").write_text("warmup timeout\n", encoding="utf-8")
        (case.case_dir / "warmup.stderr").write_text("", encoding="utf-8")
        (case.case_dir / "measured.stdout").write_text("timed out\n", encoding="utf-8")
        (case.case_dir / "measured.stderr").write_text("", encoding="utf-8")
        (case.case_dir / "expected.txt").write_text("\n", encoding="utf-8")
        (case.case_dir / "observed.txt").write_text("\n", encoding="utf-8")

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status="TIMEOUT",
            trajectory="clean",
            invoked="no",
            match_percent=0,
            warmup_seconds=0.5,
            measured_seconds=1.0,
            metadata={
                "tool_format": case.tool_format,
                "measured_exit_code": 124,
                "artifact_reached_before_timeout": False,
            },
        )


class FakeTimeoutWithArtifactAdapter:
    def __init__(self, shell_spec):
        self.shell_spec = shell_spec

    def run_case(self, case, model_spec, test_spec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
        (case.case_dir / "warmup.stdout").write_text("warmup timeout after work\n", encoding="utf-8")
        (case.case_dir / "warmup.stderr").write_text("", encoding="utf-8")
        (case.case_dir / "measured.stdout").write_text("timed out after artifact creation\n", encoding="utf-8")
        (case.case_dir / "measured.stderr").write_text("", encoding="utf-8")
        expected = str(case.workspace_dir)
        observed = str(case.workspace_dir)
        (case.case_dir / "expected.txt").write_text(expected + "\n", encoding="utf-8")
        (case.case_dir / "observed.txt").write_text(observed + "\n", encoding="utf-8")
        (case.workspace_dir / "pwd-output.txt").write_text(observed + "\n", encoding="utf-8")

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status="TIMEOUT",
            trajectory="clean",
            invoked="yes",
            match_percent=100,
            warmup_seconds=0.5,
            measured_seconds=1.0,
            metadata={
                "tool_format": case.tool_format,
                "measured_exit_code": 124,
                "artifact_reached_before_timeout": True,
            },
        )


class ExplodingAdapter:
    def __init__(self, shell_spec):
        self.shell_spec = shell_spec

    def run_case(self, case, model_spec, test_spec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")
        raise AdapterError("simulated adapter failure")
