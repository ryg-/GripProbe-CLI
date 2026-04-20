from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Literal


ToolInvocation = Literal["yes", "no", "maybe"]
Trajectory = Literal["clean", "recovered", "violated"]
RunConsistency = Literal["consistent", "diverged", "strongly_diverged"]
TraceStatus = Literal["FAIL", "TIMEOUT", "NO_TOOL_CALL", "TOOL_UNSUPPORTED", "HARNESS_ERROR"]

ACTUAL_TOOL_MARKERS = ("@shell(", "@patch(", "@read(", "@save(")
MAYBE_TOOL_MARKERS = ("Preview", "```patch", "```bash", "```sh", "```shell")
ERROR_PATTERN = re.compile(r"Error during execution:\s*(.+)")


@dataclass(frozen=True)
class TraceProfile:
    invoked: ToolInvocation
    tool_attempt_count: int
    error_count: int
    dominant_error: str | None
    repeated_error_count: int
    loop_detected: bool
    contradictory_completion_text: bool
    markdown_tool_imitation: bool
    no_tool_call_after_completion: bool

    def as_metadata(self) -> dict[str, str | int | bool]:
        payload: dict[str, str | int | bool] = {
            "invoked": self.invoked,
            "tool_attempt_count": self.tool_attempt_count,
            "error_count": self.error_count,
            "repeated_error_count": self.repeated_error_count,
            "loop_detected": self.loop_detected,
            "contradictory_completion_text": self.contradictory_completion_text,
            "markdown_tool_imitation": self.markdown_tool_imitation,
            "no_tool_call_after_completion": self.no_tool_call_after_completion,
        }
        if self.dominant_error:
            payload["dominant_error"] = self.dominant_error
        return payload


def analyze_trace(stdout: str, stderr: str) -> TraceProfile:
    combined = f"{stdout}\n{stderr}"
    actual_calls = sum(combined.count(marker) for marker in ACTUAL_TOOL_MARKERS)
    successful_execs = combined.count("Ran command:")
    error_lines = [line.strip() for line in ERROR_PATTERN.findall(combined)]
    error_counts = Counter(error_lines)
    dominant_error, repeated_error_count = ("", 0)
    if error_counts:
        dominant_error, repeated_error_count = error_counts.most_common(1)[0]

    invoked: ToolInvocation
    if actual_calls or successful_execs or error_lines:
        invoked = "yes"
    elif any(marker in combined for marker in MAYBE_TOOL_MARKERS):
        invoked = "maybe"
    else:
        invoked = "no"

    tool_attempt_count = actual_calls + successful_execs + len(error_lines)
    loop_detected = repeated_error_count >= 3
    completion_lines = [line.strip() for line in combined.splitlines() if line.strip() in {"DONE", "FAIL"}]
    contradictory_completion_text = "DONE" in completion_lines and "FAIL" in completion_lines
    markdown_tool_imitation = invoked == "maybe" and any(marker in combined for marker in ("```bash", "```sh", "```shell"))
    no_tool_call_after_completion = (
        "No tool call detected in last message" in combined and bool(completion_lines)
    )
    return TraceProfile(
        invoked=invoked,
        tool_attempt_count=tool_attempt_count,
        error_count=len(error_lines),
        dominant_error=dominant_error or None,
        repeated_error_count=repeated_error_count,
        loop_detected=loop_detected,
        contradictory_completion_text=contradictory_completion_text,
        markdown_tool_imitation=markdown_tool_imitation,
        no_tool_call_after_completion=no_tool_call_after_completion,
    )


def derive_trajectory(profile: TraceProfile, no_retry_on_error: bool, stdout: str, stderr: str) -> Trajectory:
    if (
        profile.error_count == 0
        and not profile.loop_detected
        and not profile.contradictory_completion_text
        and not profile.markdown_tool_imitation
        and not profile.no_tool_call_after_completion
    ):
        return "clean"
    if no_retry_on_error and _has_retry_after_error(stdout, stderr):
        return "violated"
    return "recovered"


def explain_trajectory(trajectory: Trajectory, profile: TraceProfile, no_retry_on_error: bool, stdout: str, stderr: str) -> list[str]:
    reasons: list[str] = []
    if trajectory == "clean":
        reasons.append("no execution errors detected")
        reasons.append("no loop pattern detected")
        reasons.append("no contradictory completion text detected")
        return reasons
    if profile.error_count:
        reasons.append(f"errors detected: {profile.error_count}")
    if profile.loop_detected:
        reasons.append(f"loop pattern detected from repeated errors: {profile.repeated_error_count}")
    if profile.contradictory_completion_text:
        reasons.append("contradictory completion text detected (both DONE and FAIL)")
    if profile.markdown_tool_imitation:
        reasons.append("markdown tool imitation detected without a real tool execution")
    if profile.no_tool_call_after_completion:
        reasons.append("completion text was emitted before harness reported that no tool call was detected")
    if no_retry_on_error and _has_retry_after_error(stdout, stderr):
        reasons.append("retry after error detected while no_retry_on_error rule was enabled")
    if not reasons:
        reasons.append("non-clean execution trace detected")
    return reasons


def compare_profiles(run_1: TraceProfile, run_2: TraceProfile, run_1_status: str, run_2_status: str) -> RunConsistency:
    if (
        run_1_status == run_2_status
        and run_1.invoked == run_2.invoked
        and run_1.loop_detected == run_2.loop_detected
        and run_1.dominant_error == run_2.dominant_error
    ):
        return "consistent"
    if (
        run_1.invoked != run_2.invoked
        or run_1.loop_detected != run_2.loop_detected
        or {run_1_status, run_2_status} == {"NO_TOOL_CALL", "TIMEOUT"}
    ):
        return "strongly_diverged"
    return "diverged"


def infer_trace_status(profile: TraceProfile, stdout: str, stderr: str, timed_out: bool = False) -> TraceStatus:
    combined = f"{stdout}\n{stderr}"
    if timed_out:
        return "TIMEOUT"
    if "does not support tools" in combined:
        return "TOOL_UNSUPPORTED"
    if "No tool call detected in last message" in combined:
        return "NO_TOOL_CALL"
    if profile.invoked != "no" or profile.error_count > 0:
        return "FAIL"
    return "HARNESS_ERROR"


def _has_retry_after_error(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}"
    if "Error during execution:" not in combined:
        return False
    after_error = combined.split("Error during execution:", 1)[1]
    if after_error.count("Error during execution:") >= 1:
        return True
    return any(marker in after_error for marker in (*ACTUAL_TOOL_MARKERS, *MAYBE_TOOL_MARKERS))
