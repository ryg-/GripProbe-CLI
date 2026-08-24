from __future__ import annotations

from pathlib import Path

import pytest

from gripprobe.models import CaseDefinition, ModelSpec, TestSpec as GripTestSpec
from gripprobe.phase_execution import run_case_with_phase_proxy
from gripprobe.proxy_capture import ProxyCaptureOptions


class _FakeProxy:
    def __init__(self, *, case_dir: Path, artifact_relpath: str, base_url: str, fail_stop: bool = False) -> None:
        self.case_dir = case_dir
        self.artifact_relpath = artifact_relpath
        self.base_url = base_url
        self.fail_stop = fail_stop
        self.stop_calls = 0

    def start(self) -> None:
        artifact = self.case_dir / self.artifact_relpath
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("captured\n", encoding="utf-8")

    def stop(self) -> None:
        self.stop_calls += 1
        if self.fail_stop:
            raise RuntimeError("stop failed")


class _FakeAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self.case_metadata: dict[str, object] = {}
        self.fail = fail

    def run_command(self, case, args, env, stdout_path, stderr_path, workspace_dir=None):
        self.calls.append(
            {
                "args": args,
                "env": dict(env),
                "workspace_dir": workspace_dir,
            }
        )
        stdout_path.write_text("ok\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.01, "start", "finish"

    def run_case(self, case, model_spec, test_spec, command_runner=None):
        if self.fail:
            raise RuntimeError("adapter failed")
        assert command_runner is not None
        self.case_metadata = dict(case.run_metadata)
        command_runner.run(
            case=case,
            args=["warmup"],
            env={"PHASE": "warmup"},
            stdout_path=case.case_dir / "warmup.stdout",
            stderr_path=case.case_dir / "warmup.stderr",
            workspace_dir=case.warmup_workspace_dir,
        )
        command_runner.run(
            case=case,
            args=["measured"],
            env={"PHASE": "measured"},
            stdout_path=case.case_dir / "measured.stdout",
            stderr_path=case.case_dir / "measured.stderr",
            workspace_dir=case.workspace_dir,
        )
        return "result"


def _case(tmp_path: Path) -> CaseDefinition:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    return CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "gptme",
            "cli_agent_label": "gptme",
            "model_id": "model",
            "model_label": "model",
            "backend_id": "ollama",
            "backend_model_id": "model",
            "cli_agent_model_id": "model",
            "model_hash": "unknown",
            "tool_format": "markdown",
            "test_id": "pwd",
            "test_title": "pwd",
            "prompt": "pwd",
            "warmup_workspace_dir": tmp_path / "warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": case_dir,
        }
    )


def _specs() -> tuple[ModelSpec, GripTestSpec]:
    model = ModelSpec.model_validate(
        {
            "id": "model",
            "label": "model",
            "family": "test",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "model", "cli_agent_model_id": "model"}],
        }
    )
    test = GripTestSpec.model_validate(
        {
            "id": "pwd",
            "title": "pwd",
            "category": "filesystem",
            "prompt": "pwd",
            "validators": [],
        }
    )
    return model, test


def test_phase_execution_routes_each_phase_without_replacing_adapter_method(tmp_path: Path) -> None:
    case = _case(tmp_path)
    model, test = _specs()
    adapter = _FakeAdapter()
    original_run_command = adapter.run_command
    proxies: list[_FakeProxy] = []

    def factory(*, case_dir: Path, artifact_relpath: str, **_kwargs):
        proxy = _FakeProxy(
            case_dir=case_dir,
            artifact_relpath=artifact_relpath,
            base_url=f"http://127.0.0.1:{19080 + len(proxies)}",
        )
        proxies.append(proxy)
        return proxy

    result, metadata, artifacts, error = run_case_with_phase_proxy(
        adapter=adapter,
        case=case,
        model_spec=model,
        test_spec=test,
        upstream_base_url="http://127.0.0.1:11434",
        proxy_options=ProxyCaptureOptions(),
        proxy_factory=factory,
    )

    assert result == "result"
    assert error is None
    assert [call["workspace_dir"] for call in adapter.calls] == [
        case.warmup_workspace_dir,
        case.workspace_dir,
    ]
    assert adapter.calls[0]["env"]["OLLAMA_HOST"] == "http://127.0.0.1:19080"
    assert adapter.calls[1]["env"]["OLLAMA_HOST"] == "http://127.0.0.1:19081"
    assert all(proxy.stop_calls == 1 for proxy in proxies)
    assert adapter.run_command == original_run_command
    assert artifacts == {
        "warmup": "artifacts/proxy.warmup.http.jsonl",
        "measured": "artifacts/proxy.measured.http.jsonl",
    }
    assert metadata["telemetry_proxy_warmup_ollama_host"] == "http://127.0.0.1:19080"
    assert "telemetry_proxy_ollama_host" not in adapter.case_metadata


