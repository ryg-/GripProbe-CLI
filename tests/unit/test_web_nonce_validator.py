from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gripprobe.models import ValidatorSpec
from gripprobe.validators.web_nonce_proof import validate_web_nonce_proof


def _proof(nonce: str, payload: str) -> str:
    return hashlib.sha256(f"{nonce}:{payload}".encode("utf-8")).hexdigest()


def _spec(request_log: Path, request_path: str, nonce: str, payload: str) -> ValidatorSpec:
    return ValidatorSpec.model_validate(
        {
            "type": "web_nonce_proof",
            "target": "web-proof.txt",
            "nonce": nonce,
            "payload": payload,
            "proof": _proof(nonce, payload),
            "request_log": str(request_log),
            "request_path": request_path,
        }
    )


def test_web_nonce_proof_validator_passes_on_matching_file_and_hit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    request_log = tmp_path / "requests.json"
    request_path = "/challenge/measured-1"
    nonce = "abc123"
    payload = "def456"
    proof = _proof(nonce, payload)

    (workspace / "web-proof.txt").write_text(
        f"NONCE={nonce}\nPAYLOAD={payload}\nPROOF={proof}\n",
        encoding="utf-8",
    )
    request_log.write_text(json.dumps([request_path]) + "\n", encoding="utf-8")

    ok, expected, observed = validate_web_nonce_proof(
        _spec(request_log, request_path, nonce, payload),
        workspace,
    )

    assert ok is True
    assert "REQUEST_HIT=/challenge/measured-1" in expected
    assert "REQUEST_HIT=yes" in observed


def test_web_nonce_proof_validator_fails_without_request_hit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    request_log = tmp_path / "requests.json"
    request_path = "/challenge/measured-2"
    nonce = "abc123"
    payload = "def456"
    proof = _proof(nonce, payload)

    (workspace / "web-proof.txt").write_text(
        f"NONCE={nonce}\nPAYLOAD={payload}\nPROOF={proof}\n",
        encoding="utf-8",
    )
    request_log.write_text(json.dumps(["/challenge/warmup-2"]) + "\n", encoding="utf-8")

    ok, _expected, observed = validate_web_nonce_proof(
        _spec(request_log, request_path, nonce, payload),
        workspace,
    )

    assert ok is False
    assert "REQUEST_HIT=no" in observed
