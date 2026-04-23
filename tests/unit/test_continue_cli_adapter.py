from __future__ import annotations

from types import MethodType
from pathlib import Path

from gripprobe.adapters.continue_cli import ContinueCliAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec


def _adapter() -> ContinueCliAdapter:
    return ContinueCliAdapter(
        ShellSpec.model_validate(
            {
                "id": "continue-cli",
                "label": "continue-cli",
                "executable": "cn",
                "supported_formats": ["markdown", "tool"],
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
            "supported_formats": ["markdown", "tool"],
        }
    )


def _test_spec() -> GripTestSpec:
    return GripTestSpec.model_validate(
        {
            "id": "shell_pwd",
            "title": "Shell PWD",
            "category": "shell",
            "prompt": "Use shell",
            "allowed_tools": ["shell", "read"],
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
            "case_id": "continue-cli__local_qwen2_5_7b__ollama__tool__shell_pwd",
            "run_id": "run-continue",
            "shell_id": "continue-cli",
            "shell_label": "continue-cli",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "unknown",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "Shell PWD",
            "prompt": spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": spec.allowed_tools,
        }
    )


def test_continue_cli_uses_isolated_single_model_config(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

    captured_args: list[list[str]] = []
    captured_envs: list[dict[str, str]] = []

    def _fake_run_command(
        self,
        case_arg,
        args: list[str],
        env: dict[str, str],
        stdout_path,
        stderr_path,
        workspace_dir=None,
    ):
        captured_args.append(list(args))
        captured_envs.append(dict(env))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        stdout_path.write_text("System:\nRan command: `pwd > pwd-output.txt`\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-20T18:00:00+02:00", "2026-04-20T18:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert str(result.metadata["warmup_command"]).startswith("cn ")
    assert str(result.metadata["measured_command"]).startswith("cn ")
    assert len(captured_args) == 2
    assert len(captured_envs) == 2
    for args in captured_args:
        assert args[0] == "cn"
        assert "--config" in args
        assert "--auto" in args
        assert "--model" not in args
        assert args.count("--allow") == 2
        assert "shell" in args
        assert "read" in args
        assert "Use shell" == args[-1]
    assert captured_envs[0]["HOME"] != captured_envs[1]["HOME"]
    for env in captured_envs:
        assert env["XDG_CONFIG_HOME"]
        assert env["XDG_STATE_HOME"]


def test_continue_cli_falls_back_to_home_config_for_model_endpoint(tmp_path: Path, monkeypatch) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

    fake_home = tmp_path / "fake-home"
    continue_dir = fake_home / ".continue"
    continue_dir.mkdir(parents=True)
    (continue_dir / "config.yaml").write_text(
        "\n".join(
            [
                "name: local-ollama",
                "version: 0.0.1",
                "schema: v1",
                "models:",
                "  - name: Qwen2.5 7B",
                "    provider: ollama",
                "    model: qwen2.5:7b",
                "    apiBase: http://127.0.0.1:11434",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GRIPPROBE_CONTINUE_CONFIG", raising=False)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    captured_args: list[list[str]] = []

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        captured_args.append(list(args))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        stdout_path.write_text("System:\nRan command: `pwd > pwd-output.txt`\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-20T18:00:00+02:00", "2026-04-20T18:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    isolated_config = Path(result.metadata["continue_config_path"])
    config_text = isolated_config.read_text(encoding="utf-8")
    assert "apiBase: http://127.0.0.1:11434" in config_text
