from __future__ import annotations

from pathlib import Path

from gripprobe.adapters.gptme import GptmeAdapter, _derive_trajectory
from gripprobe.models import ShellSpec, TestSpec as GripTestSpec


def _adapter() -> GptmeAdapter:
    return GptmeAdapter(
        ShellSpec.model_validate(
            {
                "id": "gptme",
                "label": "gptme",
                "executable": "gptme",
                "supported_formats": ["tool"],
            }
        )
    )


def _patch_test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "patch_file",
            "title": "Patch File",
            "category": "patch",
            "prompt": "patch",
            "validators": [
                {
                    "type": "patch_applied",
                    "target_file": "patch-target.txt",
                    "expected_line": "STATUS=new",
                }
            ],
        }
    )


def _python_test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "python_file",
            "title": "Python File",
            "category": "python",
            "prompt": (
                "Use the shell tool. Run exactly this command: python3 -c \"from pathlib import Path; "
                "Path('python-output.txt').write_text('PYTHON_OK\\\\n')\".\n"
                "Do not retry on error.\n"
                "If the command fails, reply only with FAIL.\n"
                "If the command succeeds, reply only with DONE.\n"
            ),
            "validators": [
                {
                    "type": "file_equals",
                    "target": "python-output.txt",
                    "expected": "PYTHON_OK",
                }
            ],
        }
    )


def test_classify_reports_fail_when_tool_call_happened_but_patch_failed(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _patch_test_spec()
    (tmp_path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "@patch(call_1): {}\nSystem: Error during execution: Invalid patch\n"
        "No tool call detected in last message\n",
        "",
    )

    assert status == "FAIL"
    assert invoked == "yes"
    assert match_percent == 0
    assert expected == "STATUS=new"
    assert observed == "STATUS=old"


def test_classify_reports_no_tool_call_when_no_tool_activity_happened(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _patch_test_spec()
    (tmp_path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "FAIL\nNo tool call detected in last message\n",
        "",
    )

    assert status == "NO_TOOL_CALL"
    assert invoked == "no"
    assert match_percent == 0
    assert expected == "STATUS=new"
    assert observed == "STATUS=old"


def test_trajectory_marks_retry_after_error_as_violated_when_passed(tmp_path: Path) -> None:
    spec = _python_test_spec()
    (tmp_path / "python-output.txt").write_text("PYTHON_OK\n", encoding="utf-8")

    trajectory = _derive_trajectory(
        spec,
        "@shell(call_1): {\"command\":\"broken\"}\n"
        "System: Error during execution: Shell error: syntax error\n"
        "@shell(call_2): {\"command\":\"fixed\"}\n"
        "System:\nRan command: `fixed`\n",
        "",
        "PASS",
    )

    assert trajectory == "violated"
