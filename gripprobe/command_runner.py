from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

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


class CallableCommandRunner:
    """Adapt the adapter's existing bound command method to the protocol."""

    def __init__(self, callback: Callable[..., CommandResult]) -> None:
        self._callback = callback

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
        return self._callback(
            case,
            args,
            env,
            stdout_path,
            stderr_path,
            workspace_dir=workspace_dir,
        )
