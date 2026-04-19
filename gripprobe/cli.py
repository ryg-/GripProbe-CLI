from __future__ import annotations

import argparse
from pathlib import Path

from gripprobe.runner import DEFAULT_BACKEND, run
from gripprobe.spec_loader import load_model_specs, load_shell_specs, load_test_specs



def cmd_validate(root: Path) -> int:
    tests = load_test_specs(root)
    models = load_model_specs(root)
    shells = load_shell_specs(root)
    print(f"Validated specs: tests={len(tests)} models={len(models)} shells={len(shells)}")
    return 0



def cmd_run(
    root: Path,
    shell: str,
    model: str,
    backend: str,
    tests: list[str] | None,
    formats: list[str] | None,
    container_image: str | None,
) -> int:
    run_dir, results = run(
        root,
        shell_name=shell,
        model_name=model,
        backend_name=backend,
        tests_filter=tests,
        formats_filter=formats,
        container_image=container_image,
    )
    print(run_dir)
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
    return parser



def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    root = Path(ns.root).resolve()
    if ns.cmd == "validate":
        return cmd_validate(root)
    if ns.cmd == "run":
        return cmd_run(
            root,
            shell=ns.shell,
            model=ns.model,
            backend=ns.backend,
            tests=ns.tests,
            formats=ns.formats,
            container_image=ns.container_image,
        )
    parser.error("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
