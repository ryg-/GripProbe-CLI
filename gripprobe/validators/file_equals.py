from __future__ import annotations

from datetime import date
from pathlib import Path

from gripprobe.models import ValidatorSpec


def expected_value(spec: ValidatorSpec, workspace: Path) -> str:
    if spec.expected is not None:
        return spec.expected
    if spec.expected_from == "workspace_path":
        return str(workspace)
    if spec.expected_from == "today":
        return date.today().isoformat()
    return ""


def validate_file_equals(spec: ValidatorSpec, workspace: Path) -> tuple[bool, str, str]:
    expected = expected_value(spec, workspace)
    if not spec.target:
        return False, expected, ""
    target_path = workspace / spec.target
    if not target_path.exists():
        return False, expected, ""
    observed = target_path.read_text(encoding="utf-8", errors="replace").replace("\r", "").strip("\n")
    return observed == expected, expected, observed
