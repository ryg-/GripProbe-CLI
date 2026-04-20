import pytest

from gripprobe.models import BackendSpec, ModelSpec
from gripprobe.runner import _select_backend


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
