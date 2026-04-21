from __future__ import annotations

from pathlib import Path
from types import MethodType

from gripprobe.adapters.aider import AiderAdapter
from gripprobe.models import CaseDefinition, ModelSpec, ShellSpec, TestSpec as GripTestSpec


def _adapter() -> AiderAdapter:
    return AiderAdapter(
        ShellSpec.model_validate(
            {
                "id": "aider",
                "label": "aider",
                "executable": "aider",
                "supported_formats": ["markdown"],
                "default_tools": ["read", "patch", "save"],
                "timeout_seconds": 300,
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
            "id": "patch_file",
            "title": "Patch File",
            "category": "patch",
            "prompt": "Replace STATUS=old with STATUS=new in patch-target.txt.",
            "allowed_tools": ["read", "patch"],
            "validators": [
                {
                    "type": "patch_applied",
                    "target_file": "patch-target.txt",
                    "expected_line": "STATUS=new",
                }
            ],
        }
    )


def _case(tmp_path: Path, spec: GripTestSpec) -> CaseDefinition:
    return CaseDefinition.model_validate(
        {
            "case_id": "aider__local_qwen2_5_7b__ollama__markdown__patch_file",
            "run_id": "run-aider",
            "shell_id": "aider",
            "shell_label": "aider",
            "model_id": "local_qwen2_5_7b",
            "model_label": "local/qwen2.5:7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
            "model_hash": "unknown",
            "tool_format": "markdown",
            "test_id": "patch_file",
            "test_title": "Patch File",
            "prompt": spec.prompt,
            "warmup_workspace_dir": tmp_path / "workspace-warmup",
            "workspace_dir": tmp_path / "workspace",
            "case_dir": tmp_path / "case",
            "allowed_tools": spec.allowed_tools,
        }
    )


def test_aider_uses_isolated_config_and_ollama_model(tmp_path: Path) -> None:
    adapter = _adapter()
    model_spec = _model_spec()
    test_spec = _test_spec()
    case = _case(tmp_path, test_spec)
    case.warmup_workspace_dir.mkdir(parents=True)
    case.workspace_dir.mkdir(parents=True)
    (case.warmup_workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")
    (case.workspace_dir / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    captured_args: list[list[str]] = []

    def _fake_run_command(self, case_arg, args, env, stdout_path, stderr_path, workspace_dir=None):
        captured_args.append(list(args))
        active_workspace = workspace_dir or case_arg.workspace_dir
        (active_workspace / "patch-target.txt").write_text("STATUS=new\n", encoding="utf-8")
        stdout_path.write_text("Applied edit to patch-target.txt\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0, 0.1, "2026-04-21T20:00:00+02:00", "2026-04-21T20:00:01+02:00"

    adapter.run_command = MethodType(_fake_run_command, adapter)

    result = adapter.run_case(case, model_spec, test_spec)

    assert result.status == "PASS"
    assert len(captured_args) == 2
    for args in captured_args:
        assert args[0] == "aider"
        assert "--config" in args
        assert "--no-git" in args
        assert "--model" in args
        assert "ollama/qwen2.5:7b" in args
        assert "--openai-api-base" in args
        assert "--message" in args
        assert "patch-target.txt" in args

    config_path = Path(result.metadata["aider_config_path"])
    config_text = config_path.read_text(encoding="utf-8")
    assert "git: false" in config_text
    assert "analytics: false" in config_text


def test_aider_classifies_text_only_failure_as_no_invocation(tmp_path: Path) -> None:
    adapter = _adapter()
    spec = _test_spec()
    (tmp_path / "patch-target.txt").write_text("STATUS=old\n", encoding="utf-8")

    status, invoked, match_percent, expected, observed = adapter._classify(
        spec,
        tmp_path,
        "No changes are needed.\n",
        "",
    )

    assert status == "FAIL"
    assert invoked == "no"
    assert match_percent == 0
    assert expected == "STATUS=new"
    assert observed == "STATUS=old"
