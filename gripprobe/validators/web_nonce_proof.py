from __future__ import annotations

import json
from pathlib import Path

from gripprobe.models import ValidatorSpec


def _expected_file_text(spec: ValidatorSpec) -> str:
    nonce = spec.nonce or ""
    payload = spec.payload or ""
    proof = spec.proof or ""
    return "\n".join(
        [
            f"NONCE={nonce}",
            f"PAYLOAD={payload}",
            f"PROOF={proof}",
        ]
    )


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


def validate_web_nonce_proof(spec: ValidatorSpec, workspace: Path) -> tuple[bool, str, str]:
    expected_file = _expected_file_text(spec)
    expected_path = spec.request_path or ""
    expected = expected_file + (f"\nREQUEST_HIT={expected_path}" if expected_path else "")

    if not spec.target:
        return False, expected, ""

    target_path = workspace / spec.target
    observed_file = ""
    if target_path.exists():
        observed_file = target_path.read_text(encoding="utf-8", errors="replace").replace("\r", "").strip("\n")

    hit = False
    if spec.request_log and expected_path:
        request_paths = _read_request_paths(Path(spec.request_log))
        hit = expected_path in request_paths

    observed_hit = "yes" if hit else "no"
    observed = observed_file + f"\nREQUEST_HIT={observed_hit}"
    return observed_file == expected_file and hit, expected, observed
