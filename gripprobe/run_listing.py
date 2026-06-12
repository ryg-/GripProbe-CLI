from __future__ import annotations

import json
import os
from pathlib import Path


def _read_json_dict(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _infer_cli_agent_from_cases(run_dir: Path) -> str:
    cases_dir = run_dir / "cases"
    if not cases_dir.exists():
        return "unknown"
    cli_agents: set[str] = set()
    for case_dir in cases_dir.iterdir():
        if not case_dir.is_dir():
            continue
        name = case_dir.name
        if "__" not in name:
            continue
        cli_agents.add(name.split("__", 1)[0].strip())
    if not cli_agents:
        return "unknown"
    if len(cli_agents) == 1:
        return next(iter(cli_agents))
    return ",".join(sorted(cli_agents))


def _extract_cli_agent(manifest: dict[str, object] | None, run_dir: Path) -> str:
    if manifest is not None:
        cli_agent_id = manifest.get("cli_agent_id")
        if isinstance(cli_agent_id, str) and cli_agent_id.strip():
            return cli_agent_id.strip()
        shell = manifest.get("shell")
        if isinstance(shell, str) and shell.strip():
            return shell.strip()
    return _infer_cli_agent_from_cases(run_dir)


def _extract_suite(manifest: dict[str, object] | None) -> str:
    if manifest is None:
        return "ad-hoc"
    run_metadata = manifest.get("run_metadata")
    if isinstance(run_metadata, dict):
        suite = run_metadata.get("suite")
        if isinstance(suite, str) and suite.strip():
            return suite.strip()
    suite_top_level = manifest.get("suite")
    if isinstance(suite_top_level, str) and suite_top_level.strip():
        return suite_top_level.strip()
    return "ad-hoc"


def list_runs_rows(root: Path, run_dirs: list[Path]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for run_dir in sorted(run_dirs):
        manifest = _read_json_dict(run_dir / "manifest.json")
        cli_agent = _extract_cli_agent(manifest, run_dir)
        suite = _extract_suite(manifest)
        try:
            rel_path = os.path.relpath(run_dir, root)
        except ValueError:
            rel_path = str(run_dir)
        rows.append((rel_path, cli_agent, suite))
    return rows
