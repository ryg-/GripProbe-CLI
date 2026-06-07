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


def test_continue_cli_prefers_case_proxy_ollama_host_over_process_env(tmp_path: Path, monkeypatch) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.run_metadata = {"telemetry_proxy_ollama_host": "http://127.0.0.1:18080"}
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        stdout_path.write_text("System:\nRan command: `pwd > pwd-output.txt`\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-20T18:00:00+02:00", "2026-04-20T18:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)
    result = adapter.run_case(case, model_spec, test_spec)

    isolated_config = Path(result.metadata["continue_config_path"])
    config_text = isolated_config.read_text(encoding="utf-8")
    assert "apiBase: http://127.0.0.1:18080" in config_text


def test_continue_cli_uses_phase_specific_proxy_hosts(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.run_metadata = {
        "telemetry_proxy_warmup_ollama_host": "http://127.0.0.1:19081",
        "telemetry_proxy_measured_ollama_host": "http://127.0.0.1:19082",
    }
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

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
    warmup_config = Path(captured_args[0][captured_args[0].index("--config") + 1])
    measured_config = Path(result.metadata["continue_config_path"])
    warmup_text = warmup_config.read_text(encoding="utf-8")
    measured_text = measured_config.read_text(encoding="utf-8")
    assert "apiBase: http://127.0.0.1:19081" in warmup_text
    assert "apiBase: http://127.0.0.1:19082" in measured_text


def test_continue_cli_runtime_patch_specs_apply_to_index_js(tmp_path: Path) -> None:
    adapter = _adapter()
    patch_root = tmp_path / "patched"
    dist_dir = patch_root / "dist"
    dist_dir.mkdir(parents=True)
    target = dist_dir / "index.js"
    target.write_text(
        "\n".join(
            [
                "const z=1;",
                "Fff=`ORIGINAL PROMPT`;",
                "function R0d({tools:e,toolChoice:t}){return{tools:e,toolChoice:t,toolWarnings:[]}}function a3o(){}",
                "async function Primary(){let{args:t,warnings:r}=await this.getArgs({...e}),n={...t,stream:!0,stream_options:{include_usage:!0}},{responseHeaders:o,value:i}=await ja(1);return i}",
                "async function X(){let{args:t,warnings:r}=await this.getArgs(e),n={...t,stream:!0,stream_options:{include_usage:!0}},{responseHeaders:o,value:i}=await ja(1);return i}",
            ]
        ),
        encoding="utf-8",
    )

    applied = adapter._apply_runtime_patches(
        patch_root,
        replacements={
            "continue_system_prompt": "SHORT",
            "continue_allowed_tool_names": '"Bash"',
        },
    )
    patched = target.read_text(encoding="utf-8")

    assert applied is True
    assert "Fff=`SHORT`" in patched
    assert 'new Set(["Bash"])' in patched
    assert 'q0=new Set(["Bash"])' in patched
    assert "Array.isArray(n.tools)" in patched


def test_continue_cli_reads_runtime_options_from_model_policy() -> None:
    adapter = _adapter()
    model_spec = _model_spec().model_copy(
        update={
            "policy_overrides": {
                "cli_agent_options": {
                    "continue-cli": {
                        "context_length": 8192,
                        "minimal_system_prompt": True,
                        "runtime_patches": True,
                        "patch_system_text": "Use tools.",
                    }
                }
            }
        }
    )

    assert adapter._resolve_context_length(model_spec) == 8192
    assert adapter._use_minimal_system_prompt(model_spec) is True
    assert adapter._continue_policy(model_spec)["runtime_patches"] is True
    assert adapter._continue_policy(model_spec)["patch_system_text"] == "Use tools."
