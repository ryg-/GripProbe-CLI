from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, cast

from gripprobe.command_runner import CallableCommandRunner, CommandResult, CommandRunner
from gripprobe.models import CaseDefinition, CaseResult, ModelSpec, TestSpec
from gripprobe.proxy_capture import (
    PhaseProxyCapture,
    ProxyCaptureOptions,
    ProxyFactory,
    TelemetryPhase,
    proxy_artifact_path,
)
from gripprobe.telemetry_proxy import OllamaTelemetryProxy


class CaseAdapter(Protocol):
    """Adapter contract used by phase execution, including legacy fallback."""

    def run_case(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        test_spec: TestSpec,
        command_runner: CommandRunner | None = None,
    ) -> CaseResult:
        ...


def phase_from_command_paths(
    *,
    case: CaseDefinition,
    stdout_path: Path,
    workspace_dir: Path | None,
) -> TelemetryPhase:
    if stdout_path.name.startswith("warmup.") or workspace_dir == case.warmup_workspace_dir:
        return "warmup"
    return "measured"


class PhaseProxyCommandRunner:
    """Route each adapter command through its phase's proxy when available."""

    def __init__(self, *, capture: PhaseProxyCapture, base_runner: CommandRunner) -> None:
        self.capture = capture
        self.base_runner = base_runner

    def run(
        self,
        *,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        workspace_dir: Path | None = None,
    ) -> CommandResult:
        phase = phase_from_command_paths(
            case=case,
            stdout_path=stdout_path,
            workspace_dir=workspace_dir,
        )
        proxy = self.capture.proxy_for(phase)
        if proxy is None or not proxy.base_url:
            self.capture.mark_unavailable(phase)
            return self.base_runner.run(
                case=case,
                args=args,
                env=env,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                workspace_dir=workspace_dir,
            )

        proxy_env = {
            **env,
            "OLLAMA_HOST": proxy.base_url,
            "OPENAI_BASE_URL": f"{proxy.base_url}/v1",
        }
        try:
            return self.base_runner.run(
                case=case,
                args=args,
                env=proxy_env,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                workspace_dir=workspace_dir,
            )
        finally:
            self.capture.finish_phase(phase)


def run_case_with_phase_proxy(
    *,
    adapter: CaseAdapter,
    case: CaseDefinition,
    model_spec: ModelSpec,
    test_spec: TestSpec,
    upstream_base_url: str,
    proxy_options: ProxyCaptureOptions,
    proxy_factory: ProxyFactory = OllamaTelemetryProxy,
) -> tuple[CaseResult, dict[str, str], dict[str, str], str | None]:
    original_run_command = getattr(adapter, "run_command", None)
    if not callable(original_run_command):
        result = adapter.run_case(case, model_spec, test_spec)
        return (
            result,
            {
                "telemetry_proxy_upstream_base_url": upstream_base_url,
                "telemetry_proxy_warmup_artifact_path": proxy_artifact_path("warmup"),
                "telemetry_proxy_measured_artifact_path": proxy_artifact_path("measured"),
            },
            {},
            "adapter_missing_run_command",
        )

    capture = PhaseProxyCapture(
        case_dir=case.case_dir,
        upstream_base_url=upstream_base_url,
        options=proxy_options,
        proxy_factory=proxy_factory,
    )
    capture.start()
    phase_proxy_metadata = capture.runtime_metadata()
    phase_hosts = {
        key: value
        for key, value in phase_proxy_metadata.items()
        if key.startswith(("telemetry_proxy_warmup_", "telemetry_proxy_measured_"))
        and key.endswith(("_ollama_host", "_openai_base_url"))
    }
    if phase_hosts:
        case.run_metadata = {**case.run_metadata, **phase_hosts}

    phase_runner = PhaseProxyCommandRunner(
        capture=capture,
        base_runner=CallableCommandRunner(
            cast(Callable[..., CommandResult], original_run_command)
        ),
    )
    try:
        result = adapter.run_case(
            case,
            model_spec,
            test_spec,
            command_runner=phase_runner,
        )
    finally:
        capture.stop_all()

    if result is None:
        raise RuntimeError("adapter completed without returning a case result")
    return result, capture.runtime_metadata(), capture.artifact_relpaths(), capture.runtime_error
