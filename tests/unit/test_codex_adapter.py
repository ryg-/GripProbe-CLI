from __future__ import annotations

import json
import os
from pathlib import Path
from types import MethodType

from gripprobe.adapters.codex import CodexAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec


def _adapter() -> CodexAdapter:
    return CodexAdapter(
        ShellSpec.model_validate(
            {
                "id": "codex",
                "label": "codex",
                "executable": "codex",
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
            "supported_formats": ["tool"],
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
            "case_id": "codex__local_qwen2_5_7b__ollama__tool__shell_pwd",
            "run_id": "run-codex",
            "shell_id": "codex",
            "shell_label": "codex",
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


def test_codex_uses_isolated_runtime_and_ollama_exec(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

    captured_args: list[list[str]] = []
    captured_envs: list[dict[str, str]] = []
    captured_aux_args: list[list[str]] = []

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
        stdout_path.write_text('{"type":"tool_use","tool_name":"shell"}\nDONE\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-21T10:00:00+02:00", "2026-04-21T10:00:01+02:00"

    def _fake_run_aux_command(
        self,
        case_arg,
        args: list[str],
        env: dict[str, str],
        workspace_dir,
        timeout_seconds: int = 15,
    ):
        del case_arg, workspace_dir, timeout_seconds
        captured_aux_args.append(list(args))
        if args[1:] == ["features", "enable", "apply_patch_freeform"]:
            codex_home = Path(env["CODEX_HOME"])
            codex_home.mkdir(parents=True, exist_ok=True)
            (codex_home / "config.toml").write_text(
                f'cache_dir = "{env["HOME"]}/cache"\n',
                encoding="utf-8",
            )
            return 0, "enabled\n", ""
        if args[1:] == ["features", "list"]:
            return 0, "apply_patch_freeform\ttrue\n", ""
        return 0, "", ""

    adapter.run_command = MethodType(_fake_run_command, adapter)
    adapter._run_aux_command = MethodType(_fake_run_aux_command, adapter)

    prev_ollama_host = os.environ.get("OLLAMA_HOST")
    prev_codex_config = os.environ.get("GRIPPROBE_CODEX_CONFIG")
    source_config = tmp_path / "source-config.toml"
    source_config.write_text(f'cache_dir = "{Path.home()}/.cache/codex"\n', encoding="utf-8")
    os.environ["OLLAMA_HOST"] = "http://c:11434"
    os.environ["GRIPPROBE_CODEX_CONFIG"] = str(source_config)
    try:
        result = adapter.run_case(case, model_spec, test_spec)
    finally:
        if prev_ollama_host is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = prev_ollama_host
        if prev_codex_config is None:
            os.environ.pop("GRIPPROBE_CODEX_CONFIG", None)
        else:
            os.environ["GRIPPROBE_CODEX_CONFIG"] = prev_codex_config

    assert result.status == "PASS"
    assert str(result.metadata["warmup_command"]).startswith("codex -a never exec ")
    assert str(result.metadata["measured_command"]).startswith("codex -a never exec ")
    assert len(captured_args) == 2
    assert len(captured_envs) == 2
    for args in captured_args:
        assert args[:4] == ["codex", "-a", "never", "exec"]
        assert "--oss" in args
        assert "--local-provider" in args
        assert "ollama" in args
        assert "--json" in args
        assert "--model" not in args
        assert "-m" in args
        assert "qwen2.5:7b" in args
        assert "-c" in args
        model_catalog_flag = args[args.index("-c") + 1]
        assert model_catalog_flag.startswith("model_catalog_json=")
        model_catalog_path = Path(model_catalog_flag.split("=", 1)[1])
        assert model_catalog_path.exists()

    assert len(captured_aux_args) == 4
    assert captured_aux_args[0][1:] == ["features", "enable", "apply_patch_freeform"]
    assert captured_aux_args[1][1:] == ["features", "list"]
    assert captured_aux_args[2][1:] == ["features", "enable", "apply_patch_freeform"]
    assert captured_aux_args[3][1:] == ["features", "list"]

    model_catalog = json.loads((case.case_dir / "artifacts" / "codex-model-catalog.json").read_text(encoding="utf-8"))
    model_entry = model_catalog["models"][0]
    assert model_entry["slug"] == "qwen2.5:7b"
    assert model_entry["display_name"] == "qwen2.5:7b"
    assert model_entry["apply_patch_tool_type"] == "freeform"

    assert result.metadata["codex_model_catalog_path"] == "artifacts/codex-model-catalog.json"
    assert result.metadata["codex_config_source_path"] == "artifacts/codex-config-source.toml"
    assert result.metadata["codex_config_warmup_path"] == "artifacts/codex-config-warmup.toml"
    assert result.metadata["codex_config_measured_path"] == "artifacts/codex-config-measured.toml"
    assert result.metadata["codex_features_enable_warmup_exit_code"] == 0
    assert result.metadata["codex_features_enable_measured_exit_code"] == 0
    assert result.metadata["codex_features_list_warmup_exit_code"] == 0
    assert result.metadata["codex_features_list_measured_exit_code"] == 0
    assert "apply_patch_freeform" in str(result.metadata["codex_features_list_warmup"])
    assert "apply_patch_freeform" in str(result.metadata["codex_features_list_measured"])

    source_artifact = case.case_dir / "artifacts" / "codex-config-source.toml"
    warmup_artifact = case.case_dir / "artifacts" / "codex-config-warmup.toml"
    measured_artifact = case.case_dir / "artifacts" / "codex-config-measured.toml"
    assert "$HOME" in source_artifact.read_text(encoding="utf-8")
    assert "$HOME" in warmup_artifact.read_text(encoding="utf-8")
    assert "$HOME" in measured_artifact.read_text(encoding="utf-8")

    assert captured_envs[0]["HOME"] != captured_envs[1]["HOME"]
    for env in captured_envs:
        assert env["CODEX_HOME"].endswith(".codex")
        assert env["XDG_STATE_HOME"]
        assert env["CODEX_OSS_BASE_URL"] == "http://c:11434/v1"
        assert env["CODEX_OSS_PORT"] == "11434"


def test_codex_classifies_text_only_completion_as_no_invocation(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _test_spec()

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        '{"type":"message","role":"assistant","content":"DONE"}\n',
        "",
    )

    assert status == "FAIL"
    assert invoked == "no"
    assert match_percent == 0
    assert expected == str(tmp_path)
    assert observed == ""


def test_codex_detects_command_execution_as_invoked(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _test_spec()

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        '{"type":"item.completed","item":{"type":"command_execution","status":"failed"}}\n',
        "",
    )

    assert status == "FAIL"
    assert invoked == "yes"
    assert match_percent == 0
    assert expected == str(tmp_path)
    assert observed == ""


def test_codex_classifies_apply_patch_unavailable_as_tool_unsupported(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _test_spec()

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "FAIL: The apply_patch tool is not available in this environment.\n",
        "",
    )

    assert status == "TOOL_UNSUPPORTED"
    assert invoked == "no"
    assert match_percent == 0
    assert expected == ""
    assert observed == ""
