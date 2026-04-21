from __future__ import annotations

from gripprobe.failure_reason import infer_failure_reason


def test_infer_failure_reason_detects_backend_tool_unsupported() -> None:
    assert (
        infer_failure_reason(
            "TOOL_UNSUPPORTED",
            "no",
            "",
            '{"status":"error","message":"400 model does not support tools"}',
        )
        == "tool unsupported by backend"
    )


def test_infer_failure_reason_detects_answered_without_invoking_tool() -> None:
    assert infer_failure_reason("FAIL", "no", "DONE\n", "") == "answered without invoking tool"


def test_infer_failure_reason_returns_none_for_normal_pass() -> None:
    assert infer_failure_reason("PASS", "yes", "DONE\n", "") is None
