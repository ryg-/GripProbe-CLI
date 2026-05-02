from __future__ import annotations

import difflib
import json
import os
import re
from html import escape
from pathlib import Path

from gripprobe.models import CaseResult


TEXT_ARTIFACTS = (
    "prompt.txt",
    "warmup.stdout",
    "warmup.stderr",
    "measured.stdout",
    "measured.stderr",
    "expected.txt",
    "observed.txt",
    "model.modelfile",
    "case.json",
)
STATUS_CLASS = {
    "PASS": "pass",
    "FAIL": "fail",
    "TIMEOUT": "timeout",
    "NO_TOOL_CALL": "notool",
    "TOOL_UNSUPPORTED": "unsupported",
    "SHELL_ERROR": "fail",
    "HARNESS_ERROR": "fail",
    "SKIPPED": "skipped",
}
TRAJECTORY_CLASS = {
    "clean": "traj-clean",
    "recovered": "traj-recovered",
    "violated": "traj-violated",
}
INVOKED_CLASS = {
    "yes": "invoked-yes",
    "no": "invoked-no",
    "maybe": "invoked-maybe",
}

_CLASS_ATTR_PATTERN = re.compile(r"class=['\"]([^'\"]+)['\"]")
_CSS_CLASS_ORDER = (
    "muted",
    "badge",
    "pass",
    "fail",
    "timeout",
    "timeout-artifact",
    "notool",
    "unsupported",
    "skipped",
    "unknown",
    "traj-clean",
    "traj-recovered",
    "traj-violated",
    "invoked-yes",
    "invoked-no",
    "invoked-maybe",
    "match-full",
    "match-partial",
    "match-none",
    "ok",
)
_CSS_CLASS_RULES = {
    "muted": ".muted{color:#666}",
    "badge": ".badge{display:inline-block;padding:.2rem .6rem;border-radius:999px;font-weight:700}",
    "pass": ".pass{background:#d9f2df;color:#115c23}",
    "fail": ".fail{background:#f9d7d7;color:#7a1520}",
    "timeout": ".timeout{background:#fde6c8;color:#7d4b00}",
    "timeout-artifact": ".timeout-artifact{background:#d8f0e1;color:#165a30}",
    "notool": ".notool{background:#e6e1ff;color:#44318d}",
    "unsupported": ".unsupported{background:#e6eefb;color:#1f4c8f}",
    "skipped": ".skipped{background:#ececec;color:#555}",
    "unknown": ".unknown{background:#eee;color:#333}",
    "traj-clean": ".traj-clean{background:#dff3e4;color:#1f6b33}",
    "traj-recovered": ".traj-recovered{background:#fff0cc;color:#8a5a00}",
    "traj-violated": ".traj-violated{background:#f7d6db;color:#8a1f2d}",
    "invoked-yes": ".invoked-yes{background:#d9ecff;color:#0b4f92}",
    "invoked-no": ".invoked-no{background:#ececec;color:#555}",
    "invoked-maybe": ".invoked-maybe{background:#efe3ff;color:#5b2f8f}",
    "match-full": ".match-full{background:#d9f2df;color:#115c23}",
    "match-partial": ".match-partial{background:#fff0cc;color:#8a5a00}",
    "match-none": ".match-none{background:#f9d7d7;color:#7a1520}",
    "ok": ".ok{color:#115c23;font-weight:600}",
}


def _collect_css_classes(html_fragment: str) -> set[str]:
    classes: set[str] = set()
    for match in _CLASS_ATTR_PATTERN.finditer(html_fragment):
        for token in match.group(1).split():
            if token:
                classes.add(token)
    return classes


def _render_conditional_css(html_fragment: str) -> str:
    classes = _collect_css_classes(html_fragment)
    rules: list[str] = []
    for class_name in _CSS_CLASS_ORDER:
        if class_name in classes:
            rule = _CSS_CLASS_RULES.get(class_name)
            if rule:
                rules.append(rule)
    return "\n".join(rules)

