from __future__ import annotations

import json
from pathlib import Path
from types import MethodType

from gripprobe.adapters.opencode import OpencodeAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec


def _adapter() -> OpencodeAdapter:
    return OpencodeAdapter(
        ShellSpec.model_validate(
            {
                "id": "opencode",
                "label": "opencode",
                "executable": "opencode",
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
            "case_id": "opencode__local_qwen2_5_7b__ollama__tool__shell_pwd",
            "run_id": "run-opencode",
            "shell_id": "opencode",
            "shell_label": "opencode",
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


def test_opencode_uses_isolated_single_model_config(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)

    captured_args: list[list[str]] = []

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        captured_args.append(list(args))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "pwd-output.txt").write_text(str(active_workspace) + "\n", encoding="utf-8")
        stdout_path.write_text('{"type":"message","role":"assistant","content":"DONE"}\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-21T10:00:00+02:00", "2026-04-21T10:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert len(captured_args) == 2
    for args in captured_args:
        assert args[:3] == ["opencode", "run", "--format"]
        assert "--model" in args
        assert "ollama/qwen2.5:7b" in args
        assert "--dangerously-skip-permissions" in args

    isolated_config = Path(result.metadata["opencode_config_path"])
    payload = json.loads(isolated_config.read_text(encoding="utf-8"))
    assert payload["model"] == "ollama/qwen2.5:7b"
    assert payload["small_model"] == "ollama/qwen2.5:7b"
    assert payload["provider"]["ollama"]["models"]["qwen2.5:7b"]["name"] == "Qwen2.5 7B"


def test_opencode_classifies_text_only_completion_as_no_invocation(tmp_path: Path) -> None:
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
