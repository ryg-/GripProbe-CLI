from __future__ import annotations

import argparse
from pathlib import Path

from gripprobe.aggregate import aggregate_reports, discover_run_dirs
from gripprobe.backfill import backfill_model_hashes
from gripprobe.rebuild import rebuild_reports
from gripprobe.run_listing import list_runs_rows
from gripprobe.runner import DEFAULT_BACKEND, run
from gripprobe.spec_loader import (
    load_cli_agent_specs,
    load_hardware_profiles,
    load_model_specs,
    load_suite_specs,
    load_test_specs,
)
from gripprobe.suite_runner import run_suite



def cmd_validate(root: Path) -> int:
    tests = load_test_specs(root)
    models = load_model_specs(root)
    cli_agents = load_cli_agent_specs(root)
    suites = load_suite_specs(root)
    hardware_profiles = load_hardware_profiles(root)
    print(
        "Validated specs: "
        f"tests={len(tests)} "
        f"models={len(models)} "
        f"cli_agents={len(cli_agents)} "
        f"suites={len(suites)} "
        f"hardware_profiles={len(hardware_profiles)}"
    )
    return 0


def _parse_metadata(items: list[str] | None) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Invalid metadata entry {item!r}; expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid metadata entry {item!r}; key cannot be empty")
        metadata[key] = value
    return metadata



def cmd_run(
    root: Path,
    cli_agent: str,
    model: str,
    backend: str,
    tests: list[str] | None,
    test_tags: list[str] | None,
    formats: list[str] | None,
    container_image: str | None,
    keep_system_messages: bool,
    model_hash: str | None,
    metadata: dict[str, str],
    telemetry_proxy: str,
) -> int:
    run_dir, results = run(
        root,
        cli_agent_name=cli_agent,
        model_name=model,
        backend_name=backend,
        tests_filter=tests,
        test_tags_filter=test_tags,
        formats_filter=formats,
        container_image=container_image,
        keep_system_messages=keep_system_messages,
        model_hash=model_hash,
        run_metadata=metadata,
        telemetry_proxy_mode=telemetry_proxy,
        progress=lambda line: print(line, flush=True),
    )
    print(run_dir)
    print(f"cases={len(results)}")
    return 0





def cmd_rebuild_reports(run_dir: Path, keep_system_messages: bool, recompute_case_json: bool) -> int:
    rebuilt_dir, results = rebuild_reports(
        run_dir,
        keep_system_messages=keep_system_messages,
        recompute_case_json=recompute_case_json,
    )
    print(rebuilt_dir)
    print(f"cases={len(results)}")
    return 0


def cmd_aggregate_reports(root: Path, run_dirs: list[Path], output_dir: Path) -> int:
    aggregate_dir, results = aggregate_reports(run_dirs, output_dir, root=root)
    print(aggregate_dir)
    print(f"cases={len(results)}")
    return 0


def cmd_backfill_model_hashes(run_dirs: list[Path]) -> int:
    stats = backfill_model_hashes(run_dirs)
    print(f"runs={stats['runs']}")
    print(f"case_updates={stats['case_updates']}")
    print(f"manifest_updates={stats['manifest_updates']}")
    return 0


def cmd_list_runs(root: Path, run_dirs: list[Path], cli_agent: str | None, suite: str | None) -> int:
    print("path\tcli_agent\tsuite")
    for rel_path, row_cli_agent, row_suite in list_runs_rows(root, run_dirs):
        if cli_agent and row_cli_agent != cli_agent:
            continue
        if suite and row_suite != suite:
            continue
        print(f"{rel_path}\t{row_cli_agent}\t{row_suite}")
    return 0


