from __future__ import annotations

import os
from pathlib import Path

from gripprobe.adapters.base import ShellAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.failure_reason import infer_failure_reason
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class AiderAdapter(ShellAdapter):
    def _prepare_aider_home(self, case: CaseDefinition) -> tuple[Path, Path]:
        aider_home = case.case_dir / "aider-home"
        aider_home.mkdir(parents=True, exist_ok=True)
        config_path = aider_home / ".aider.conf.yml"
        config_path.write_text(
            "\n".join(
                [
                    "git: false",
                    "auto-commits: false",
                    "dirty-commits: false",
                    "analytics: false",
                    "check-update: false",
                    "show-release-notes: false",
                    "fancy-input: false",
                    "pretty: false",
                    "stream: false",
                    "suggest-shell-commands: false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return aider_home, config_path

    def _model_name(self, case: CaseDefinition) -> str:
        if case.backend_id == "ollama":
            return f"ollama/{case.backend_model_id}"
        return case.shell_model_id

    def _base_args(self, case: CaseDefinition, config_path: Path, workspace_dir: Path) -> list[str]:
        args = [
            self.shell_spec.executable,
            "--config",
            str(config_path),
            "--no-git",
            "--yes-always",
            "--no-auto-commits",
            "--no-dirty-commits",
            "--no-check-update",
            "--analytics-disable",
            "--no-fancy-input",
            "--no-pretty",
            "--no-stream",
            "--no-suggest-shell-commands",
            "--model",
            self._model_name(case),
            "--message",
            case.prompt,
        ]
        if case.backend_id == "ollama":
            api_base = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
            args[1:1] = ["--openai-api-base", f"{api_base}/v1"]
        for path in sorted(workspace_dir.iterdir()):
            if path.is_file():
                args.append(path.name)
        return args

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
            return "PASS", "maybe", 100, expected, observed
        combined = f"{stdout}\n{stderr}"
        if "Applied edit to" in combined or "Added " in combined or "Creating empty file" in combined:
            return "FAIL", "maybe", 0, expected, observed
        return "FAIL", "no", 0, expected, observed

    def run_case(self, case: CaseDefinition, model_spec: ModelSpec, test_spec: TestSpec):
        case.case_dir.mkdir(parents=True, exist_ok=True)
        (case.case_dir / "artifacts").mkdir(exist_ok=True)
        (case.case_dir / "prompt.txt").write_text(case.prompt, encoding="utf-8")

        warmup_stdout = case.case_dir / "warmup.stdout"
        warmup_stderr = case.case_dir / "warmup.stderr"
        measured_stdout = case.case_dir / "measured.stdout"
        measured_stderr = case.case_dir / "measured.stderr"

        aider_home, config_path = self._prepare_aider_home(case)
        env = os.environ.copy()
        env.update(self.shell_spec.env)
        shared_env = {
            **env,
            "HOME": str(aider_home),
            "AIDER_ANALYTICS": "false",
            "AIDER_CHECK_UPDATE": "false",
            "AIDER_SHOW_RELEASE_NOTES": "false",
            "AIDER_AUTO_COMMITS": "false",
            "AIDER_DIRTY_COMMITS": "false",
        }
        warmup_env = {**shared_env, "GRIPPROBE_WORKSPACE": str(case.warmup_workspace_dir)}
        measured_env = {**shared_env, "GRIPPROBE_WORKSPACE": str(case.workspace_dir)}
        warmup_args = self._base_args(case, config_path, case.warmup_workspace_dir)
        measured_args = self._base_args(case, config_path, case.workspace_dir)

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
        validators_ok, validators_expected, validators_observed = evaluate_validators(test_spec, case.workspace_dir)

        artifact_reached_before_timeout = False
        if measured_rc == 124:
            artifact_reached_before_timeout = validators_ok
            status: CaseStatus = "TIMEOUT"
            invoked: ToolInvocation = "maybe" if validators_ok else "no"
            match_percent = 100 if validators_ok else 0
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
                "allowed_tools": case.allowed_tools or self.shell_spec.default_tools,
                "model_selection": "cli-model",
                "model_hash": case.model_hash,
                "artifact_reached_before_timeout": artifact_reached_before_timeout,
                "aider_config_path": str(config_path),
                "failure_reason": failure_reason,
            },
        )
