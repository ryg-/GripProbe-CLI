from __future__ import annotations

import os
from pathlib import Path

from gripprobe.adapters.base import ShellAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.validator_runner import evaluate_validators


class GptmeAdapter(ShellAdapter):
    def _classify(self, test_spec: TestSpec, workspace: Path, stdout: str, stderr: str) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        if "No tool call detected in last message" in stdout or "No tool call detected in last message" in stderr:
            return "NO_TOOL_CALL", "no", 0, expected, observed
        if "System:" in stdout or "Ran command:" in stdout or "Preview" in stdout:
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
        env["GRIPPROBE_WORKSPACE"] = str(case.workspace_dir)
        env["GPTME_LOGS_HOME"] = str(case.case_dir / "gptme-logs")

        warmup_rc, warmup_s = self.run_command(case, base_args, env, warmup_stdout, warmup_stderr)

        measured_args = base_args.copy()
        measured_args[measured_args.index(f"{case.case_id}-warmup")] = f"{case.case_id}-measured"
        measured_rc, measured_s = self.run_command(case, measured_args, env, measured_stdout, measured_stderr)

        stdout_text = measured_stdout.read_text(encoding="utf-8", errors="replace") if measured_stdout.exists() else ""
        stderr_text = measured_stderr.read_text(encoding="utf-8", errors="replace") if measured_stderr.exists() else ""

        status: CaseStatus
        invoked: ToolInvocation
        if measured_rc == 124:
            status, invoked, match_percent, expected, observed = "TIMEOUT", "no", 0, "", ""
        else:
            status, invoked, match_percent, expected, observed = self._classify(test_spec, case.workspace_dir, stdout_text, stderr_text)

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
                "measured_exit_code": measured_rc,
                "tool_format": case.tool_format,
                "allowed_tools": case.allowed_tools,
            },
        )
