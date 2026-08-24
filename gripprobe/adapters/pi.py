from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gripprobe.adapters.base import CliAgentAdapter
from gripprobe.command_runner import CommandRunner
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class PiAdapter(CliAgentAdapter):
    @staticmethod
    def _pi_policy(model_spec: ModelSpec) -> dict[str, Any]:
        cli_agent_options = (model_spec.policy_overrides or {}).get("cli_agent_options")
        if not isinstance(cli_agent_options, dict):
            return {}
        options = cli_agent_options.get("pi")
        return options if isinstance(options, dict) else {}

    def _resolve_system_prompt(self, model_spec: ModelSpec) -> str | None:
        value = self._pi_policy(model_spec).get("system_prompt")
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    @classmethod
    def _policy_flag(cls, model_spec: ModelSpec, key: str, default: bool = False) -> bool:
        value = cls._pi_policy(model_spec).get(key)
        if isinstance(value, bool):
            return value
        return default

    def _prepare_pi_home(
        self,
        case: CaseDefinition,
        runtime_env: dict[str, str],
        base_env: dict[str, str],
        phase: str,
    ) -> Path:
        home_dir = Path(runtime_env["HOME"])
        agent_dir = home_dir / ".pi" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)

        base_url = self._resolve_case_openai_base_url_for_phase(case, base_env, phase)
        models_payload = {
            "providers": {
                "ollama": {
                    "baseUrl": base_url,
                    "api": "openai-completions",
                    "apiKey": "ollama",
                    "authHeader": True,
                    "models": [
                        {
                            "id": case.backend_model_id,
                            "name": case.model_label,
                        }
                    ],
                }
            }
        }
        (agent_dir / "models.json").write_text(
            json.dumps(models_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return agent_dir

    @staticmethod
    def _pi_tools(allowed_tools: list[str]) -> list[str]:
        mapping = {
            "shell": "bash",
            "read": "read",
            "patch": "edit",
            "save": "write",
            "write": "write",
        }
        result: list[str] = []
        for tool in allowed_tools:
            mapped = mapping.get(tool)
            if mapped and mapped not in result:
                result.append(mapped)
        return result

    @staticmethod
    def _infer_invoked(stdout: str, stderr: str) -> ToolInvocation:
        combined = f"{stdout}\n{stderr}"
        if any(marker in combined for marker in ('"type":"command_execution"', '"type":"tool_use"', '"type":"tool_call"')):
            return "yes"
        if any(marker in combined for marker in ('"type":"reasoning"', "I'll use", "I need to use")):
            return "maybe"
        return "no"

    def _classify(
        self,
        test_spec: TestSpec,
        workspace: Path,
        stdout: str,
        stderr: str,
    ) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        invoked = self._infer_invoked(stdout, stderr)
        if invoked == "no":
            return "NO_TOOL_CALL", invoked, 0, expected, observed
        return "FAIL", invoked, 0, expected, observed

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

        env = os.environ.copy()
        env.update(self.cli_agent_spec.env)
        self._apply_case_backend_env_overrides(case, env)

        warmup_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "warmup")
        measured_runtime_env = self._prepare_runtime_dirs(case, self.cli_agent_spec.id, "measured")
        warmup_agent_dir = self._prepare_pi_home(case, warmup_runtime_env, env, "warmup")
        measured_agent_dir = self._prepare_pi_home(case, measured_runtime_env, env, "measured")

        warmup_env = {**env, **warmup_runtime_env, "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir)}
        measured_env = {**env, **measured_runtime_env, "GRIPPROBE_WORKSPACE": str(case.workspace_dir)}
        if self._policy_flag(model_spec, "skip_version_check"):
            warmup_env["PI_SKIP_VERSION_CHECK"] = "1"
            measured_env["PI_SKIP_VERSION_CHECK"] = "1"
        if "telemetry_enabled" in self._pi_policy(model_spec):
            telemetry_enabled = self._policy_flag(model_spec, "telemetry_enabled", default=True)
            warmup_env["PI_TELEMETRY"] = "1" if telemetry_enabled else "0"
            measured_env["PI_TELEMETRY"] = "1" if telemetry_enabled else "0"

        pi_tools = self._pi_tools(case.allowed_tools or self.cli_agent_spec.default_tools)
        base_args = [
            self.cli_agent_spec.executable,
            "--mode",
            "json",
            "--provider",
            "ollama",
            "--model",
            case.backend_model_id,
            "--tools",
            ",".join(pi_tools),
            "--no-context-files",
            "--no-skills",
            "--no-extensions",
            "--no-prompt-templates",
        ]
        if self._policy_flag(model_spec, "offline"):
            base_args.append("--offline")
        system_prompt = self._resolve_system_prompt(model_spec)
        if system_prompt:
            base_args.extend(["--system-prompt", system_prompt])

        warmup_args = [*base_args, case.prompt]
        measured_args = [*base_args, case.prompt]
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
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)

        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status: CaseStatus = "TIMEOUT"
            invoked = "yes" if validators_ok else self._infer_invoked(stdout_text, stderr_text)
            match_percent = 100 if validators_ok else 0
            expected = validators_expected
            observed = validators_observed
        elif measured_rc != 0:
            status = "SHELL_ERROR"
            invoked = self._infer_invoked(stdout_text, stderr_text)
            match_percent = 0
            expected = validators_expected
            observed = validators_observed
        else:
            status, invoked, match_percent, expected, observed = self._classify(
                test_spec,
                case.workspace_dir,
                stdout_text,
                stderr_text,
            )
        failure_reason = infer_failure_reason(status, invoked, stdout_text, stderr_text)

        (case.case_dir / "expected.txt").write_text(expected + ("\n" if expected else ""), encoding="utf-8")
        (case.case_dir / "observed.txt").write_text(observed + ("\n" if observed else ""), encoding="utf-8")

        return build_case_result(
            case=case,
            model_spec=model_spec,
            test_spec=test_spec,
            status=status,
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
                "allowed_tools": case.allowed_tools or self.cli_agent_spec.default_tools,
                "pi_tools": pi_tools,
                "warmup_command": warmup_command,
                "measured_command": measured_command,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "pi_models_warmup_path": str(warmup_agent_dir / "models.json"),
                "pi_models_measured_path": str(measured_agent_dir / "models.json"),
                "failure_reason": failure_reason,
                **case.run_metadata,
            },
        )
