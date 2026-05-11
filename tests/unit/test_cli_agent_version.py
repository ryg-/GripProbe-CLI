from __future__ import annotations

from gripprobe.cli_agent_version import get_cli_agent_version, parse_cli_agent_version, with_cli_agent_version


def test_parse_cli_agent_version_extracts_semver_like_token() -> None:
    assert parse_cli_agent_version("gptme v0.31.0+unknown") == "v0.31.0+unknown"
    assert parse_cli_agent_version("continue-cli 1.5.45") == "1.5.45"


def test_parse_cli_agent_version_returns_unknown_for_non_version_text() -> None:
    assert parse_cli_agent_version("Traceback (most recent call last):") == "unknown"
    assert parse_cli_agent_version("") == "unknown"


def test_get_cli_agent_version_prefers_explicit_key_then_shell_version() -> None:
    assert get_cli_agent_version({"cli_agent_version": "1.2.3", "shell_version": "tool 9.9.9"}) == "1.2.3"
    assert get_cli_agent_version({"shell_version": "tool 2.4.6"}) == "2.4.6"
    assert get_cli_agent_version({}) == "unknown"


def test_with_cli_agent_version_inserts_deterministic_fallback() -> None:
    assert with_cli_agent_version({"shell_version": "tool 3.2.1"})["cli_agent_version"] == "3.2.1"
    assert with_cli_agent_version({})["cli_agent_version"] == "unknown"