def cmd_run_suite(
    root: Path,
    suite: str,
    cli_agents: list[str] | None,
    models: list[str] | None,
    tests: list[str] | None,
    test_tags: list[str] | None,
    formats: list[str] | None,
    container_image: str | None,
    keep_system_messages: bool,
    model_hash: str | None,
    metadata: dict[str, str],
    resume_suite: bool,
    telemetry_proxy: str,
) -> int:
    run_dirs = run_suite(
        root,
        suite_name=suite,
        cli_agents=cli_agents,
        models=models,
        tests=tests,
        test_tags=test_tags,
        formats=formats,
        container_image=container_image,
        keep_system_messages=keep_system_messages,
        model_hash=model_hash,
        metadata=metadata,
        resume_suite=resume_suite,
        telemetry_proxy_mode=telemetry_proxy,
    )
    for run_dir in run_dirs:
        print(run_dir)
    print(f"runs={len(run_dirs)}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gripprobe")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate")
    run_p = sub.add_parser("run")
    run_p.add_argument("--cli-agent")
    run_p.add_argument("--shell", help="Deprecated alias for --cli-agent")
    run_p.add_argument("--model", required=True)
    run_p.add_argument("--backend", default=DEFAULT_BACKEND)
    run_p.add_argument("--tests", nargs="*")
    run_p.add_argument("--test-tags", nargs="*")
    run_p.add_argument("--sanity", action="store_true", help="Run only tests tagged with sanity")
    run_p.add_argument("--formats", nargs="*")
    run_p.add_argument("--container-image")
    run_p.add_argument("--keep-system-messages", action="store_true")
    run_p.add_argument(
        "--model-hash",
        help="Optional fallback model hash. For Ollama, GripProbe now resolves the digest automatically via /api/tags when possible.",
    )
    run_p.add_argument("--metadata", action="append", help="Attach run metadata as key=value; may be passed multiple times")
    run_p.add_argument(
        "--telemetry-proxy",
        choices=["off", "auto", "force"],
        default="auto",
        help="Telemetry proxy mode: auto (default), off, or force. MVP currently extracts wrapper telemetry and records proxy mode as skipped/error metadata when proxy capture is unavailable.",
    )
    run_suite_p = sub.add_parser("run-suite")
    run_suite_p.add_argument("--suite", default="default_cli_matrix")
    run_suite_p.add_argument("--cli-agents", nargs="*")
    run_suite_p.add_argument("--shells", nargs="*", help="Deprecated alias for --cli-agents")
    run_suite_p.add_argument("--models", nargs="*")
    run_suite_p.add_argument("--tests", nargs="*")
    run_suite_p.add_argument("--test-tags", nargs="*")
    run_suite_p.add_argument("--formats", nargs="*")
    run_suite_p.add_argument("--container-image")
    run_suite_p.add_argument("--keep-system-messages", action="store_true")
    run_suite_p.add_argument(
        "--resume-suite",
        action="store_true",
        help="Resume per test case from existing results/runs: skip completed cli_agent/model/format/test cases and run only missing ones",
    )
    run_suite_p.add_argument(
        "--model-hash",
        help="Optional fallback model hash. For Ollama, GripProbe now resolves the digest automatically via /api/tags when possible.",
    )
    run_suite_p.add_argument("--metadata", action="append", help="Attach run metadata as key=value; may be passed multiple times")
    run_suite_p.add_argument(
        "--telemetry-proxy",
        choices=["off", "auto", "force"],
        default="auto",
        help="Telemetry proxy mode: auto (default), off, or force. MVP currently extracts wrapper telemetry and records proxy mode as skipped/error metadata when proxy capture is unavailable.",
    )
    rebuild_p = sub.add_parser("rebuild-reports")
    rebuild_p.add_argument("--run-dir", required=True)
    rebuild_p.add_argument("--keep-system-messages", action="store_true")
    rebuild_p.add_argument("--recompute-case-json", action="store_true")
    backfill_p = sub.add_parser("backfill-model-hashes")
    backfill_p.add_argument("--run-dir")
    backfill_p.add_argument("--runs-root")
    aggregate_p = sub.add_parser("aggregate-reports")
    aggregate_p.add_argument("--run-dirs", nargs="+")
    aggregate_p.add_argument("--runs-root")
    aggregate_p.add_argument("--output-dir", required=True)
    list_p = sub.add_parser("list-runs")
    list_p.add_argument("--runs-root")
    list_p.add_argument("--cli-agent")
    list_p.add_argument("--shell", help="Deprecated alias for --cli-agent")
    list_p.add_argument("--suite")
    return parser



