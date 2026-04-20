from __future__ import annotations

import subprocess
from pathlib import Path

from gripprobe.runner import _collect_shell_runtime_metadata


def test_collect_shell_runtime_metadata_reads_first_version_line(monkeypatch) -> None:
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_CONTEXT_LENGTH": "32768", "OLLAMA_NUM_PARALLEL": "1"})
    monkeypatch.setattr("gripprobe.runner.shutil.which", lambda executable: f"{Path.home()}/bin/{executable}")
    monkeypatch.setattr(
        "gripprobe.runner.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["tool", "--version"],
            returncode=0,
            stdout="tool 1.2.3\nextra line\n",
            stderr="",
        ),
    )

    metadata = _collect_shell_runtime_metadata("tool")

    assert metadata == {
        "shell_executable": "tool",
        "shell_executable_path": "$HOME/bin/tool",
        "shell_version": "tool 1.2.3",
        "shell_version_exit_code": "0",
        "ollama_context_length": "32768",
        "ollama_num_parallel": "1",
    }


def test_collect_shell_runtime_metadata_returns_partial_data_when_probe_fails(monkeypatch) -> None:
    monkeypatch.setattr("gripprobe.runner.os.environ", {})
    monkeypatch.setattr("gripprobe.runner.shutil.which", lambda executable: None)

    def _raise(*args, **kwargs):
        raise OSError("not found")

    monkeypatch.setattr("gripprobe.runner.subprocess.run", _raise)

    metadata = _collect_shell_runtime_metadata("tool")

    assert metadata == {"shell_executable": "tool"}
