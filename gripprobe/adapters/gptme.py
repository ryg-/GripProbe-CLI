from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from gripprobe.adapters.base import CliAgentAdapter
from gripprobe.command_runner import CommandRunner
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.results import remove_transient_files, strip_system_messages_from_transcripts
from gripprobe.trace_analysis import (
    RunConsistency,
    Trajectory,
    analyze_trace,
    compare_profiles,
    derive_trajectory,
    explain_trajectory,
    infer_trace_status,
)
from gripprobe.validator_runner import evaluate_validators


class GptmeAdapter(CliAgentAdapter):
    @staticmethod
    def _gptme_policy(model_spec: ModelSpec) -> dict[str, Any]:
        cli_agent_options = (model_spec.policy_overrides or {}).get("cli_agent_options")
        if not isinstance(cli_agent_options, dict):
            return {}
        options = cli_agent_options.get("gptme")
        return options if isinstance(options, dict) else {}

    def _resolve_system_mode(self, model_spec: ModelSpec) -> str:
        mode = str(self._gptme_policy(model_spec).get("system_prompt", "short")).strip().lower()
        if mode in {"off", "none", "disable", "disabled"}:
            return "off"
        if mode in {"custom"}:
            return "custom"
        if mode in {"full", "default"}:
            return "full"
        return "short"

    def _resolve_custom_system_prompt(self, model_spec: ModelSpec) -> str:
        custom_prompt = str(self._gptme_policy(model_spec).get("custom_system_prompt", "")).strip()
        if custom_prompt:
            return custom_prompt
        return "Use tools first. Keep reasoning extremely short. Reply only with tool calls and final DONE/FAIL."

    def _resolve_context_include(self, model_spec: ModelSpec) -> str | None:
        value = self._gptme_policy(model_spec).get("context_include")
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return ",".join(items) if items else None
        return None

    def _ensure_ollama_openai_env(self, case: CaseDefinition, env: dict[str, str]) -> None:
        if case.backend_id != "ollama":
            return
        if not env.get("OPENAI_BASE_URL"):
            env["OPENAI_BASE_URL"] = self._resolve_case_openai_base_url(case, env)
        if not env.get("OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = "ollama"

    def _classify(self, test_spec: TestSpec, workspace: Path, stdout: str, stderr: str) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        profile = analyze_trace(stdout, stderr)
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        if "No tool call detected in last message" in stdout or "No tool call detected in last message" in stderr:
            if profile.invoked == "yes":
                return "FAIL", "yes", 0, expected, observed
            return "NO_TOOL_CALL", profile.invoked, 0, expected, observed
        if profile.invoked != "no" or "System:" in stdout:
            return "FAIL", profile.invoked, 0, expected, observed
        return "FAIL", "no", 0, expected, observed

    def run_case(
        self,
        case: CaseDefinition,
        model_spec: ModelSpec,
        test_spec: TestSpec,
        command_runner: CommandRunner | None = None,
    ):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "artifacts").mkdir(exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")

        warmup_stdout = case.case_dir / "warmup.stdout"
        warmup_stderr = case.case_dir / "warmup.stderr"
        measured_stdout = case.case_dir / "measured.stdout"
        measured_stderr = case.case_dir / "measured.stderr"

        tool_list = ",".join(case.allowed_tools or self.cli_agent_spec.default_tools)
        base_args = [
            self.cli_agent_spec.executable,
            *self.cli_agent_spec.default_args,
            "--name",
            f"{case.case_id}-warmup",
            "--workspace",
            str(case.workspace_dir),
            "--tools",
            tool_list,
            "--tool-format",
            case.tool_format,
            "-m",
            case.cli_agent_model_id,
            case.prompt,
        ]
        system_mode = self._resolve_system_mode(model_spec)
        if system_mode == "custom":
            custom_prompt = self._resolve_custom_system_prompt(model_spec)
            base_args[base_args.index("--workspace"):base_args.index("--workspace")] = ["--system", custom_prompt]
        elif system_mode != "off":
            base_args[base_args.index("--workspace"):base_args.index("--workspace")] = ["--system", system_mode]
        context_include = self._resolve_context_include(model_spec)
        if context_include:
            base_args[base_args.index("--workspace"):base_args.index("--workspace")] = ["--context", context_include]

        env = os.environ.copy()
        env.update(self.cli_agent_spec.env)
        self._apply_case_backend_env_overrides(case, env)
        self._ensure_ollama_openai_env(case, env)
        warmup_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "measured")
        warmup_args = base_args.copy()
        warmup_args[warmup_args.index(str(case.workspace_dir))] = str(case.warmup_workspace_dir)
        warmup_env = {
            **env,
            **warmup_runtime_env,
            "GPTME_LOGS_HOME": str(Path(warmup_runtime_env["XDG_STATE_HOME"]) / "gptme-logs"),
            "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir),
        }
        measured_env = {
            **env,
            **measured_runtime_env,
            "GPTME_LOGS_HOME": str(Path(measured_runtime_env["XDG_STATE_HOME"]) / "gptme-logs"),
            "GRIPPROBE_WORKSPACE": str(case.workspace_dir),
        }
        measured_args = base_args.copy()
        measured_args[measured_args.index(f"{case.case_id}-warmup")] = f"{case.case_id}-measured"
        warmup_command = self._command_text(case, warmup_args, warmup_env, workspace_dir=case.warmup_workspace_dir)
        measured_command = self._command_text(case, measured_args, measured_env, workspace_dir=case.workspace_dir)

        warmup_rc, warmup_s, warmup_started_at, warmup_finished_at = self._run_case_command(
            command_runner,
            case=case,
            args=warmup_args,
            env=warmup_env,
            stdout_path=warmup_stdout,
            stderr_path=warmup_stderr,
            workspace_dir=case.warmup_workspace_dir,
        )

        measured_rc, measured_s, measured_started_at, measured_finished_at = self._run_case_command(
            command_runner,
            case=case,
            args=measured_args,
            env=measured_env,
            stdout_path=measured_stdout,
            stderr_path=measured_stderr,
            workspace_dir=case.workspace_dir,
        )

        stdout_text = measured_stdout.read_text(encoding="utf-8", errors="replace") if measured_stdout.exists() else ""
        stderr_text = measured_stderr.read_text(encoding="utf-8", errors="replace") if measured_stderr.exists() else ""
        warmup_stdout_text = warmup_stdout.read_text(encoding="utf-8", errors="replace") if warmup_stdout.exists() else ""
        warmup_stderr_text = warmup_stderr.read_text(encoding="utf-8", errors="replace") if warmup_stderr.exists() else ""
        run_1_profile = analyze_trace(warmup_stdout_text, warmup_stderr_text)
        run_2_profile = analyze_trace(stdout_text, stderr_text)
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)

        status: CaseStatus
        invoked: ToolInvocation
        trajectory: Trajectory = "clean"
        run_consistency: RunConsistency
        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status = "TIMEOUT"
            invoked = run_2_profile.invoked
            match_percent = 100 if validators_ok else 0
            expected = validators_expected
            observed = validators_observed
            trajectory = derive_trajectory(run_2_profile, test_spec.rules.no_retry_on_error, stdout_text, stderr_text)
        else:
            status, invoked, match_percent, expected, observed = self._classify(test_spec, case.workspace_dir, stdout_text, stderr_text)
            trajectory = derive_trajectory(run_2_profile, test_spec.rules.no_retry_on_error, stdout_text, stderr_text)
        trajectory_reasons = explain_trajectory(
            trajectory,
            run_2_profile,
            test_spec.rules.no_retry_on_error,
            stdout_text,
            stderr_text,
        )
        failure_reason = infer_failure_reason(status, invoked, stdout_text, stderr_text)
        run_1_status = infer_trace_status(run_1_profile, warmup_stdout_text, warmup_stderr_text, timed_out=warmup_rc == 124)
        run_consistency = compare_profiles(run_1_profile, run_2_profile, run_1_status, status)

        (case.case_dir / "expected.txt").write_text(expected + ("\n" if expected else ""), encoding="utf-8")
        (case.case_dir / "observed.txt").write_text(observed + ("\n" if observed else ""), encoding="utf-8")
        if not case.keep_system_messages:
            strip_system_messages_from_transcripts(case.case_dir)
        remove_transient_files(case.case_dir)

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status=status,
            trajectory=trajectory,
            invoked=invoked,
            match_percent=match_percent,
            warmup_seconds=warmup_s,
            measured_seconds=measured_s,
            metadata={
                "warmup_exit_code": warmup_rc,
                "warmup_started_at": warmup_started_at,
                "warmup_finished_at": warmup_finished_at,
                "measured_exit_code": measured_rc,
                "measured_started_at": measured_started_at,
                "measured_finished_at": measured_finished_at,
                "tool_format": case.tool_format,
                "allowed_tools": case.allowed_tools,
                "warmup_command": warmup_command,
                "measured_command": measured_command,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "run_1_status": run_1_status,
                "run_2_status": status,
                "run_1_profile": run_1_profile.as_metadata(),
                "run_2_profile": run_2_profile.as_metadata(),
                "run_consistency": run_consistency,
                "language": test_spec.language,
                "rules": test_spec.rules.model_dump(),
                "trajectory_reasons": trajectory_reasons,
                "failure_reason": failure_reason,
                **case.run_metadata,
            },
        )