def _sanitize_user_paths(text: str) -> str:
    sanitized = re.sub(r"(?<![\w$])/(?:home|Users)/[^/\s\"'<>:]+", "$HOME", text)
    sanitized = re.sub(r"(?<![\w$])[A-Za-z]:\\+Users\\+[^\\/\s\"'<>:]+", "$HOME", sanitized)
    return sanitized


def _sanitize_local_username(text: str) -> str:
    username = Path.home().name
    if not username:
        return text
    return re.sub(rf"(?<![A-Za-z0-9_.-]){re.escape(username)}(?![A-Za-z0-9_.-])", "$USER", text)


def _sanitize_for_html(text: str) -> str:
    return _sanitize_local_username(_sanitize_user_paths(text))


def _sanitize_obj(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_for_html(value)
    if isinstance(value, list):
        return [_sanitize_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_obj(item) for key, item in value.items()}
    return value


def _match_class(match_percent: int) -> str:
    if match_percent >= 100:
        return "match-full"
    if match_percent > 0:
        return "match-partial"
    return "match-none"


def _timeout_artifact_reached(result: CaseResult) -> bool:
    return result.status == "TIMEOUT" and bool(result.metadata.get("artifact_reached_before_timeout"))


def _status_badges(result: CaseResult) -> str:
    status_class = STATUS_CLASS.get(result.status, "unknown")
    badges = [f"<span class='badge {status_class}'>{escape(result.status)}</span>"]
    if _timeout_artifact_reached(result):
        badges.append("<span class='badge timeout-artifact'>artifact reached</span>")
    return " ".join(badges)


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return _sanitize_for_html(path.read_text(encoding="utf-8", errors="replace"))


def _find_conversation_jsonl(case_dir: Path) -> Path | None:
    matches = sorted(case_dir.rglob("conversation.jsonl"))
    return matches[0] if matches else None


def _render_transcript(case_dir: Path) -> str:
    convo_path = _find_conversation_jsonl(case_dir)
    if convo_path is None:
        return "<p class='muted'>No structured session transcript found.</p>"

    rows: list[str] = []
    for line in convo_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = escape(str(item.get("role", "unknown")))
        content = escape(_sanitize_for_html(str(item.get("content", ""))))
        rows.append(
            "<section class='message'>"
            f"<h3>{role}</h3>"
            f"<pre>{content}</pre>"
            "</section>"
        )
    if not rows:
        return "<p class='muted'>Transcript file exists but could not be parsed.</p>"
    return "\n".join(rows)


def _render_artifact_links(case_dir: Path, detail_path: Path) -> str:
    links: list[str] = []
    for name in TEXT_ARTIFACTS:
        artifact = case_dir / name
        if artifact.exists():
            rel = escape(os.path.relpath(artifact, detail_path.parent))
            links.append(f"<li><a href='{rel}'>{escape(name)}</a></li>")
    convo_path = _find_conversation_jsonl(case_dir)
    if convo_path is not None:
        rel = escape(os.path.relpath(convo_path, detail_path.parent))
        links.append(f"<li><a href='{rel}'>conversation.jsonl</a></li>")
    workspace = case_dir / "workspace"
    if workspace.exists():
        for artifact in sorted(workspace.rglob("*")):
            if artifact.is_file():
                rel = escape(os.path.relpath(artifact, detail_path.parent))
                label = escape(f"workspace/{artifact.relative_to(workspace)}")
                links.append(f"<li><a href='{rel}'>{label}</a></li>")
    if not links:
        return "<p class='muted'>No raw artifacts found.</p>"
    return "<ul>" + "".join(links) + "</ul>"


def _render_diff(expected_text: str, observed_text: str) -> str:
    if not expected_text and not observed_text:
        return "<p class='muted'>No expected/observed content.</p>"
    if expected_text == observed_text:
        return "<p class='ok'>Expected and observed match.</p>"
    diff = "\n".join(
        difflib.unified_diff(
            expected_text.splitlines(),
            observed_text.splitlines(),
            fromfile="expected",
            tofile="observed",
            lineterm="",
        )
    )
    return f"<pre>{escape(diff)}</pre>"


def _panel(title: str, content: str) -> str:
    if not content.strip():
        return ""
    return f"<div class='panel'><h2>{escape(title)}</h2>{content}</div>"


def _pre_block(text: str) -> str:
    if not text.strip():
        return ""
    return f"<pre>{escape(text)}</pre>"


def _render_shell_commands(result: CaseResult) -> str:
    warmup_command = _sanitize_for_html(str(result.metadata.get("warmup_command") or "")).strip()
    measured_command = _sanitize_for_html(str(result.metadata.get("measured_command") or "")).strip()
    if not warmup_command and not measured_command:
        return ""
    parts: list[str] = []
    if warmup_command:
        parts.append(f"<h3>Warmup</h3><pre>{escape(warmup_command)}</pre>")
    if measured_command:
        parts.append(f"<h3>Measured</h3><pre>{escape(measured_command)}</pre>")
    return "".join(parts)


def _render_case_json_panel_text(case_dir: Path) -> str:
    case_json_path = case_dir / "case.json"
    raw = _read_text(case_json_path)
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and "shell_executable_path" in metadata:
        metadata = dict(metadata)
        metadata["shell_executable_path"] = "[hidden in HTML]"
        payload["metadata"] = metadata
    payload = _sanitize_obj(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _render_run_comparison(case_json_raw: str) -> str:
    if not case_json_raw.strip():
        return ""
    try:
        payload = json.loads(case_json_raw)
    except json.JSONDecodeError:
        return ""
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    run_consistency = metadata.get("run_consistency")
    run_1_status = metadata.get("run_1_status")
    run_2_status = metadata.get("run_2_status")
    run_1_profile = metadata.get("run_1_profile")
    run_2_profile = metadata.get("run_2_profile")
    if not any((run_consistency, run_1_status, run_2_status, run_1_profile, run_2_profile)):
        return ""
    blocks: list[str] = []
    if run_consistency:
        blocks.append(f"<p><strong>Consistency:</strong> {escape(str(run_consistency))}</p>")
    for label, status, profile in (
        ("Run 1", run_1_status, run_1_profile),
        ("Run 2", run_2_status, run_2_profile),
    ):
        if not status and not isinstance(profile, dict):
            continue
        rows = []
        if status:
            rows.append(f"<li><strong>Status:</strong> {escape(str(status))}</li>")
        if isinstance(profile, dict):
            for key in (
                "invoked",
                "tool_attempt_count",
                "error_count",
                "repeated_error_count",
                "loop_detected",
                "markdown_tool_imitation",
                "no_tool_call_after_completion",
                "dominant_error",
            ):
                if key in profile:
                    rows.append(f"<li><strong>{escape(key)}:</strong> {escape(str(profile[key]))}</li>")
        blocks.append(f"<div class='panel'><h3>{escape(label)}</h3><ul>{''.join(rows)}</ul></div>")
    if not blocks:
        return ""
    return "<div class='grid'>" + "".join(blocks) + "</div>"


def _render_trajectory_hints(case_json_raw: str) -> str:
    if not case_json_raw.strip():
        return ""
    try:
        payload = json.loads(case_json_raw)
    except json.JSONDecodeError:
        return ""
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    reasons = metadata.get("trajectory_reasons")
    reason_items = ""
    if isinstance(reasons, list):
        reason_items = "".join(f"<li>{escape(str(reason))}</li>" for reason in reasons)
    legend = (
        "<ul>"
        "<li><strong>clean</strong>: no execution errors, no loop pattern, no contradictory DONE/FAIL text</li>"
        "<li><strong>recovered</strong>: result reached but trace shows errors, retries, or contradictory completion text</li>"
        "<li><strong>violated</strong>: result reached after breaking an explicit structured rule such as no_retry_on_error</li>"
        "</ul>"
    )
    current = f"<h3>Current Case</h3><ul>{reason_items}</ul>" if reason_items else ""
    return legend + current


def _render_failure_reason(case_json_raw: str) -> str:
    if not case_json_raw.strip():
        return ""
    try:
        payload = json.loads(case_json_raw)
    except json.JSONDecodeError:
        return ""
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    failure_reason = metadata.get("failure_reason")
    if not failure_reason:
        return ""
    return f"<p><strong>Failure Reason:</strong> {escape(str(failure_reason))}</p>"


def _render_runtime_snapshot(snapshot: object) -> str:
    if not isinstance(snapshot, dict):
        return ""
    probes = snapshot.get("probes")
    if not isinstance(probes, dict):
        return ""
    blocks: list[str] = []
    captured_at = snapshot.get("captured_at")
    if captured_at:
        blocks.append(f"<p><strong>Captured:</strong> {escape(_sanitize_for_html(str(captured_at)))}</p>")
    for probe_name, probe_payload in probes.items():
        if not isinstance(probe_payload, dict):
            continue
        command = escape(_sanitize_for_html(str(probe_payload.get("command", ""))))
        status = escape(_sanitize_for_html(str(probe_payload.get("status", ""))))
        duration = escape(_sanitize_for_html(str(probe_payload.get("duration_seconds", ""))))
        exit_code = probe_payload.get("exit_code")
        stdout = escape(_sanitize_for_html(str(probe_payload.get("stdout", ""))))
        stderr = escape(_sanitize_for_html(str(probe_payload.get("stderr", ""))))
        error = escape(_sanitize_for_html(str(probe_payload.get("error", ""))))
        meta = [f"<li><strong>Status:</strong> {status}</li>"]
        if command:
            meta.append(f"<li><strong>Command:</strong> <code>{command}</code></li>")
        if duration:
            meta.append(f"<li><strong>Duration:</strong> {duration}s</li>")
        if exit_code is not None:
            meta.append(f"<li><strong>Exit Code:</strong> {escape(str(exit_code))}</li>")
        if error:
            meta.append(f"<li><strong>Error:</strong> {error}</li>")
        body = f"<ul>{''.join(meta)}</ul>"
        if stdout:
            body += f"<h4>stdout</h4><pre>{stdout}</pre>"
        if stderr:
            body += f"<h4>stderr</h4><pre>{stderr}</pre>"
        blocks.append(f"<div class='panel'><h3>{escape(str(probe_name))}</h3>{body}</div>")
    if not blocks:
        return ""
    return "<div class='grid'>" + "".join(blocks) + "</div>"


def _render_case_runtime_snapshots(case_json_raw: str) -> str:
    if not case_json_raw.strip():
        return ""
    try:
        payload = json.loads(case_json_raw)
    except json.JSONDecodeError:
        return ""
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    snapshots = metadata.get("runtime_snapshots")
    if not isinstance(snapshots, dict):
        return ""
    sections: list[str] = []
    for label, key in (("Before Case", "before"), ("After Case", "after")):
        rendered = _render_runtime_snapshot(snapshots.get(key))
        if rendered:
            sections.append(f"<h3>{escape(label)}</h3>{rendered}")
    return "".join(sections)


def _render_run_runtime_snapshots(reports_dir: Path) -> str:
    manifest_path = reports_dir.parent / "manifest.json"
    if not manifest_path.exists():
        return ""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    run_metadata = payload.get("run_metadata")
    if not isinstance(run_metadata, dict):
        return ""
    snapshots = run_metadata.get("runtime_snapshots")
    if not isinstance(snapshots, dict):
        return ""
    sections: list[str] = []
    for label, key in (("Run Start", "run_started"), ("Run Finish", "run_finished")):
        rendered = _render_runtime_snapshot(snapshots.get(key))
        if rendered:
            sections.append(f"<h2>{escape(label)}</h2>{rendered}")
    return "".join(sections)


def _write_case_detail(
    result: CaseResult,
    reports_dir: Path,
    case_dir: Path,
    detail_filename: str | None = None,
    show_artifacts: bool = True,
    show_runtime_snapshots: bool = True,
    show_case_json: bool = True,
) -> str:
    details_dir = reports_dir / "cases"
    details_dir.mkdir(parents=True, exist_ok=True)
    detail_path = details_dir / (detail_filename or f"{result.case_id}.html")
    prompt_raw = _read_text(case_dir / "prompt.txt")
    warmup_stdout_raw = _read_text(case_dir / "warmup.stdout")
    warmup_stderr_raw = _read_text(case_dir / "warmup.stderr")
    measured_stdout_raw = _read_text(case_dir / "measured.stdout")
    measured_stderr_raw = _read_text(case_dir / "measured.stderr")
    expected_raw = _read_text(case_dir / "expected.txt")
    observed_raw = _read_text(case_dir / "observed.txt")
    case_json_raw = _render_case_json_panel_text(case_dir)
    run_comparison_html = _render_run_comparison(case_json_raw)
    trajectory_hints_html = _render_trajectory_hints(case_json_raw)
    failure_reason_html = _render_failure_reason(case_json_raw)
    runtime_snapshots_html = _render_case_runtime_snapshots(case_json_raw) if show_runtime_snapshots else ""
    shell_commands_html = _render_shell_commands(result)
    transcript_html = _render_transcript(case_dir)
    artifact_links = _render_artifact_links(case_dir, detail_path) if show_artifacts else ""
    modelfile_raw = _read_text(case_dir / "model.modelfile")
    summary_rel = escape(os.path.relpath(reports_dir / "summary.html", detail_path.parent))
    trajectory_class = TRAJECTORY_CLASS.get(result.trajectory, "unknown")
    invoked_class = INVOKED_CLASS.get(result.invoked, "unknown")
    match_class = _match_class(result.match_percent)

    top_panels = "".join(
        panel for panel in [
            _panel("Prompt", _pre_block(prompt_raw)),
            _panel("Expected", _pre_block(expected_raw)),
            _panel("Observed", _pre_block(observed_raw)),
            _panel("Case JSON", _pre_block(case_json_raw)) if show_case_json else "",
        ]
        if panel
    )
    output_panels = "".join(
        panel for panel in [
            _panel("Warmup stdout", _pre_block(warmup_stdout_raw)),
            _panel("Warmup stderr", _pre_block(warmup_stderr_raw)),
            _panel("Measured stdout", _pre_block(measured_stdout_raw)),
            _panel("Measured stderr", _pre_block(measured_stderr_raw)),
        ]
        if panel
    )
    diff_html = _render_diff(expected_raw, observed_raw)
    detail_body = f"""<p><a href='{summary_rel}'>Back to summary</a></p>
<h1>{escape(result.title)}</h1>
<p><strong>Case:</strong> <code>{escape(result.case_id)}</code></p>
<p>{_status_badges(result)} <strong>Trajectory:</strong> <span class='badge {trajectory_class}'>{escape(result.trajectory)}</span> | <strong>Invoked:</strong> <span class='badge {invoked_class}'>{escape(result.invoked)}</span> | <strong>Match:</strong> <span class='badge {match_class}'>{result.match_percent}%</span></p>
{failure_reason_html}
{("<p class='ok'>The expected workspace artifact was present before the harness timeout elapsed.</p>") if _timeout_artifact_reached(result) else ''}
{('<section><h2>Shell Commands</h2>' + shell_commands_html + '</section>') if shell_commands_html else ''}
{('<section><h2>Runtime Snapshots</h2>' + runtime_snapshots_html + '</section>') if runtime_snapshots_html else ''}
{('<section><h2>Trajectory Hints</h2>' + trajectory_hints_html + '</section>') if trajectory_hints_html else ''}
{('<section><h2>Run Comparison</h2>' + run_comparison_html + '</section>') if run_comparison_html else ''}
{('<div class="grid">' + top_panels + '</div>') if top_panels else ''}
<section>
<h2>Expected vs Observed</h2>
{diff_html}
</section>
<section>
<h2>Session Transcript</h2>
{transcript_html}
</section>
{('<section><h2>Tool / Process Output</h2><div class="grid">' + output_panels + '</div></section>') if output_panels else ''}
{('<section><h2>Raw Artifacts</h2>' + artifact_links + '</section>') if artifact_links else ''}
{('<section><h2>Model Modelfile (Ollama)</h2>' + _pre_block(modelfile_raw) + '</section>') if modelfile_raw.strip() else ''}"""
    badge_css = _render_conditional_css(detail_body)

    html = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><title>{escape(result.case_id)}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111;line-height:1.45}}
