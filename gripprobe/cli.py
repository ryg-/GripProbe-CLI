from __future__ import annotations

import argparse
from pathlib import Path

from gripprobe.rebuild import rebuild_reports
from gripprobe.runner import DEFAULT_BACKEND, run
from gripprobe.spec_loader import load_model_specs, load_shell_specs, load_test_specs



def cmd_validate(root: Path) -> int:
    tests = load_test_specs(root)
    models = load_model_specs(root)
    shells = load_shell_specs(root)
    print(f"Validated specs: tests={len(tests)} models={len(models)} shells={len(shells)}")
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
    shell: str,
    model: str,
    backend: str,
    tests: list[str] | None,
    formats: list[str] | None,
    container_image: str | None,
    keep_system_messages: bool,
    metadata: dict[str, str],
) -> int:
    run_dir, results = run(
        root,
        shell_name=shell,
        model_name=model,
        backend_name=backend,
        tests_filter=tests,
        formats_filter=formats,
        container_image=container_image,
        keep_system_messages=keep_system_messages,
        run_metadata=metadata,
        progress=lambda line: print(line, flush=True),
    )
    print(run_dir)
    print(f"cases={len(results)}")
    return 0





def cmd_rebuild_reports(run_dir: Path, keep_system_messages: bool) -> int:
    rebuilt_dir, results = rebuild_reports(run_dir, keep_system_messages=keep_system_messages)
    print(rebuilt_dir)
    print(f"cases={len(results)}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gripprobe")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate")
    run_p = sub.add_parser("run")
    run_p.add_argument("--shell", required=True)
    run_p.add_argument("--model", required=True)
    run_p.add_argument("--backend", default=DEFAULT_BACKEND)
    run_p.add_argument("--tests", nargs="*")
    run_p.add_argument("--formats", nargs="*")
    run_p.add_argument("--container-image")
    run_p.add_argument("--keep-system-messages", action="store_true")
    run_p.add_argument("--metadata", action="append", help="Attach run metadata as key=value; may be passed multiple times")
    rebuild_p = sub.add_parser("rebuild-reports")
    rebuild_p.add_argument("--run-dir", required=True)
    rebuild_p.add_argument("--keep-system-messages", action="store_true")
    return parser



def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    root = Path(ns.root).resolve()
    if ns.cmd == "validate":
        return cmd_validate(root)
    if ns.cmd == "run":
        try:
            metadata = _parse_metadata(ns.metadata)
        except ValueError as exc:
            parser.error(str(exc))
        return cmd_run(
            root,
            shell=ns.shell,
            model=ns.model,
            backend=ns.backend,
            tests=ns.tests,
            formats=ns.formats,
            container_image=ns.container_image,
            keep_system_messages=ns.keep_system_messages,
            metadata=metadata,
        )
    if ns.cmd == "rebuild-reports":
        return cmd_rebuild_reports(
            Path(ns.run_dir).resolve(),
            keep_system_messages=ns.keep_system_messages,
        )
    parser.error("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
