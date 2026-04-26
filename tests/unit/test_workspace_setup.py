from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from gripprobe.runner import _prepare_workspace


def test_prepare_workspace_seeds_patch_target_for_patch_file(tmp_path: Path) -> None:
    _prepare_workspace(tmp_path, "patch_file")

    assert (tmp_path / "patch-target.txt").read_text(encoding="utf-8") == "STATUS=old\n"


def test_prepare_workspace_seeds_patch_target_and_patch_file_for_prepared_patch_case(tmp_path: Path) -> None:
    _prepare_workspace(tmp_path, "patch_file_prepared")

    assert (tmp_path / "patch-target.txt").read_text(encoding="utf-8") == "STATUS=old\n"
    assert (tmp_path / "prepared.patch").read_text(encoding="utf-8") == (
        "<<<<<<< ORIGINAL\n"
        "STATUS=old\n"
        "=======\n"
        "STATUS=new\n"
        ">>>>>>> UPDATED\n"
    )


def test_prepare_workspace_seeds_plan_template_for_weekly_plan_scenario(tmp_path: Path) -> None:
    _prepare_workspace(tmp_path, "weekly_plan_next_week")

    current_monday = date.today() - timedelta(days=date.today().weekday())
    next_monday = current_monday + timedelta(days=7)
    assert (tmp_path / "Plan.md").read_text(encoding="utf-8") == (
        "# Plan\n\n"
        f"## Week of {current_monday.isoformat()}\n"
        "- [ ] Carry over outstanding items\n\n"
        f"## Week of {next_monday.isoformat()}\n"
        "- [ ] Placeholder for planning\n\n"
        "## Monthly Summary\n"
        "- [ ] No entries yet\n"
    )


def test_prepare_workspace_seeds_json_ranking_fixture(tmp_path: Path) -> None:
    _prepare_workspace(tmp_path, "json_rank_from_file")

    assert (tmp_path / "query.txt").read_text(encoding="utf-8") == "weekly plan static fixture checkbox\n"
    assert (tmp_path / "required-token.txt").read_text(encoding="utf-8") == "static-token-abc123\n"
    assert "doc-static-top" in (tmp_path / "search-response.json").read_text(encoding="utf-8")
