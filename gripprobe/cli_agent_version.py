from __future__ import annotations

import re
from typing import Any
from collections.abc import Mapping

UNKNOWN_CLI_AGENT_VERSION = "unknown"
_VERSION_TOKEN_RE = re.compile(
    r"(?<![0-9A-Za-z])v?\d+(?:\.\d+){1,2}(?:[-+][0-9A-Za-z.-]+)?"
)


def parse_cli_agent_version(raw_version: str | None) -> str:
    if raw_version is None:
        return UNKNOWN_CLI_AGENT_VERSION
    lines = str(raw_version).splitlines()
    if not lines:
        return UNKNOWN_CLI_AGENT_VERSION
    first_line = lines[0].strip()
    if not first_line:
        return UNKNOWN_CLI_AGENT_VERSION
    match = _VERSION_TOKEN_RE.search(first_line)
    if not match:
        return UNKNOWN_CLI_AGENT_VERSION
    return match.group(0)


def get_cli_agent_version(metadata: Mapping[str, Any] | None) -> str:
    if not isinstance(metadata, Mapping):
        return UNKNOWN_CLI_AGENT_VERSION
    value = metadata.get("cli_agent_version")
    if isinstance(value, str) and value.strip():
        return value.strip()
    shell_version = metadata.get("shell_version")
    if isinstance(shell_version, str):
        return parse_cli_agent_version(shell_version)
    return UNKNOWN_CLI_AGENT_VERSION


def with_cli_agent_version(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload["cli_agent_version"] = get_cli_agent_version(payload)
    return payload


def format_cli_agent_label(shell_name: str, metadata: Mapping[str, Any] | None) -> str:
    version = get_cli_agent_version(metadata)
    return f"{shell_name} {version}".strip()
