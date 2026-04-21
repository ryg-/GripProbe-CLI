from __future__ import annotations

import pytest

from gripprobe.cli import _parse_metadata, build_parser


def test_parse_metadata_accepts_multiple_key_value_entries() -> None:
    assert _parse_metadata(["venv=/tmp/venv", "launcher=pipx"]) == {
        "venv": "/tmp/venv",
        "launcher": "pipx",
    }


def test_parse_metadata_rejects_invalid_entries() -> None:
    with pytest.raises(ValueError, match="expected key=value"):
        _parse_metadata(["broken"])


def test_run_parser_accepts_sanity_flag() -> None:
    parser = build_parser()

    ns = parser.parse_args(
        [
            "run",
            "--shell",
            "continue-cli",
            "--model",
            "local/qwen3:8b",
            "--sanity",
        ]
    )

    assert ns.cmd == "run"
    assert ns.sanity is True


def test_run_parser_exposes_model_hash_as_optional_fallback_help() -> None:
    parser = build_parser()
    subparsers = next(action for action in parser._actions if getattr(action, "choices", None))
    run_parser = subparsers.choices["run"]
    help_text = run_parser.format_help()

    assert "--model-hash" in help_text
    assert "fallback model hash" in help_text
    assert "/api/tags" in help_text
