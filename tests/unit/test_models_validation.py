import pytest
from pydantic import ValidationError

from gripprobe.models import ModelSpec, TestSpec as GripTestSpec


def test_testspec_allows_missing_allowed_tools() -> None:
    spec = GripTestSpec.model_validate(
        {
            "id": "shell_pwd",
            "title": "Shell PWD",
            "category": "shell",
            "prompt": "Run pwd.",
            "validators": [
                {
                    "type": "file_equals",
                    "target": "pwd-output.txt",
                    "expected_from": "workspace_path",
                }
            ],
        }
    )

    assert spec.allowed_tools is None
    assert len(spec.validators) == 1


def test_testspec_requires_validators_array() -> None:
    with pytest.raises(ValidationError, match="validators"):
        GripTestSpec.model_validate(
            {
                "id": "shell_pwd",
                "title": "Shell PWD",
                "category": "shell",
                "prompt": "Run pwd.",
            }
        )


def test_modelspec_requires_backends_array() -> None:
    with pytest.raises(ValidationError, match="backends"):
        ModelSpec.model_validate(
            {
                "id": "local_qwen2_5_7b",
                "label": "local/qwen2.5:7b",
                "family": "qwen",
                "size_class": "small",
            }
        )
