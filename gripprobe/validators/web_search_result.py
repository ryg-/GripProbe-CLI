from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gripprobe.models import ValidatorSpec


def _read_request_paths(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    try:
        payload = json.loads(log_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _parse_expected_payload(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _matches_expected(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in observed:
            return False
        observed_value = observed[key]
        if isinstance(expected_value, (int, float)) and isinstance(observed_value, (int, float)):
            if float(observed_value) != float(expected_value):
                return False
            continue
        if observed_value != expected_value:
            return False
    return True


def validate_web_search_result(spec: ValidatorSpec, workspace: Path) -> tuple[bool, str, str]:
    if not spec.target or not spec.expected:
        return False, "", ""

    expected_payload = _parse_expected_payload(spec.expected)
    if expected_payload is None:
        return False, "INVALID_EXPECTED_JSON", ""

    target_path = workspace / spec.target
    request_log = spec.request_log
    request_path = spec.request_path
    request_check_enabled = bool(request_log) and bool(request_path)
    expected_suffix = f"\nREQUEST_HIT={request_path}" if request_check_enabled else ""

    if not target_path.exists():
        expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True)
        return False, expected + expected_suffix, "MISSING_FILE"

    try:
        observed_payload = json.loads(target_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True)
        return False, expected + expected_suffix, "INVALID_OBSERVED_JSON"
    if not isinstance(observed_payload, dict):
        expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True)
        return False, expected + expected_suffix, "INVALID_OBSERVED_JSON_SHAPE"

    hit = True
    if request_check_enabled:
        assert request_log is not None
        assert request_path is not None
        request_paths = _read_request_paths(Path(request_log))
        hit = request_path in request_paths
    values_ok = _matches_expected(expected_payload, observed_payload)

    expected = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True) + expected_suffix
    observed = json.dumps(observed_payload, ensure_ascii=False, sort_keys=True)
    if request_check_enabled:
        observed += f"\nREQUEST_HIT={'yes' if hit else 'no'}"
    return values_ok and hit, expected, observed
