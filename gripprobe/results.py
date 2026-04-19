from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    root: Path
    run_id: str
    run_dir: Path
    cases_dir: Path
    reports_dir: Path


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_run_paths(root: Path, run_id: str | None = None) -> RunPaths:
    rid = run_id or utc_run_id()
    run_dir = root / "results" / "runs" / rid
    cases_dir = run_dir / "cases"
    reports_dir = run_dir / "reports"
    cases_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(root=root, run_id=rid, run_dir=run_dir, cases_dir=cases_dir, reports_dir=reports_dir)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def remove_transient_files(root: Path, names: tuple[str, ...] = (".lock",)) -> None:
    if not root.exists():
        return
    for name in names:
        for path in root.rglob(name):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
