from __future__ import annotations

from pathlib import Path

from gripprobe.spec_loader import load_test_specs
from gripprobe.trace_analysis import analyze_trace, derive_trajectory


def test_multilingual_specs_load_with_language_and_rules(specs_root: Path) -> None:
    specs = {spec.id: spec for spec in load_test_specs(specs_root)}

    assert specs["python_file_de"].language == "de"
    assert specs["python_file_de"].rules.no_retry_on_error is True
    assert specs["python_file_ru"].language == "ru"
    assert specs["python_file_ru"].rules.require_exact_command is True
    assert specs["shell_date_de"].language == "de"
    assert specs["shell_date_de"].validators[0].expected_from == "today"
    assert specs["shell_date_ru"].language == "ru"
    assert specs["shell_date_ru"].rules.no_retry_on_error is True


def test_trajectory_violation_uses_structured_rules_not_english_prompt(specs_root: Path) -> None:
    spec = {spec.id: spec for spec in load_test_specs(specs_root)}["python_file_ru"]
    stdout = (
        "@shell(call_1): {\"command\":\"broken\"}\n"
        "System: Error during execution: Shell error: syntax error\n"
        "@shell(call_2): {\"command\":\"fixed\"}\n"
        "System:\nRan command: `fixed`\n"
    )

    trajectory = derive_trajectory(analyze_trace(stdout, ""), spec.rules.no_retry_on_error, stdout, "")

    assert trajectory == "violated"


def test_non_sanity_tag_marks_all_non_sanity_specs(specs_root: Path) -> None:
    specs = load_test_specs(specs_root)

    for spec in specs:
        has_sanity = "sanity" in spec.tags
        has_non_sanity = "non_sanity" in spec.tags
        if has_sanity:
            assert not has_non_sanity, f"{spec.id} should not have both sanity and non_sanity tags"
        else:
            assert has_non_sanity, f"{spec.id} is missing non_sanity tag"
