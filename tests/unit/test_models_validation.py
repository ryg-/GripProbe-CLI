import pytest
from pydantic import ValidationError

from gripprobe.models import ModelSpec, TestSpec as GripTestSpec
from gripprobe.spec_loader import load_hardware_profiles


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


def test_modelspec_allows_backend_without_model_hash() -> None:
    spec = ModelSpec.model_validate(
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
        }
    )

    assert spec.backends[0].model_hash is None


def test_web_nonce_proof_validator_requires_target() -> None:
    with pytest.raises(ValidationError, match="web_nonce_proof validator requires target"):
        GripTestSpec.model_validate(
            {
                "id": "web_nonce_proof",
                "title": "Web Nonce Proof",
                "category": "web",
                "prompt": "web",
                "validators": [
                    {
                        "type": "web_nonce_proof",
                    }
                ],
            }
        )


def test_web_search_result_validator_requires_expected() -> None:
    with pytest.raises(ValidationError, match="web_search_result validator requires expected"):
        GripTestSpec.model_validate(
            {
                "id": "web_search_json_ranked",
                "title": "Web Search JSON Ranked",
                "category": "web",
                "prompt": "search",
                "validators": [
                    {
                        "type": "web_search_result",
                        "target": "search-result.json",
                        "request_log": "requests.json",
                        "request_path": "/search/token",
                    }
                ],
            }
        )


def test_web_search_result_validator_requires_request_log_and_request_path_together() -> None:
    with pytest.raises(ValidationError, match="web_search_result validator requires request_log and request_path together"):
        GripTestSpec.model_validate(
            {
                "id": "web_search_json_ranked",
                "title": "Web Search JSON Ranked",
                "category": "web",
                "prompt": "search",
                "validators": [
                    {
                        "type": "web_search_result",
                        "target": "search-result.json",
                        "expected": "{\"query\":\"x\"}",
                        "request_log": "requests.json",
                    }
                ],
            }
        )


def test_web_search_result_validator_allows_file_only_mode_without_request_metadata() -> None:
    spec = GripTestSpec.model_validate(
        {
            "id": "json_rank_from_file",
            "title": "JSON Rank From File",
            "category": "scenario",
            "prompt": "rank",
            "validators": [
                {
                    "type": "web_search_result",
                    "target": "search-result.json",
                    "expected": "{\"query\":\"x\"}",
                }
            ],
        }
    )

    assert spec.validators[0].request_log is None
    assert spec.validators[0].request_path is None


def test_weekly_plan_task_validator_requires_target_and_expected() -> None:
    with pytest.raises(ValidationError, match="weekly_plan_task validator requires expected"):
        GripTestSpec.model_validate(
            {
                "id": "weekly_plan_next_week",
                "title": "Weekly Plan Next Week",
                "category": "scenario",
                "prompt": "plan",
                "validators": [
                    {
                        "type": "weekly_plan_task",
                        "target": "Plan.md",
                    }
                ],
            }
        )


def test_load_hardware_profiles_reads_profiles_yaml(tmp_path) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "hardware_profiles.yaml").write_text(
        "profiles:\n"
        "  - id: lab_a\n"
        "    label: Lab A\n"
        "    cpu: CPU\n"
        "    gpu: GPU\n"
        "    ram: 128GB\n",
        encoding="utf-8",
    )

    profiles = load_hardware_profiles(tmp_path)

    assert len(profiles) == 1
    assert profiles[0].id == "lab_a"
