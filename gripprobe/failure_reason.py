from __future__ import annotations

from gripprobe.case_result import CaseStatus, ToolInvocation


def infer_failure_reason(status: CaseStatus, invoked: ToolInvocation, stdout: str, stderr: str) -> str | None:
    combined = f"{stdout}\n{stderr}"
    completion_lines = {line.strip() for line in combined.splitlines() if line.strip() in {"DONE", "FAIL"}}
    if status == "TOOL_UNSUPPORTED" or "does not support tools" in combined:
        return "tool unsupported by backend"
    if status in {"FAIL", "NO_TOOL_CALL"} and invoked == "no" and completion_lines:
        return "answered without invoking tool"
    return None
