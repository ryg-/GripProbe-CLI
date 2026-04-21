from __future__ import annotations

from gripprobe.models import TestSpec as GripTestSpec
from gripprobe.runner import _filter_tests, _filter_tests_by_tags


def _spec(test_id: str, title: str, tags: list[str]) -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": test_id,
            "title": title,
            "category": "shell",
            "prompt": "test",
            "tags": tags,
            "validators": [
                {
                    "type": "file_equals",
                    "target": "x.txt",
                    "expected": "x",
                }
            ],
        }
    )


def test_filter_tests_by_tags_keeps_matching_specs() -> None:
    tests = [
        _spec("shell_pwd", "Shell PWD", ["mvp", "sanity"]),
        _spec("shell_file", "Shell File", ["mvp"]),
        _spec("python_file_simple", "Python File Simple", ["sanity"]),
    ]

    filtered = _filter_tests_by_tags(tests, ["sanity"])

    assert [item.id for item in filtered] == ["shell_pwd", "python_file_simple"]


def test_filter_tests_and_tags_compose() -> None:
    tests = [
        _spec("shell_pwd", "Shell PWD", ["mvp", "sanity"]),
        _spec("shell_file", "Shell File", ["mvp"]),
        _spec("python_file_simple", "Python File Simple", ["sanity"]),
    ]

    filtered = _filter_tests_by_tags(_filter_tests(tests, ["shell_pwd", "shell_file"]), ["sanity"])

    assert [item.id for item in filtered] == ["shell_pwd"]
