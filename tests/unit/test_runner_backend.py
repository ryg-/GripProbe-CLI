import pytest

from pathlib import Path

from gripprobe.models import BackendSpec, CaseDefinition, ModelSpec, ShellSpec
from gripprobe.runner import (
    _apply_model_policy_overrides,
    _apply_prompt_policy_overrides,
    _resolve_model_hash,
    _resolve_proxy_allowed_tool_names,
    _select_backend,
)


@pytest.fixture()
def model_spec() -> ModelSpec:
    return ModelSpec.model_validate(
        {
            "id": "local_qwen2_5_7b",
            "label": "local/qwen2.5:7b",
            "family": "qwen",
            "size_class": "small",
            "parameters_b": 7,
            "quantization": "Q4_K_M",
            "backends": [
                {
                    "id": "ollama",
                    "model_id": "qwen2.5:7b",
                    "shell_model_id": "local/qwen2.5:7b",
                },
                {
                    "id": "vllm",
                    "model_id": "qwen2.5-7b-instruct",
                    "shell_model_id": "openai/qwen2.5-7b-instruct",
                },
            ],
            "supported_formats": ["markdown", "tool"],
        }
    )


def test_select_backend_returns_requested_backend(model_spec: ModelSpec) -> None:
    backend = _select_backend(model_spec, "vllm")

    assert isinstance(backend, BackendSpec)
    assert backend.id == "vllm"
    assert backend.model_id == "qwen2.5-7b-instruct"
    assert backend.shell_model_id == "openai/qwen2.5-7b-instruct"


def test_select_backend_raises_for_unknown_backend(model_spec: ModelSpec) -> None:
    with pytest.raises(ValueError, match="backend=tgi"):
        _select_backend(model_spec, "tgi")


def test_apply_model_policy_overrides_updates_shell_timeout_for_matching_shell() -> None:
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_8b",
            "label": "local/qwen3:8b",
            "family": "qwen",
            "size_class": "small",
            "backends": [
                {
                    "id": "ollama",
                    "model_id": "qwen3:8b",
                    "shell_model_id": "local/qwen3:8b",
                }
            ],
            "policy_overrides": {
                "shell_timeout_seconds": {
                    "continue-cli": 600,
                }
            },
        }
    )
    shell_spec = ShellSpec.model_validate(
        {
            "id": "continue-cli",
            "label": "continue-cli",
            "executable": "cn",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
        }
    )

    overridden = _apply_model_policy_overrides(shell_spec, model_spec)

    assert overridden.timeout_seconds == 600
    assert shell_spec.timeout_seconds == 120


def test_resolve_model_hash_uses_ollama_digest_when_available(monkeypatch) -> None:
    backend = BackendSpec.model_validate(
        {
            "id": "ollama",
            "model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
        }
    )
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: "845dbda0ea48")

    resolved = _resolve_model_hash(backend, cli_model_hash="cli-fallback")

    assert resolved == "845dbda0ea48"


def test_resolve_model_hash_falls_back_to_cli_when_ollama_digest_missing(monkeypatch) -> None:
    backend = BackendSpec.model_validate(
        {
            "id": "ollama",
            "model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
        }
    )
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: None)

    resolved = _resolve_model_hash(backend, cli_model_hash="cli-fallback")

    assert resolved == "cli-fallback"


def test_resolve_model_hash_uses_backend_hash_for_non_ollama() -> None:
    backend = BackendSpec.model_validate(
        {
            "id": "vllm",
            "model_id": "qwen2.5-7b-instruct",
            "shell_model_id": "openai/qwen2.5-7b-instruct",
            "model_hash": "backend-hash",
        }
    )

    resolved = _resolve_model_hash(backend, cli_model_hash="cli-fallback")

    assert resolved == "cli-fallback"


def test_resolve_model_hash_returns_unknown_when_no_sources_exist(monkeypatch) -> None:
    backend = BackendSpec.model_validate(
        {
            "id": "ollama",
            "model_id": "qwen2.5:7b",
            "shell_model_id": "local/qwen2.5:7b",
        }
    )
    monkeypatch.setattr("gripprobe.runner._fetch_ollama_model_digest", lambda model_id: None)

    resolved = _resolve_model_hash(backend)

    assert resolved == "unknown"


def test_apply_prompt_policy_overrides_appends_no_think_once() -> None:
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_1_7b",
            "label": "local/qwen3:1.7b",
            "family": "qwen",
            "size_class": "small",
            "backends": [
                {
                    "id": "ollama",
                    "model_id": "qwen3:1.7b",
                    "shell_model_id": "local/qwen3:1.7b",
                }
            ],
            "policy_overrides": {"prompt_append_no_think": True},
        }
    )
    base_prompt = "Use the shell tool.\nRun exactly this command: pwd > pwd-output.txt."
    overridden = _apply_prompt_policy_overrides(base_prompt, model_spec)
    overridden_twice = _apply_prompt_policy_overrides(overridden, model_spec)

    assert overridden.endswith("/no_think\n")
    assert overridden.count("/no_think") == 1
    assert overridden_twice.count("/no_think") == 1


def test_resolve_proxy_allowed_tool_names_excludes_exit_when_overridden() -> None:
    case = CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "continue-cli",
            "cli_agent_label": "continue-cli",
            "model_id": "local_qwen3_1_7b",
            "model_label": "local/qwen3:1.7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen3:1.7b",
            "cli_agent_model_id": "local/qwen3:1.7b",
            "model_hash": "hash",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "shell_pwd",
            "prompt": "run pwd",
            "warmup_workspace_dir": Path("/tmp/warmup"),
            "workspace_dir": Path("/tmp/workspace"),
            "case_dir": Path("/tmp/case"),
            "allowed_tools": ["shell"],
        }
    )
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "continue-cli",
            "label": "continue-cli",
            "executable": "cn",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_1_7b",
            "label": "local/qwen3:1.7b",
            "family": "qwen",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "qwen3:1.7b", "shell_model_id": "local/qwen3:1.7b"}],
            "policy_overrides": {"proxy_include_exit_tool": False},
        }
    )

    names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec)

    assert names == ["Bash"]


def test_resolve_proxy_allowed_tool_names_includes_model_overrides() -> None:
    case = CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "continue-cli",
            "cli_agent_label": "continue-cli",
            "model_id": "local_qwen3_1_7b",
            "model_label": "local/qwen3:1.7b",
            "backend_id": "ollama",
            "backend_model_id": "qwen3:1.7b",
            "cli_agent_model_id": "local/qwen3:1.7b",
            "model_hash": "hash",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "shell_pwd",
            "prompt": "run pwd",
            "warmup_workspace_dir": Path("/tmp/warmup"),
            "workspace_dir": Path("/tmp/workspace"),
            "case_dir": Path("/tmp/case"),
            "allowed_tools": ["shell"],
        }
    )
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "continue-cli",
            "label": "continue-cli",
            "executable": "cn",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_1_7b",
            "label": "local/qwen3:1.7b",
            "family": "qwen",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "qwen3:1.7b", "shell_model_id": "local/qwen3:1.7b"}],
            "policy_overrides": {"proxy_include_tool_names": ["read", "patch"]},
        }
    )

    names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec)

    assert names == ["Bash", "Read", "MultiEdit", "Exit"]
