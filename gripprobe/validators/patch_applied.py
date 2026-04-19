from __future__ import annotations

from pathlib import Path

from gripprobe.models import ValidatorSpec


def validate_patch_applied(spec: ValidatorSpec, workspace: Path) -> tuple[bool, str, str]:
    if spec.target_file is None or spec.expected_line is None:
        return False, "", ""
    target = workspace / spec.target_file
    if not target.exists():
        return False, spec.expected_line, ""
    observed = target.read_text(encoding="utf-8", errors="replace").replace("\r", "").strip("\n")
    return observed == spec.expected_line, spec.expected_line, observed
