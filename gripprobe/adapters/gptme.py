from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from gripprobe.adapters.base import ShellAdapter
from gripprobe.case_result import CaseStatus, ToolInvocation, build_case_result
from gripprobe.models import CaseDefinition, ModelSpec, TestSpec
from gripprobe.results import remove_transient_files, strip_system_messages_from_transcripts
from gripprobe.validator_runner import evaluate_validators


Trajectory = Literal["clean", "recovered", "violated"]


def _derive_trajectory(test_spec: TestSpec, stdout: str, stderr: str, status: CaseStatus) -> Trajectory:
    combined = f"{stdout}\n{stderr}"
    error_markers = (
        "Error during execution:",
        "Shell error:",
        "Invalid patch:",
    )
    had_error = any(marker in combined for marker in error_markers)
    if not had_error:
        return "clean"
    if status != "PASS":
        return "recovered"
    if "Do not retry on error." in test_spec.prompt:
        after_error = combined.split("Error during execution:", 1)[1] if "Error during execution:" in combined else combined
        if any(marker in after_error for marker in ("@shell(", "@patch(", "@read(", "@save(")):
            return "violated"
    return "recovered"


class GptmeAdapter(ShellAdapter):
    @staticmethod
    def _saw_tool_activity(stdout: str, stderr: str) -> bool:
        haystacks = (stdout, stderr)
        markers = (
            "@patch(",
            "@shell(",
            "@read(",
            "@save(",
            "Error during execution:",
            "Ran command:",
            "Preview",
        )
        return any(marker in text for text in haystacks for marker in markers)

    def _classify(self, test_spec: TestSpec, workspace: Path, stdout: str, stderr: str) -> tuple[CaseStatus, ToolInvocation, int, str, str]:
        if "does not support tools" in stdout or "does not support tools" in stderr:
            return "TOOL_UNSUPPORTED", "no", 0, "", ""
        ok, expected, observed = evaluate_validators(test_spec, workspace)
        if ok:
            return "PASS", "yes", 100, expected, observed
        saw_tool_activity = self._saw_tool_activity(stdout, stderr)
        if "No tool call detected in last message" in stdout or "No tool call detected in last message" in stderr:
            if saw_tool_activity:
                return "FAIL", "yes", 0, expected, observed
            return "NO_TOOL_CALL", "no", 0, expected, observed
        if saw_tool_activity or "System:" in stdout:
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
        trajectory: Trajectory = "clean"
        if measured_rc == 124:
            status, invoked, match_percent, expected, observed = "TIMEOUT", "no", 0, "", ""
        else:
            status, invoked, match_percent, expected, observed = self._classify(test_spec, case.workspace_dir, stdout_text, stderr_text)
            trajectory = _derive_trajectory(test_spec, stdout_text, stderr_text, status)

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
                    "measured_exit_code": measured_rc,
                    "tool_format": case.tool_format,
                    "allowed_tools": case.allowed_tools,
                    **case.run_metadata,
                },
        )
