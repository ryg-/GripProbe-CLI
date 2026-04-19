from __future__ import annotations

import pytest

from gripprobe.cli import _parse_metadata


def test_parse_metadata_accepts_multiple_key_value_entries() -> None:
    assert _parse_metadata(["venv=/tmp/venv", "launcher=pipx"]) == {
        "venv": "/tmp/venv",
        "launcher": "pipx",
    }


def test_parse_metadata_rejects_invalid_entries() -> None:
    with pytest.raises(ValueError, match="expected key=value"):
        _parse_metadata(["broken"])
