from __future__ import annotations

from pathlib import Path

from gripprobe.models import CaseResult


def write_markdown_summary(results: list[CaseResult], path: Path) -> None:
    lines = [
        "# GripProbe Run Summary",
        "",
        "| Shell | Model | Backend | Hash | Format | Test | Status | Trajectory | Invoked | Match | Warmup (s) | Measured (s) |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item.shell} | {item.model.label} | {item.model.backend} | {item.model.model_hash} | {item.format} | {item.title} | {item.status} | {item.trajectory} | {item.invoked} | {item.match_percent} | {item.timings.warmup_seconds} | {item.timings.measured_seconds} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
