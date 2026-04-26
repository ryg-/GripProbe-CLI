from __future__ import annotations

from pathlib import Path

from gripprobe.adapters.base import AdapterError
from gripprobe.models import TestSpec, ValidatorSpec
from gripprobe.validators.file_equals import validate_file_equals
from gripprobe.validators.patch_applied import validate_patch_applied
from gripprobe.validators.web_search_result import validate_web_search_result
from gripprobe.validators.web_nonce_proof import validate_web_nonce_proof
from gripprobe.validators.weekly_plan_task import validate_weekly_plan_task


ValidatorResult = tuple[bool, str, str]


def run_validator(spec: ValidatorSpec, workspace: Path) -> ValidatorResult:
    if spec.type == "file_equals":
        return validate_file_equals(spec, workspace)
    if spec.type == "patch_applied":
        return validate_patch_applied(spec, workspace)
    if spec.type == "web_nonce_proof":
        return validate_web_nonce_proof(spec, workspace)
    if spec.type == "web_search_result":
        return validate_web_search_result(spec, workspace)
    if spec.type == "weekly_plan_task":
        return validate_weekly_plan_task(spec, workspace)
    raise AdapterError(f"Unsupported validator: {spec.type}")


def evaluate_validators(test_spec: TestSpec, workspace: Path) -> ValidatorResult:
    expected_parts: list[str] = []
    observed_parts: list[str] = []
    overall_ok = True

    for validator in test_spec.validators:
        ok, expected, observed = run_validator(validator, workspace)
        overall_ok = overall_ok and ok
        expected_parts.append(expected)
        observed_parts.append(observed)

    return overall_ok, "\n".join(filter(None, expected_parts)), "\n".join(filter(None, observed_parts))
