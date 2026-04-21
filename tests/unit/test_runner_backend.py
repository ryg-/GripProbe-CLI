import pytest

from gripprobe.models import BackendSpec, ModelSpec, ShellSpec
from gripprobe.runner import _apply_model_policy_overrides, _resolve_model_hash, _select_backend


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
