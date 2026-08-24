from __future__ import annotations

from pathlib import Path

from gripprobe.adapters.base import CliAgentAdapter
from gripprobe.command_runner import CommandRunner
from gripprobe.models import CaseDefinition, CliAgentSpec, ModelSpec, TestSpec as GripTestSpec


class _ProbeAdapter(CliAgentAdapter):
    def __init__(self, spec: CliAgentSpec) -> None:
        super().__init__(spec)
        self.default_calls: list[dict[str, object]] = []

    def run_case(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        test_spec: GripTestSpec,
        command_runner: CommandRunner | None = None,
    ):
        return self._run_case_command(
            command_runner,
            case=case,
            args=["agent", "--prompt"],
            env={"TEST_ENV": "original"},
            stdout_path=case.case_dir / "stdout.log",
            stderr_path=case.case_dir / "stderr.log",
            workspace_dir=case.workspace_dir,
        )

    def run_command(
        self,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        workspace_dir: Path | None = None,
    ):
        self.default_calls.append({"args": args, "env": env, "workspace_dir": workspace_dir})
        return 0, 0.01, "started", "finished"


def _case(tmp_path: Path) -> CaseDefinition:
    return CaseDefinition.model_validate(
        {
            "case_id": "probe",
            "run_id": "run-probe",
            "cli_agent_id": "probe",
            "cli_agent_label": "probe",
            "model_id": "model",
            "model_label": "model",
            "backend_id": "ollama",
            "backend_model_id": "model",
            "cli_agent_model_id": "model",
            "model_hash": "unknown",
            "tool_format": "markdown",
            "test_id": "probe",
            "test_title": "Probe",
            "prompt": "probe",
            "warmup_workspace_dir": tmp_path / "warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
        }
    )


def _specs() -> tuple[ModelSpec, GripTestSpec]:
    model = ModelSpec.model_validate(
        {
            "id": "model",
            "label": "model",
            "family": "test",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "model", "cli_agent_model_id": "model"}],
        }
    )
    test = GripTestSpec.model_validate(
        {
            "id": "probe",
            "title": "Probe",
            "category": "probe",
            "prompt": "probe",
            "validators": [],
        }
    )
    return model, test


def test_case_command_uses_adapter_default_when_runner_is_omitted(tmp_path: Path) -> None:
    adapter = _ProbeAdapter(CliAgentSpec(id="probe", label="probe", executable="probe"))
    model, test = _specs()

    result = adapter.run_case(_case(tmp_path), model, test)

    assert result[0] == 0
    assert len(adapter.default_calls) == 1


def test_case_command_uses_injected_runner_without_mutating_adapter(tmp_path: Path) -> None:
    adapter = _ProbeAdapter(CliAgentSpec(id="probe", label="probe", executable="probe"))
    model, test = _specs()
    calls: list[dict[str, object]] = []

    class _InjectedRunner:
        def run(self, **kwargs):
            calls.append(kwargs)
            return 7, 0.02, "injected-start", "injected-finish"

    original_run_command = adapter.run_command
    result = adapter.run_case(_case(tmp_path), model, test, command_runner=_InjectedRunner())

    assert result == (7, 0.02, "injected-start", "injected-finish")
    assert len(calls) == 1
    assert calls[0]["env"] == {"TEST_ENV": "original"}
    assert adapter.run_command == original_run_command
    assert adapter.default_calls == []
