import pytest

from pathlib import Path

from gripprobe.models import BackendSpec, CaseDefinition, ModelSpec, ShellSpec
from gripprobe.proxy_capture import (
    _cli_agent_policy,
    resolve_proxy_allowed_tool_names,
    should_disable_proxy_for_cli_agent,
)
from gripprobe.runner import (
    _apply_model_policy_overrides,
    _apply_prompt_policy_overrides,
    _resolve_model_hash,
    _select_backend,
)


_resolve_proxy_allowed_tool_names = resolve_proxy_allowed_tool_names
_should_disable_proxy_for_cli_agent = should_disable_proxy_for_cli_agent


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


def test_resolve_proxy_allowed_tool_names_uses_cli_agent_yaml_dialect_for_gptme() -> None:
    case = CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "gptme",
            "cli_agent_label": "gptme",
            "model_id": "local_qwen3_1_7b_rpi",
            "model_label": "local/qwen3:1.7b_rpi",
            "backend_id": "ollama",
            "backend_model_id": "qwen3:1.7b",
            "cli_agent_model_id": "local/qwen3:1.7b",
            "model_hash": "hash",
            "tool_format": "tool",
            "test_id": "patch_file_shell",
            "test_title": "Patch File Via Shell",
            "prompt": "run shell patch",
            "warmup_workspace_dir": Path("/tmp/warmup"),
            "workspace_dir": Path("/tmp/workspace"),
            "case_dir": Path("/tmp/case"),
            "allowed_tools": ["shell"],
        }
    )
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "gptme",
            "label": "gptme",
            "executable": "gptme",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
            "tool_dialect": [
                {"id": "shell", "raw_name": "shell", "canonical_name": "Bash", "role": "command"},
                {"id": "complete", "raw_name": "complete", "canonical_name": "Exit", "role": "terminate"},
            ],
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_1_7b_rpi",
            "label": "local/qwen3:1.7b_rpi",
            "family": "qwen",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "qwen3:1.7b", "shell_model_id": "local/qwen3:1.7b"}],
            "policy_overrides": {"telemetry_proxy_filter_tools": True, "proxy_include_exit_tool": True},
        }
    )

    names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec)

    assert names == ["shell", "complete"]


def test_gptme_cli_agent_policy_can_disable_proxy() -> None:
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "gptme",
            "label": "gptme",
            "executable": "gptme",
            "supported_formats": ["tool"],
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_qwen3_1_7b_rpi",
            "label": "local/qwen3:1.7b_rpi",
            "family": "qwen",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "qwen3:1.7b", "shell_model_id": "local/qwen3:1.7b"}],
            "policy_overrides": {
                "cli_agent_options": {
                    "gptme": {
                        "filter_tools": True,
                        "disable_proxy": True,
                    }
                }
            },
        }
    )

    policy = _cli_agent_policy(model_spec, "gptme")

    assert policy["filter_tools"] is True
    assert _should_disable_proxy_for_cli_agent(cli_agent_spec, model_spec) is True


def test_resolve_proxy_allowed_tool_names_uses_cli_agent_yaml_dialect_for_codex() -> None:
    case = CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "codex",
            "cli_agent_label": "codex",
            "model_id": "local_llama3_2_latest_rpi",
            "model_label": "local/llama3.2:latest_rpi",
            "backend_id": "ollama",
            "backend_model_id": "llama3.2:latest",
            "cli_agent_model_id": "local/llama3.2:latest",
            "model_hash": "hash",
            "tool_format": "tool",
            "test_id": "patch_file",
            "test_title": "Patch File",
            "prompt": "read then patch",
            "warmup_workspace_dir": Path("/tmp/warmup"),
            "workspace_dir": Path("/tmp/workspace"),
            "case_dir": Path("/tmp/case"),
            "allowed_tools": ["read", "patch"],
        }
    )
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "codex",
            "label": "codex",
            "executable": "codex",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
            "tool_dialect": [
                {"id": "shell", "raw_name": "exec_command", "canonical_name": "Bash", "role": "command"},
                {"id": "shell_session", "raw_name": "write_stdin", "canonical_name": "Bash", "role": "command"},
                {"id": "read", "raw_name": "exec_command", "canonical_name": "Read", "role": "read"},
                {"id": "read_session", "raw_name": "write_stdin", "canonical_name": "Read", "role": "read"},
                {"id": "patch", "raw_name": "apply_patch", "canonical_name": "apply_patch", "role": "patch"},
            ],
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_llama3_2_latest_rpi",
            "label": "local/llama3.2:latest_rpi",
            "family": "llama",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "llama3.2:latest", "shell_model_id": "local/llama3.2:latest"}],
            "policy_overrides": {
                "cli_agent_options": {
                    "codex": {
                        "telemetry_proxy_filter_tools": True,
                        "proxy_include_exit_tool": False,
                    }
                }
            },
        }
    )

    names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec)

    assert names == ["exec_command", "write_stdin", "apply_patch"]


def test_cli_agent_proxy_options_override_global_model_proxy_keys() -> None:
    case = CaseDefinition.model_validate(
        {
            "case_id": "case",
            "run_id": "run",
            "cli_agent_id": "codex",
            "cli_agent_label": "codex",
            "model_id": "local_llama3_2_latest_rpi",
            "model_label": "local/llama3.2:latest_rpi",
            "backend_id": "ollama",
            "backend_model_id": "llama3.2:latest",
            "cli_agent_model_id": "local/llama3.2:latest",
            "model_hash": "hash",
            "tool_format": "tool",
            "test_id": "shell_pwd",
            "test_title": "Shell PWD",
            "prompt": "run shell",
            "warmup_workspace_dir": Path("/tmp/warmup"),
            "workspace_dir": Path("/tmp/workspace"),
            "case_dir": Path("/tmp/case"),
            "allowed_tools": ["shell"],
        }
    )
    cli_agent_spec = ShellSpec.model_validate(
        {
            "id": "codex",
            "label": "codex",
            "executable": "codex",
            "supported_formats": ["tool"],
            "timeout_seconds": 120,
            "tool_dialect": [
                {"id": "shell", "raw_name": "exec_command", "canonical_name": "Bash", "role": "command"},
                {"id": "shell_session", "raw_name": "write_stdin", "canonical_name": "Bash", "role": "command"},
            ],
        }
    )
    model_spec = ModelSpec.model_validate(
        {
            "id": "local_llama3_2_latest_rpi",
            "label": "local/llama3.2:latest_rpi",
            "family": "llama",
            "size_class": "small",
            "backends": [{"id": "ollama", "model_id": "llama3.2:latest", "shell_model_id": "local/llama3.2:latest"}],
            "policy_overrides": {
                "telemetry_proxy_filter_tools": False,
                "proxy_include_exit_tool": True,
                "cli_agent_options": {
                    "codex": {
                        "telemetry_proxy_filter_tools": True,
                        "proxy_include_exit_tool": False,
                    }
                },
            },
        }
    )

    policy = _cli_agent_policy(model_spec, "codex")
    names = _resolve_proxy_allowed_tool_names(case, cli_agent_spec, model_spec)

    assert policy["telemetry_proxy_filter_tools"] is True
    assert policy["proxy_include_exit_tool"] is False
    assert names == ["exec_command", "write_stdin"]