a{{color:#0b57d0}}
pre{{white-space:pre-wrap;word-break:break-word;background:#f0eee8;padding:1rem;border:1px solid #d6d1c4;border-radius:6px}}
code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
section{{margin:1.5rem 0}}
.message{{border-top:1px solid #d6d1c4;padding-top:1rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}}
.panel{{background:#fbfaf7;border:1px solid #d6d1c4;border-radius:8px;padding:1rem}}
{badge_css}
</style></head><body>
{detail_body}
</body></html>"""
    detail_path.write_text(html, encoding="utf-8")
    return str(detail_path.relative_to(reports_dir))


def write_case_detail_pages(
    results: list[CaseResult],
    reports_dir: Path,
    cases_dir: Path,
    detail_filenames: dict[str, str] | None = None,
    show_artifacts: bool = True,
    show_runtime_snapshots: bool = True,
    show_case_json: bool = True,
) -> dict[str, str]:
    return {
        item.case_id: _write_case_detail(
            item,
            reports_dir,
            cases_dir / item.case_id,
            detail_filename=(detail_filenames or {}).get(item.case_id),
            show_artifacts=show_artifacts,
            show_runtime_snapshots=show_runtime_snapshots,
            show_case_json=show_case_json,
        )
        for item in results
    }


def write_html_summary(results: list[CaseResult], path: Path) -> None:
    reports_dir = path.parent
    cases_dir = reports_dir.parent / "cases"
    detail_links = write_case_detail_pages(results, reports_dir, cases_dir)
    run_runtime_snapshots_html = _render_run_runtime_snapshots(reports_dir)
    rows = []
    for item in results:
        detail_rel = detail_links[item.case_id]
        trajectory_class = TRAJECTORY_CLASS.get(item.trajectory, "unknown")
        invoked_class = INVOKED_CLASS.get(item.invoked, "unknown")
        match_class = _match_class(item.match_percent)
        rows.append(
            "<tr>"
            f"<td>{escape(item.shell)}</td>"
            f"<td>{escape(item.model.label)}</td>"
            f"<td>{escape(item.model.backend)}</td>"
            f"<td>{escape(item.model.model_hash)}</td>"
            f"<td>{escape(item.format)}</td>"
            f"<td>{escape(item.title)}</td>"
            f"<td>{_status_badges(item)}</td>"
            f"<td>{escape(_sanitize_for_html(str(item.metadata.get('failure_reason') or '')))}</td>"
            f"<td><span class='badge {trajectory_class}'>{escape(item.trajectory)}</span></td>"
            f"<td><span class='badge {invoked_class}'>{escape(item.invoked)}</span></td>"
            f"<td><span class='badge {match_class}'>{item.match_percent}%</span></td>"
            f"<td>{item.timings.warmup_seconds}</td>"
            f"<td>{item.timings.measured_seconds}</td>"
            f"<td><a href='{escape(detail_rel)}'>details</a></td>"
            "</tr>"
        )
    summary_body = f"""<h1>GripProbe Run Summary</h1>
{('<section><h1>Runtime Snapshots</h1>' + run_runtime_snapshots_html + '</section>') if run_runtime_snapshots_html else ''}
<table>
<thead><tr><th>Shell</th><th>Model</th><th>Backend</th><th>Hash</th><th>Format</th><th>Test</th><th>Status</th><th>Reason</th><th>Trajectory</th><th>Invoked</th><th>Match</th><th>Warmup (s)</th><th>Measured (s)</th><th>Details</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>"""
    badge_css = _render_conditional_css(summary_body)
    html = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><title>GripProbe Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.5rem;text-align:left;vertical-align:top}}
th{{background:#ece8dc}}
a{{color:#0b57d0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}}
.panel{{background:#fbfaf7;border:1px solid #d6d1c4;border-radius:8px;padding:1rem;margin-bottom:1rem}}
.panel h3,.panel h4{{margin-top:0}}
pre{{white-space:pre-wrap;word-break:break-word;background:#f0eee8;padding:1rem;border:1px solid #d6d1c4;border-radius:6px}}
code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
{badge_css}
</style></head><body>
{summary_body}
</body></html>"""
    path.write_text(html, encoding="utf-8")