def test_phase_execution_falls_back_when_one_proxy_cannot_start(tmp_path: Path) -> None:
    case = _case(tmp_path)
    model, test = _specs()
    adapter = _FakeAdapter()
    proxies: list[_FakeProxy] = []

    def factory(*, case_dir: Path, artifact_relpath: str, **_kwargs):
        if artifact_relpath.endswith("warmup.http.jsonl"):
            raise RuntimeError("warmup unavailable")
        proxy = _FakeProxy(case_dir=case_dir, artifact_relpath=artifact_relpath, base_url="http://127.0.0.1:19081")
        proxies.append(proxy)
        return proxy

    _result, _metadata, artifacts, error = run_case_with_phase_proxy(
        adapter=adapter,
        case=case,
        model_spec=model,
        test_spec=test,
        upstream_base_url="http://127.0.0.1:11434",
        proxy_options=ProxyCaptureOptions(),
        proxy_factory=factory,
    )

    assert error == "warmup unavailable"
    assert "telemetry_proxy_ollama_host" not in adapter.case_metadata
    assert adapter.case_metadata["telemetry_proxy_measured_ollama_host"] == "http://127.0.0.1:19081"
    assert "OLLAMA_HOST" not in adapter.calls[0]["env"]
    assert adapter.calls[1]["env"]["OLLAMA_HOST"] == "http://127.0.0.1:19081"
    assert artifacts == {"measured": "artifacts/proxy.measured.http.jsonl"}
    assert proxies[0].stop_calls == 1


def test_phase_execution_stops_proxies_when_adapter_raises(tmp_path: Path) -> None:
    case = _case(tmp_path)
    model, test = _specs()
    adapter = _FakeAdapter(fail=True)
    proxies: list[_FakeProxy] = []

    def factory(*, case_dir: Path, artifact_relpath: str, **_kwargs):
        proxy = _FakeProxy(case_dir=case_dir, artifact_relpath=artifact_relpath, base_url="http://127.0.0.1:19080")
        proxies.append(proxy)
        return proxy

    with pytest.raises(RuntimeError, match="adapter failed"):
        run_case_with_phase_proxy(
            adapter=adapter,
            case=case,
            model_spec=model,
            test_spec=test,
            upstream_base_url="http://127.0.0.1:11434",
            proxy_options=ProxyCaptureOptions(),
            proxy_factory=factory,
        )

    assert all(proxy.stop_calls == 1 for proxy in proxies)


def test_phase_execution_preserves_result_when_proxy_stop_fails(tmp_path: Path) -> None:
    case = _case(tmp_path)
    model, test = _specs()
    adapter = _FakeAdapter()
    proxies: list[_FakeProxy] = []

    def factory(*, case_dir: Path, artifact_relpath: str, **_kwargs):
        proxy = _FakeProxy(
            case_dir=case_dir,
            artifact_relpath=artifact_relpath,
            base_url="http://127.0.0.1:19080",
            fail_stop=True,
        )
        proxies.append(proxy)
        return proxy

    result, _metadata, _artifacts, error = run_case_with_phase_proxy(
        adapter=adapter,
        case=case,
        model_spec=model,
        test_spec=test,
        upstream_base_url="http://127.0.0.1:11434",
        proxy_options=ProxyCaptureOptions(),
        proxy_factory=factory,
    )

    assert result == "result"
    assert error == "stop failed"
    assert all(proxy.stop_calls == 1 for proxy in proxies)
