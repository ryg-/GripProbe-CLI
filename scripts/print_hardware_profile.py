#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import socket
import subprocess
from pathlib import Path


def _run_command(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


def _detect_cpu() -> str:
    lscpu = _run_command(["lscpu"])
    if lscpu:
        for line in lscpu.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip().lower() == "model name":
                candidate = value.strip()
                if candidate:
                    return candidate
    cpuinfo_path = Path("/proc/cpuinfo")
    if cpuinfo_path.exists():
        for line in cpuinfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip().lower() == "model name":
                candidate = value.strip()
                if candidate:
                    return candidate
    return "unknown"


def _detect_gpu() -> str:
    output = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader",
        ]
    )
    if not output:
        return "unknown"
    counts: dict[str, int] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        counts[line] = counts.get(line, 0) + 1
    if not counts:
        return "unknown"
    parts = []
    for name in sorted(counts):
        count = counts[name]
        suffix = f" x{count}" if count > 1 else ""
        parts.append(f"{name}{suffix}")
    return "; ".join(parts)


def _detect_ram() -> str:
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        return "unknown"
    for line in meminfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("MemTotal:"):
            continue
        match = re.search(r"(\d+)", line)
        if not match:
            break
        kib = int(match.group(1))
        gib = kib / (1024 * 1024)
        return f"{gib:.1f} GiB"
    return "unknown"


def _yaml_quote(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _default_profile_id(hostname: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", hostname.lower()).strip("_")
    return normalized or "unspecified"


def _print_profile(
    profile_id: str,
    label: str,
    cpu: str,
    gpu: str,
    ram: str,
    notes: str | None,
    item_only: bool,
) -> None:
    prefix = "  - " if not item_only else "- "
    indent = "    " if not item_only else "  "
    if not item_only:
        print("profiles:")
    print(f"{prefix}id: {_yaml_quote(profile_id)}")
    print(f"{indent}label: {_yaml_quote(label)}")
    print(f"{indent}cpu: {_yaml_quote(cpu)}")
    print(f"{indent}gpu: {_yaml_quote(gpu)}")
    print(f"{indent}ram: {_yaml_quote(ram)}")
    if notes:
        print(f"{indent}notes: {_yaml_quote(notes)}")


def main() -> int:
    hostname = socket.gethostname()
    parser = argparse.ArgumentParser(
        description="Print a GripProbe hardware profile YAML block to stdout.",
    )
    parser.add_argument("--id", default=_default_profile_id(hostname), help="hardware profile id")
    parser.add_argument("--label", default=hostname, help="human-readable profile label")
    parser.add_argument("--notes", default="", help="optional notes")
    parser.add_argument("--cpu", help="override detected CPU label")
    parser.add_argument("--gpu", help="override detected GPU label")
    parser.add_argument("--ram", help="override detected RAM label")
    parser.add_argument(
        "--item-only",
        action="store_true",
        help="print only one list item (without top-level profiles: key)",
    )
    args = parser.parse_args()

    profile_id = args.id.strip() or "unspecified"
    label = args.label.strip() or profile_id
    cpu = args.cpu or _detect_cpu()
    gpu = args.gpu or _detect_gpu()
    ram = args.ram or _detect_ram()
    notes = args.notes.strip() or None
    _print_profile(profile_id, label, cpu, gpu, ram, notes, args.item_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
