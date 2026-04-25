from __future__ import annotations

from datetime import date, timedelta
import re
from pathlib import Path

from gripprobe.models import ValidatorSpec


WEEK_HEADING = re.compile(r"^\s*##\s+Week of\s+(\d{4}-\d{2}-\d{2})\s*$")
H2_HEADING = re.compile(r"^\s*##\s+")
UNCHECKED_TASK = re.compile(r"^\s*-\s*\[\s*]\s+(.*?)\s*$")


def _next_week_monday(today: date) -> date:
    current_monday = today - timedelta(days=today.weekday())
    return current_monday + timedelta(days=7)


def _normalize_task(text: str) -> str:
    return " ".join(text.strip().split())


def validate_weekly_plan_task(spec: ValidatorSpec, workspace: Path) -> tuple[bool, str, str]:
    if not spec.target or not spec.expected:
        return False, "", ""

    expected_task = _normalize_task(spec.expected)
    expected_week = _next_week_monday(date.today()).isoformat()
    expected = "\n".join(
        [
            f"WEEK_START={expected_week}",
            f"TASK=- [ ] {expected_task}",
        ]
    )

    plan_path = workspace / spec.target
    if not plan_path.exists():
        return False, expected, "MISSING_FILE"

    raw = plan_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.replace("\r", "").splitlines()

    section_start: int | None = None
    section_end = len(lines)
    for idx, line in enumerate(lines):
        match = WEEK_HEADING.match(line)
        if not match:
            continue
        week_date = match.group(1)
        if week_date == expected_week:
            section_start = idx
            for next_idx in range(idx + 1, len(lines)):
                if H2_HEADING.match(lines[next_idx]):
                    section_end = next_idx
                    break
            break

    if section_start is None:
        observed = "\n".join(
            [
                "MISSING_WEEK_SECTION",
                f"EXPECTED_WEEK_START={expected_week}",
            ]
        )
        return False, expected, observed

    observed_task = ""
    for line in lines[section_start + 1 : section_end]:
        match = UNCHECKED_TASK.match(line)
        if not match:
            continue
        candidate = _normalize_task(match.group(1))
        if candidate == expected_task:
            observed_task = candidate
            break

    if not observed_task:
        observed = "\n".join(
            [
                f"WEEK_START={expected_week}",
                "TASK_NOT_FOUND_IN_NEXT_WEEK_SECTION",
            ]
        )
        return False, expected, observed

    observed = "\n".join(
        [
            f"WEEK_START={expected_week}",
            f"TASK=- [ ] {observed_task}",
        ]
    )
    return True, expected, observed
