from __future__ import annotations

import json
from pathlib import Path

from gripprobe.aggregate import discover_run_dirs
from gripprobe.runner import _fetch_ollama_model_digest


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _backfill_case_json(case_json_path: Path) -> bool:
    payload = _load_json(case_json_path)
    model = payload.get("model")
    if not isinstance(model, dict):
        return False
    if model.get("backend") != "ollama":
        return False
    model_id = model.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        return False
    digest = _fetch_ollama_model_digest(model_id.strip())
    if not digest:
        return False

    changed = False
    if model.get("model_hash") != digest:
        model["model_hash"] = digest
        changed = True

    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("model_hash") != digest:
        metadata["model_hash"] = digest
        changed = True

    if changed:
        _write_json(case_json_path, payload)
    return changed


def _backfill_manifest(run_dir: Path) -> bool:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return False
    payload = _load_json(manifest_path)
    if payload.get("backend") != "ollama":
        return False

    cases_dir = run_dir / "cases"
    if not cases_dir.exists():
        return False

    digest: str | None = None
    for case_dir in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
        case_json_path = case_dir / "case.json"
        if not case_json_path.exists():
            continue
        case_payload = _load_json(case_json_path)
        model = case_payload.get("model")
        if not isinstance(model, dict):
            continue
        model_id = model.get("model_id")
        backend = model.get("backend")
        if backend != "ollama" or not isinstance(model_id, str) or not model_id.strip():
            continue
        digest = _fetch_ollama_model_digest(model_id.strip())
        if digest:
            break

    if not digest:
        return False

    changed = False
    if payload.get("model_hash") != digest:
        payload["model_hash"] = digest
        changed = True

    run_metadata = payload.get("run_metadata")
    if isinstance(run_metadata, dict) and run_metadata.get("model_hash") != digest:
        run_metadata["model_hash"] = digest
        changed = True

    if changed:
        _write_json(manifest_path, payload)
    return changed


def backfill_model_hashes_for_run(run_dir: Path) -> dict[str, int]:
    run_dir = run_dir.resolve()
    cases_dir = run_dir / "cases"
    case_updates = 0
    manifest_updates = 0

    if cases_dir.exists():
        for case_dir in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
            case_json_path = case_dir / "case.json"
            if case_json_path.exists() and _backfill_case_json(case_json_path):
                case_updates += 1

    if _backfill_manifest(run_dir):
        manifest_updates = 1

    return {
        "runs": 1,
        "case_updates": case_updates,
        "manifest_updates": manifest_updates,
    }


def backfill_model_hashes(run_dirs: list[Path]) -> dict[str, int]:
    totals = {
        "runs": 0,
        "case_updates": 0,
        "manifest_updates": 0,
    }
    for run_dir in run_dirs:
        stats = backfill_model_hashes_for_run(run_dir)
        totals["runs"] += stats["runs"]
        totals["case_updates"] += stats["case_updates"]
        totals["manifest_updates"] += stats["manifest_updates"]
    return totals


def discover_and_backfill_model_hashes(runs_root: Path) -> dict[str, int]:
    return backfill_model_hashes(discover_run_dirs(runs_root))
