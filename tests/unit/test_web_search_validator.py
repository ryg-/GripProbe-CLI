from __future__ import annotations

import json
from pathlib import Path

from gripprobe.models import ValidatorSpec
from gripprobe.validators.web_search_result import validate_web_search_result


def _spec(request_log: Path, request_path: str, expected_payload: dict[str, str | float]) -> ValidatorSpec:
    return ValidatorSpec.model_validate(
        {
            "type": "web_search_result",
            "target": "search-result.json",
            "expected": json.dumps(expected_payload, ensure_ascii=False, sort_keys=True),
            "request_log": str(request_log),
            "request_path": request_path,
        }
    )


def test_web_search_result_validator_passes_for_matching_json_and_request_hit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    request_log = tmp_path / "requests.json"
    request_path = "/search/measured-1"
    payload = {
        "query": "weekly-plan-a1b2",
        "selected_id": "doc-1111",
        "selected_url": "https://kb.example/1111",
        "selected_score": 0.97,
    }
    (workspace / "search-result.json").write_text(json.dumps(payload), encoding="utf-8")
    request_log.write_text(json.dumps([request_path]) + "\n", encoding="utf-8")

    ok, expected, observed = validate_web_search_result(_spec(request_log, request_path, payload), workspace)

    assert ok is True
    assert "REQUEST_HIT=/search/measured-1" in expected
    assert "REQUEST_HIT=yes" in observed


def test_web_search_result_validator_fails_on_mismatch_or_missing_hit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    request_log = tmp_path / "requests.json"
    request_path = "/search/measured-2"
    expected_payload = {
        "query": "weekly-plan-c3d4",
        "selected_id": "doc-2222",
        "selected_url": "https://kb.example/2222",
        "selected_score": 0.97,
    }
    observed_payload = {
        "query": "weekly-plan-c3d4",
        "selected_id": "doc-wrong",
        "selected_url": "https://kb.example/2222",
        "selected_score": 0.97,
    }
    (workspace / "search-result.json").write_text(json.dumps(observed_payload), encoding="utf-8")
    request_log.write_text(json.dumps(["/search/warmup-2"]) + "\n", encoding="utf-8")

    ok, _expected, observed = validate_web_search_result(_spec(request_log, request_path, expected_payload), workspace)

    assert ok is False
    assert "REQUEST_HIT=no" in observed


def test_web_search_result_validator_passes_without_request_check_for_file_only_mode(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    payload = {
        "query": "weekly-plan-file-mode",
        "selected_id": "doc-3333",
        "selected_url": "https://kb.example/3333",
        "selected_score": 0.97,
    }
    (workspace / "search-result.json").write_text(json.dumps(payload), encoding="utf-8")
    spec = ValidatorSpec.model_validate(
        {
            "type": "web_search_result",
            "target": "search-result.json",
            "expected": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        }
    )

    ok, expected, observed = validate_web_search_result(spec, workspace)

    assert ok is True
    assert "REQUEST_HIT=" not in expected
    assert "REQUEST_HIT=" not in observed
