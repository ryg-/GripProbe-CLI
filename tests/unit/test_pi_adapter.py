from __future__ import annotations

import json
from pathlib import Path
from types import MethodType

from gripprobe.adapters.pi import PiAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec


def _adapter() -> PiAdapter:
    return PiAdapter(
        ShellSpec.model_validate(
            {
                "id": "pi",
                "label": "pi",
                "executable": "pi",
                "supported_formats": ["tool"],
                "default_tools": ["shell", "patch", "read", "save"],
            }
        )
    )


def _model_spec() -> ModelSpec:
    return ModelSpec.model_validate(
        {
            "id": "local_qwen2_5_7b",
            "label": "local/qwen2.5:7b",
            "family": "qwen",
            "size_class": "small",
            "backends": [
                {
                    "id": "ollama",
                    "model_id": "qwen2.5:7b",
                    "shell_model_id": "local/qwen2.5:7b",
                }
            ],
            "policy_overrides": {
                "cli_agent_options": {
                    "pi": {
                        "system_prompt": "Use tools first. Be concise.",
                        "offline": True,
                        "skip_version_check": True,
                        "telemetry_enabled": False,
                    }
                }
            },
        }
    )


def _test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "shell_pwd",
            "title": "Shell PWD",
            "category": "shell",
            "prompt": "Use the shell tool. Run pwd > pwd-output.txt.",
            "allowed_tools": ["shell"],
            "validators": [
                {
                    "type": "file_equals",
                    "target": "pwd-output.txt",
                    "expected_from": "workspace_path",
                }
            ],
        }
    )


def _case(tmp_path: Path, spec: GripTestSpec) -> CaseDefinition:
    return CaseDefinition.model_validate(
        {
            "case_id": "pi__local_qwen2_5_7b__ollama__tool__shell_pwd",
            "run_id": "run-pi",
            "cli_agent_id": "pi",
            "cli_agent_label": "pi",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "cli_agent_model_id": "local/qwen2.5:7b",
            "model_hash": "unknown",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "Shell PWD",
            "prompt": spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": spec.allowed_tools,
            "run_metadata": {
                "telemetry_proxy_warmup_openai_base_url": "http://127.0.0.1:38143/v1",
                "telemetry_proxy_measured_openai_base_url": "http://127.0.0.1:41951/v1",
            },
        }
    )


def test_pi_uses_isolated_models_json_and_json_mode(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

    captured_args: list[list[str]] = []
    captured_envs: list[dict[str, str]] = []

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        del self
        captured_args.append(list(args))
        captured_envs.append(dict(env))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        stdout_path.write_text(
            '{"type":"item.started","item":{"type":"command_execution","status":"in_progress"}}\n'
            '{"type":"item.completed","item":{"type":"command_execution","status":"completed","exit_code":0}}\n',
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-06-09T12:00:00+00:00", "2026-06-09T12:00:01+00:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert len(captured_args) == 2
    for args in captured_args:
        assert args[:3] == ["pi", "--mode", "json"]
        assert "--provider" in args
        assert "--model" in args
        assert "--tools" in args
        assert "bash" in args[args.index("--tools") + 1]
        assert "--no-context-files" in args
        assert "--no-skills" in args
        assert "--no-extensions" in args
        assert "--no-prompt-templates" in args
        assert "--offline" in args
        assert "--system-prompt" in args
        assert "Use tools first. Be concise." in args

    for env in captured_envs:
        assert env["PI_SKIP_VERSION_CHECK"] == "1"
        assert env["PI_TELEMETRY"] == "0"

    warmup_models = Path(captured_envs[0]["HOME"]) / ".pi" / "agent" / "models.json"
    measured_models = Path(captured_envs[1]["HOME"]) / ".pi" / "agent" / "models.json"
    warmup_payload = json.loads(warmup_models.read_text())
    measured_payload = json.loads(measured_models.read_text())
    assert warmup_payload["providers"]["ollama"]["baseUrl"] == "http://127.0.0.1:38143/v1"
    assert measured_payload["providers"]["ollama"]["baseUrl"] == "http://127.0.0.1:41951/v1"


def test_pi_infers_invoked_from_command_execution() -> None:
    adapter = _adapter()

    assert (
        adapter._infer_invoked(  # noqa: SLF001
            '{"type":"item.completed","item":{"type":"command_execution","status":"completed","exit_code":0}}',
            "",
        )
        == "yes"
    )
