from __future__ import annotations

import subprocess
import urllib.error
from pathlib import Path
from typing import cast

from gripprobe.runner import (
    _collect_runtime_snapshot,
    _collect_shell_runtime_metadata,
    _fetch_ollama_model_digest,
    _ollama_base_url,
    _ollama_probe_target,
)


ProbePayload = dict[str, str | int | float]
ProbeMap = dict[str, ProbePayload]
SnapshotPayload = dict[str, object]


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


def test_collect_runtime_snapshot_captures_ollama_and_system_probes(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        command = " ".join(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"{command} ok\n",
            stderr="",
        )

    monkeypatch.setattr("gripprobe.runner.subprocess.run", _fake_run)
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_HOST": "http://127.0.0.1:11434"})

    class _FakeResponse:
        status = 200

        def read(self):
            return b'{"models":[{"name":"qwen3:8b"}]}'

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=0):
        assert request.full_url == "http://127.0.0.1:11434/api/ps"
        return _FakeResponse()

    monkeypatch.setattr("gripprobe.runner.urllib.request.urlopen", _fake_urlopen)

    snapshot = _collect_runtime_snapshot(include_ollama=True)

    snapshot_payload = cast(SnapshotPayload, snapshot)
    assert snapshot_payload["captured_at"]
    probes = cast(ProbeMap, snapshot_payload["probes"])
    assert probes["loadavg"]["status"] == "ok"
    assert probes["meminfo"]["status"] == "ok"
    assert probes["nvidia_smi"]["status"] == "ok"
    assert probes["ollama_ps"]["status"] == "ok"
    assert probes["ollama_ps"]["stdout"] == '{"models":[{"name":"qwen3:8b"}]}'
    assert probes["ollama_ps"]["command"] == "GET http://127.0.0.1:11434/api/ps"
    assert ["cat", "/proc/loadavg"] in calls


def test_collect_runtime_snapshot_marks_missing_probe_as_unavailable(monkeypatch) -> None:
    def _fake_run(args, **kwargs):
        if args[0] == "nvidia-smi":
            raise FileNotFoundError("missing")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("gripprobe.runner.subprocess.run", _fake_run)

    snapshot = _collect_runtime_snapshot(include_ollama=False)
    snapshot_payload = cast(SnapshotPayload, snapshot)
    probes = cast(ProbeMap, snapshot_payload["probes"])

    assert probes["nvidia_smi"]["status"] == "unavailable"


def test_collect_runtime_snapshot_uses_ssh_for_remote_ollama_host(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok\n", stderr="")

    class _FakeResponse:
        status = 200

        def read(self):
            return b'{"models":[]}'

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("gripprobe.runner.subprocess.run", _fake_run)
    monkeypatch.setattr("gripprobe.runner.urllib.request.urlopen", lambda request, timeout=0: _FakeResponse())
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_HOST": "http://ollama-host:11434"})

    snapshot = _collect_runtime_snapshot(include_ollama=True)
    snapshot_payload = cast(SnapshotPayload, snapshot)
    probes = cast(ProbeMap, snapshot_payload["probes"])

    assert probes["loadavg"]["command"] == "ssh ollama-host cat /proc/loadavg"
    assert probes["meminfo"]["command"] == "ssh ollama-host cat /proc/meminfo"
    assert str(probes["nvidia_smi"]["command"]).startswith("ssh ollama-host nvidia-smi")
    assert ["ssh", "ollama-host", "cat /proc/loadavg"] in calls


def test_ollama_probe_target_uses_explicit_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "gripprobe.runner.os.environ",
        {
            "OLLAMA_HOST": "http://ollama-host:11434",
            "GRIPPROBE_OLLAMA_SSH_TARGET": "gpu-box",
        },
    )

    assert _ollama_probe_target() == "gpu-box"


def test_collect_runtime_snapshot_marks_ollama_connection_error(monkeypatch) -> None:
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_HOST": "127.0.0.1:11434"})
    monkeypatch.setattr(
        "gripprobe.runner.urllib.request.urlopen",
        lambda request, timeout=0: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )

    snapshot = _collect_runtime_snapshot(include_ollama=True)
    snapshot_payload = cast(SnapshotPayload, snapshot)
    probes = cast(ProbeMap, snapshot_payload["probes"])

    assert probes["ollama_ps"]["status"] == "connection_error"
    assert probes["ollama_ps"]["command"] == "GET http://127.0.0.1:11434/api/ps"


def test_ollama_base_url_adds_scheme(monkeypatch) -> None:
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_HOST": "127.0.0.1:11434/"})

    assert _ollama_base_url() == "http://127.0.0.1:11434"


def test_fetch_ollama_model_digest_reads_digest_from_tags(monkeypatch) -> None:
    monkeypatch.setattr("gripprobe.runner.os.environ", {"OLLAMA_HOST": "http://127.0.0.1:11434"})

    class _FakeResponse:
        def read(self):
            return (
                b'{"models":['
                b'{"name":"qwen2.5:7b","digest":"845dbda0ea48"},'
                b'{"name":"qwen3:8b","digest":"500a1f067a9f"}'
                b']}'
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("gripprobe.runner.urllib.request.urlopen", lambda request, timeout=0: _FakeResponse())

    assert _fetch_ollama_model_digest("qwen2.5:7b") == "845dbda0ea48"
