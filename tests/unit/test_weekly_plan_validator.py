from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from gripprobe.models import ValidatorSpec
from gripprobe.validators.weekly_plan_task import validate_weekly_plan_task


def _next_week_monday_iso() -> str:
    current_monday = date.today() - timedelta(days=date.today().weekday())
    return (current_monday + timedelta(days=7)).isoformat()


def test_weekly_plan_validator_passes_when_task_is_in_next_week_section(tmp_path: Path) -> None:
    task = "Review onboarding draft at https://example.com/docs/onboarding-v2 and send feedback."
    next_week = _next_week_monday_iso()
    plan = (
        "# Plan\n\n"
        "## Week of 2026-01-05\n"
        "- [ ] Old task\n\n"
        f"## Week of {next_week}\n"
        f"- [ ] {task}\n\n"
        "## Monthly Summary\n"
        "- [ ] No entries yet\n"
    )
    (tmp_path / "Plan.md").write_text(plan, encoding="utf-8")

    spec = ValidatorSpec.model_validate(
        {
            "type": "weekly_plan_task",
            "target": "Plan.md",
            "expected": task,
        }
    )
    ok, expected, observed = validate_weekly_plan_task(spec, tmp_path)

    assert ok is True
    assert f"WEEK_START={next_week}" in expected
    assert f"TASK=- [ ] {task}" in observed


def test_weekly_plan_validator_fails_when_task_is_not_in_next_week_section(tmp_path: Path) -> None:
    task = "Review onboarding draft at https://example.com/docs/onboarding-v2 and send feedback."
    next_week = _next_week_monday_iso()
    wrong_week = (date.fromisoformat(next_week) + timedelta(days=7)).isoformat()
    plan = (
        "# Plan\n\n"
        f"## Week of {next_week}\n"
        "- [ ] Placeholder\n\n"
        f"## Week of {wrong_week}\n"
        f"- [ ] {task}\n"
    )
    (tmp_path / "Plan.md").write_text(plan, encoding="utf-8")

    spec = ValidatorSpec.model_validate(
        {
            "type": "weekly_plan_task",
            "target": "Plan.md",
            "expected": task,
        }
    )
    ok, _expected, observed = validate_weekly_plan_task(spec, tmp_path)

    assert ok is False
    assert "TASK_NOT_FOUND_IN_NEXT_WEEK_SECTION" in observed


def test_weekly_plan_validator_fails_when_task_is_appended_after_monthly_summary(tmp_path: Path) -> None:
    task = "Review onboarding draft at https://example.com/docs/onboarding-v2 and send feedback."
    next_week = _next_week_monday_iso()
    plan = (
        "# Plan\n\n"
        f"## Week of {next_week}\n"
        "- [ ] Placeholder\n\n"
        "## Monthly Summary\n"
        "- [ ] No entries yet\n"
        f"- [ ] {task}\n"
    )
    (tmp_path / "Plan.md").write_text(plan, encoding="utf-8")

    spec = ValidatorSpec.model_validate(
        {
            "type": "weekly_plan_task",
            "target": "Plan.md",
            "expected": task,
        }
    )
    ok, _expected, observed = validate_weekly_plan_task(spec, tmp_path)

    assert ok is False
    assert "TASK_NOT_FOUND_IN_NEXT_WEEK_SECTION" in observed