def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    root = Path(ns.root).resolve()
    if ns.cmd == "validate":
        return cmd_validate(root)
    if ns.cmd == "run":
        cli_agent = (ns.cli_agent or ns.shell or "").strip()
        if not cli_agent:
            parser.error("run requires --cli-agent (or deprecated --shell)")
        if ns.cli_agent and ns.shell and ns.cli_agent != ns.shell:
            parser.error("run received conflicting --cli-agent and --shell values")
        try:
            metadata = _parse_metadata(ns.metadata)
        except ValueError as exc:
            parser.error(str(exc))
        test_tags = list(ns.test_tags or [])
        if ns.sanity and "sanity" not in test_tags:
            test_tags.append("sanity")
        return cmd_run(
            root,
            cli_agent=cli_agent,
            model=ns.model,
            backend=ns.backend,
            tests=ns.tests,
            test_tags=test_tags or None,
            formats=ns.formats,
            container_image=ns.container_image,
            keep_system_messages=ns.keep_system_messages,
            model_hash=ns.model_hash,
            metadata=metadata,
            telemetry_proxy=ns.telemetry_proxy,
        )
    if ns.cmd == "run-suite":
        cli_agents = ns.cli_agents if ns.cli_agents is not None else ns.shells
        if ns.cli_agents and ns.shells:
            cli_agents = [*ns.cli_agents, *[item for item in ns.shells if item not in set(ns.cli_agents)]]
        try:
            metadata = _parse_metadata(ns.metadata)
        except ValueError as exc:
            parser.error(str(exc))
        return cmd_run_suite(
            root,
            suite=ns.suite,
            cli_agents=cli_agents,
            models=ns.models,
            tests=ns.tests,
            test_tags=ns.test_tags,
            formats=ns.formats,
            container_image=ns.container_image,
            keep_system_messages=ns.keep_system_messages,
            model_hash=ns.model_hash,
            metadata=metadata,
            resume_suite=ns.resume_suite,
            telemetry_proxy=ns.telemetry_proxy,
        )
    if ns.cmd == "rebuild-reports":
        return cmd_rebuild_reports(
            Path(ns.run_dir).resolve(),
            keep_system_messages=ns.keep_system_messages,
            recompute_case_json=ns.recompute_case_json,
        )
    if ns.cmd == "backfill-model-hashes":
        if bool(ns.run_dir) == bool(ns.runs_root):
            parser.error("backfill-model-hashes requires exactly one of --run-dir or --runs-root")
        run_dirs = (
            [Path(ns.run_dir).resolve()]
            if ns.run_dir
            else discover_run_dirs(Path(ns.runs_root).resolve())
        )
        return cmd_backfill_model_hashes(run_dirs)
    if ns.cmd == "aggregate-reports":
        if bool(ns.run_dirs) == bool(ns.runs_root):
            parser.error("aggregate-reports requires exactly one of --run-dirs or --runs-root")
        run_dirs = (
            [Path(item).resolve() for item in ns.run_dirs]
            if ns.run_dirs
            else discover_run_dirs(Path(ns.runs_root).resolve())
        )
        return cmd_aggregate_reports(
            root,
            run_dirs,
            Path(ns.output_dir).resolve(),
        )
    if ns.cmd == "list-runs":
        runs_root = Path(ns.runs_root).resolve() if ns.runs_root else root / "results" / "runs"
        run_dirs = discover_run_dirs(runs_root)
        cli_agent_filter = ns.cli_agent or ns.shell
        return cmd_list_runs(root, run_dirs, cli_agent_filter, ns.suite)
    parser.error("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
