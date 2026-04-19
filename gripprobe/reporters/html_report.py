from __future__ import annotations

from html import escape
from pathlib import Path

from gripprobe.models import CaseResult


def write_html_summary(results: list[CaseResult], path: Path) -> None:
    rows = []
    for item in results:
        rows.append(
            "<tr>"
            f"<td>{escape(item.shell)}</td>"
            f"<td>{escape(item.model.label)}</td>"
            f"<td>{escape(item.model.backend)}</td>"
            f"<td>{escape(item.model.model_hash)}</td>"
            f"<td>{escape(item.format)}</td>"
            f"<td>{escape(item.title)}</td>"
            f"<td>{escape(item.status)}</td>"
            f"<td>{escape(item.invoked)}</td>"
            f"<td>{item.match_percent}</td>"
            f"<td>{item.timings.warmup_seconds}</td>"
            f"<td>{item.timings.measured_seconds}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>GripProbe Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.5rem;text-align:left}}
th{{background:#ece8dc}}
</style></head><body>
<h1>GripProbe Run Summary</h1>
<table>
<thead><tr><th>Shell</th><th>Model</th><th>Backend</th><th>Hash</th><th>Format</th><th>Test</th><th>Status</th><th>Invoked</th><th>Match</th><th>Warmup (s)</th><th>Measured (s)</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table></body></html>"""
    path.write_text(html, encoding="utf-8")
