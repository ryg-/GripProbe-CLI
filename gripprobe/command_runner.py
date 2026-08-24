from __future__ import annotations

from pathlib import Path
from typing import Protocol

from gripprobe.models import CaseDefinition


CommandResult = tuple[int, float, str, str]


class CommandRunner(Protocol):
    """Run one agent command for a single benchmark case."""

    def run(
        self,
        *,
        case: CaseDefinition,
        args: list[str],
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        workspace_dir: Path | None = None,
    ) -> CommandResult:
        ...
