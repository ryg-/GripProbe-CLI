from __future__ import annotations

import os
from pathlib import Path

from gripprobe.adapters.base import ShellAdapter
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


class GptmeAdapter(ShellAdapter):
    @staticmethod
    def _normalize_http_base(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raw = "http://127.0.0.1:11434"
        if "://" not in raw:
            raw = f"http://{raw}"
        return raw.rstrip("/")

    def _ensure_ollama_openai_env(self, case: CaseDefinition, env: dict[str, str]) -> None:
        if case.backend_id != "ollama":
            return
        if not env.get("OPENAI_BASE_URL"):
            ollama_host = env.get("OLLAMA_HOST", "http://127.0.0.1:11434")
            env["OPENAI_BASE_URL"] = f"{self._normalize_http_base(ollama_host)}/v1"
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

    def run_case(self, case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "artifacts").mkdir(exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")

        warmup_stdout = case.case_dir / "warmup.stdout"
        warmup_stderr = case.case_dir / "warmup.stderr"
        measured_stdout = case.case_dir / "measured.stdout"
        measured_stderr = case.case_dir / "measured.stderr"

        tool_list = ",".join(case.allowed_tools or self.shell_spec.default_tools)
        base_args = [
            self.shell_spec.executable,
            *self.shell_spec.default_args,
            "--name",
            f"{case.case_id}-warmup",
            "--system",
            "short",
            "--workspace",
            str(case.workspace_dir),
            "--tools",
            tool_list,
            "--tool-format",
            case.tool_format,
            "-m",
            case.shell_model_id,
            case.prompt,
        ]

        env = os.environ.copy()
        env.update(self.shell_spec.env)
        self._ensure_ollama_openai_env(case, env)
        warmup_runtime_env = self._prepare_runtime_dirs(case, self.shell_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.shell_spec.id, "measured")
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

        warmup_rc, warmup_s, warmup_started_at, warmup_finished_at = self.run_command(
            case,
            warmup_args,
            warmup_env,
            warmup_stdout,
            warmup_stderr,
            workspace_dir=case.warmup_workspace_dir,
        )

        measured_rc, measured_s, measured_started_at, measured_finished_at = self.run_command(
            case,
            measured_args,
            measured_env,
            measured_stdout,
            measured_stderr,
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
