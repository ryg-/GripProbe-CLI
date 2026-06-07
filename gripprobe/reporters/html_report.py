from __future__ import annotations

import difflib
import json
import os
import re
from collections.abc import Mapping
from html import escape
from pathlib import Path

from gripprobe.cli_agent_version import format_cli_agent_label, get_cli_agent_version
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
    "PASS_WITH_POLICY_VIOLATION": "policy",
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
    "policy",
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
    "policy": ".policy{background:#fff4bf;color:#705600}",
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
_TELEMETRY_PREVIEW_JSONL_LIMIT = 50


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


def _render_summary_layout_css(html_fragment: str) -> str:
    classes = _collect_css_classes(html_fragment)
    rules: list[str] = []
    if "grid" in classes:
        rules.append(".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}")
    if "panel" in classes:
        rules.append(".panel{background:#fbfaf7;border:1px solid #d6d1c4;border-radius:8px;padding:1rem;margin-bottom:1rem}")
        rules.append(".panel h3,.panel h4{margin-top:0}")
    if "<pre" in html_fragment:
        rules.append("pre{white-space:pre-wrap;word-break:break-word;background:#f0eee8;padding:1rem;border:1px solid #d6d1c4;border-radius:6px}")
    if "<code" in html_fragment:
        rules.append("code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}")
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
    sanitized = _sanitize_local_username(_sanitize_user_paths(text))
    sanitized = re.sub(r"https?://[^/\s\"'<>:]+:11434", "http://ollama-host:11434", sanitized)
    sanitized = re.sub(r"\bssh\s+[^/\s\"'<>:]+", "ssh ollama-host", sanitized)
    return sanitized


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


def _looks_like_tool_markdown(text: str) -> bool:
    lowered = text.lower()
    if "```tool" in lowered:
        return True
    markers = (
        "tool_call",
        "function_call",
        "<tool_call",
        "</tool_call>",
        '"tool_name"',
        "'tool_name'",
        "tool_name:",
    )
    return any(marker in lowered for marker in markers)


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
        role_raw = str(item.get("role", "unknown"))
        role_key = role_raw.strip().lower()
        content_raw = _sanitize_for_html(str(item.get("content", "")))
        content = escape(content_raw)
        classes = ["message"]
        if role_key == "user":
            classes.append("msg-user")
        elif role_key in ("assistant", "llm", "model"):
            classes.append("msg-llm")
        elif role_key == "tool":
            classes.append("msg-tool")
        if _looks_like_tool_markdown(content_raw):
            classes.append("msg-tool-md")
        role = escape(role_raw)
        rows.append(
            f"<section class='{' '.join(classes)}'>"
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


def _render_cli_agent_commands(result: CaseResult) -> str:
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
    if isinstance(metadata, dict):
        metadata = dict(metadata)
        if "shell_executable_path" in metadata:
            metadata["shell_executable_path"] = "[hidden in HTML]"
        if "cli_agent_executable_path" in metadata:
            metadata["cli_agent_executable_path"] = "[hidden in HTML]"
        payload["metadata"] = metadata
    payload = _sanitize_obj(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _case_metadata_from_json_text(case_json_raw: str) -> dict[str, object]:
    if not case_json_raw.strip():
        return {}
    try:
        payload = json.loads(case_json_raw)
    except json.JSONDecodeError:
        return {}
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    sanitized = _sanitize_obj(metadata)
    return sanitized if isinstance(sanitized, dict) else {}


def _render_run_comparison(case_json_raw: str, result: CaseResult) -> str:
    metadata = _case_metadata_from_json_text(case_json_raw)
    if not metadata:
        metadata = result.metadata
    run_consistency = metadata.get("run_consistency")
    run_1_status = metadata.get("run_1_status")
    run_2_status = metadata.get("run_2_status")
    run_1_profile = metadata.get("run_1_profile")
    run_2_profile = metadata.get("run_2_profile")
    if not any((run_consistency, run_1_status, run_2_status, run_1_profile, run_2_profile)):
        return ""
    blocks: list[str] = []
    if run_consistency:
        blocks.append(f"<p><strong>Consistency:</strong> {escape(_sanitize_for_html(str(run_consistency)))}</p>")
    for label, status, profile in (
        ("Run 1", run_1_status, run_1_profile),
        ("Run 2", run_2_status, run_2_profile),
    ):
        if not status and not isinstance(profile, dict):
            continue
        rows = []
        if status:
            rows.append(f"<li><strong>Status:</strong> {escape(_sanitize_for_html(str(status)))}</li>")
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
                    rows.append(
                        f"<li><strong>{escape(key)}:</strong> "
                        f"{escape(_sanitize_for_html(str(profile[key])))}</li>"
                    )
        blocks.append(f"<div class='panel'><h3>{escape(label)}</h3><ul>{''.join(rows)}</ul></div>")
    if not blocks:
        return ""
    return "<div class='grid'>" + "".join(blocks) + "</div>"


def _render_trajectory_hints(case_json_raw: str, result: CaseResult) -> str:
    metadata = _case_metadata_from_json_text(case_json_raw)
    if not metadata:
        metadata = result.metadata
    reasons = metadata.get("trajectory_reasons")
    reason_items = ""
    if isinstance(reasons, list):
        reason_items = "".join(f"<li>{escape(_sanitize_for_html(str(reason)))}</li>" for reason in reasons)
    legend = (
        "<ul>"
        "<li><strong>clean</strong>: no execution errors, no loop pattern, no contradictory DONE/FAIL text</li>"
        "<li><strong>recovered</strong>: result reached but trace shows errors, retries, or contradictory completion text</li>"
        "<li><strong>violated</strong>: result reached after breaking an explicit structured rule such as no_retry_on_error</li>"
        "</ul>"
    )
    current = f"<h3>Current Case</h3><ul>{reason_items}</ul>" if reason_items else ""
    return legend + current


def _render_failure_reason(case_json_raw: str, result: CaseResult) -> str:
    metadata = _case_metadata_from_json_text(case_json_raw)
    if not metadata:
        metadata = result.metadata
    failure_reason = metadata.get("failure_reason")
    if not failure_reason:
        return ""
    return f"<p><strong>Failure Reason:</strong> {escape(_sanitize_for_html(str(failure_reason)))}</p>"


def _json_for_script_tag(value: object) -> str:
    # Prevent accidental closing of script tag when embedding JSON payloads.
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _render_telemetry_viewer_script() -> str:
    return """<script>
function gripprobeOpenTelemetryViewer(payloadId, rawHref){
function tryParseJsonString(value){
if(typeof value!=='string'){return value;}
var trimmed=value.trim();
if(!trimmed){return value;}
var start=trimmed.charAt(0);
var end=trimmed.charAt(trimmed.length-1);
if(!((start==='{'&&end==='}')||(start==='['&&end===']'))){return value;}
try{return JSON.parse(trimmed);}catch(_jsonErr){return value;}
}
function decodeEscapedExcerpt(value){
if(typeof value!=='string'){return value;}
if(value.indexOf('\\\\\"')===-1&&value.indexOf('\\\\n')===-1&&value.indexOf('\\\\t')===-1&&value.indexOf('\\\\r')===-1){return value;}
var text=value;
text=text.replace(/\\\\r\\\\n/g,'\\n');
text=text.replace(/\\\\n/g,'\\n');
text=text.replace(/\\\\t/g,'\\t');
text=text.replace(/\\\\r/g,'\\r');
text=text.replace(/\\\\\\\"/g,'"');
text=text.replace(/\\\\\\\\/g,'\\\\');
return text;
}
function tryParseSseStream(value){
if(typeof value!=='string'){return value;}
if(value.indexOf('data:')===-1){return value;}
var normalized=value.replace(/\\r\\n/g,'\\n');
var blocks=normalized.split(/\\n\\n+/);
var chunks=[];
for(var bi=0;bi<blocks.length;bi++){
var block=blocks[bi];
if(!block||!block.trim()){continue;}
var lines=block.split(/\\n/);
var payloadLines=[];
for(var li=0;li<lines.length;li++){
var line=lines[li];
if(line.indexOf('data:')===0){payloadLines.push(line.slice(5).trim());}
}
if(payloadLines.length===0){continue;}
var payloadText=payloadLines.join('\\n');
if(payloadText==='[DONE]'){chunks.push({event:'done'});continue;}
try{chunks.push(JSON.parse(payloadText));}
catch(_sseErr){chunks.push({event:'raw',data:payloadText});}
}
if(chunks.length===0){return value;}
return {x_gripprobe_view:'sse_chunks',chunks:chunks};
}
function normalizeBodyExcerpt(value){
var parsed=tryParseJsonString(value);
if(parsed!==value){return normalizeForView(parsed);}
var sseParsed=tryParseSseStream(value);
if(sseParsed!==value){return normalizeForView(sseParsed);}
var decoded=decodeEscapedExcerpt(value);
if(decoded!==value){
parsed=tryParseJsonString(decoded);
if(parsed!==decoded){return normalizeForView(parsed);}
sseParsed=tryParseSseStream(decoded);
if(sseParsed!==decoded){return normalizeForView(sseParsed);}
}
return decoded;
}
function normalizeForView(node){
if(Array.isArray(node)){return node.map(normalizeForView);}
if(node&&typeof node==='object'){
var out={};
for(var k in node){
if(!Object.prototype.hasOwnProperty.call(node,k)){continue;}
var v=node[k];
if((k==='x_gripprobe_body_excerpt'||k==='body_excerpt')&&typeof v==='string'){
out[k]=normalizeBodyExcerpt(v);
}else{
out[k]=normalizeForView(v);
}
}
return out;
}
return node;
}
function looksLikeToolMarkdown(text){
if(typeof text!=='string'){return false;}
var lowered=text.toLowerCase();
if(lowered.indexOf('```tool')!==-1){return true;}
var markers=['tool_call','function_call','<tool_call','</tool_call>','\"tool_name\"',\"'tool_name'\",'tool_name:'];
for(var i=0;i<markers.length;i++){
if(lowered.indexOf(markers[i])!==-1){return true;}
}
return false;
}
function hasToolSignals(entry){
if(!entry||typeof entry!=='object'){return false;}
if(typeof entry.event_type==='string'&&entry.event_type.toLowerCase().indexOf('tool')!==-1){return true;}
if(typeof entry.source_tier==='string'&&entry.source_tier.toLowerCase().indexOf('tool')!==-1){return true;}
if(typeof entry.role==='string'&&entry.role.toLowerCase()==='tool'){return true;}
if(entry.payload&&typeof entry.payload==='object'&&entry.payload.tool_name){return true;}
if(entry.tool_name){return true;}
if(entry.tool_call||entry.tool_calls||entry.function_call||entry.function_calls){return true;}
if(typeof entry.x_gripprobe_tool_call_count==='number'&&entry.x_gripprobe_tool_call_count>0){return true;}
if(typeof entry.x_gripprobe_tool_call_nonstructured_count==='number'&&entry.x_gripprobe_tool_call_nonstructured_count>0){return true;}
if(typeof entry.x_gripprobe_tool_result_count==='number'&&entry.x_gripprobe_tool_result_count>0){return true;}
return false;
}
function classifyViewerEntry(entry){
var classes=['tv-row'];
var roleClass='';
if(entry&&typeof entry==='object'){
var tier='';
if(typeof entry.source_tier==='string'){tier=entry.source_tier.toLowerCase();}
else if(typeof entry.role==='string'){tier=entry.role.toLowerCase();}
if(tier==='user'){roleClass='tv-user';}
if(tier==='assistant'||tier==='llm'||tier==='model'){roleClass='tv-llm';}
if(tier==='tool'){roleClass='tv-tool';}
if(hasToolSignals(entry)&&roleClass!=='tv-user'){roleClass='tv-tool';}
var textSignals='';
if(typeof entry.x_gripprobe_body_excerpt==='string'){textSignals+=entry.x_gripprobe_body_excerpt+'\\n';}
if(typeof entry.body_excerpt==='string'){textSignals+=entry.body_excerpt+'\\n';}
if(typeof entry.content==='string'){textSignals+=entry.content+'\\n';}
if(entry.payload&&typeof entry.payload.content==='string'){textSignals+=entry.payload.content+'\\n';}
if(looksLikeToolMarkdown(textSignals)){classes.push('tv-tool-md');}
}
if(roleClass){classes.push(roleClass);}
return classes.join(' ');
}
function extractToolCallIds(entry){
if(!entry||typeof entry!=='object'){return {ids:[],source:''};}
if(Array.isArray(entry.x_gripprobe_tool_call_ids)&&entry.x_gripprobe_tool_call_ids.length>0){
return {ids:entry.x_gripprobe_tool_call_ids,source:'x_gripprobe_tool_call_ids'};
}
if(entry.payload&&typeof entry.payload==='object'){
if(Array.isArray(entry.payload.tool_call_ids)&&entry.payload.tool_call_ids.length>0){
return {ids:entry.payload.tool_call_ids,source:'payload.tool_call_ids'};
}
if(Array.isArray(entry.payload.x_gripprobe_tool_call_ids)&&entry.payload.x_gripprobe_tool_call_ids.length>0){
return {ids:entry.payload.x_gripprobe_tool_call_ids,source:'payload.x_gripprobe_tool_call_ids'};
}
}
if(entry.x_gripprobe_response&&typeof entry.x_gripprobe_response==='object'){
if(Array.isArray(entry.x_gripprobe_response.x_gripprobe_tool_call_ids)&&entry.x_gripprobe_response.x_gripprobe_tool_call_ids.length>0){
return {ids:entry.x_gripprobe_response.x_gripprobe_tool_call_ids,source:'x_gripprobe_response.x_gripprobe_tool_call_ids'};
}
if(Array.isArray(entry.x_gripprobe_response.tool_call_ids)&&entry.x_gripprobe_response.tool_call_ids.length>0){
return {ids:entry.x_gripprobe_response.tool_call_ids,source:'x_gripprobe_response.tool_call_ids'};
}
}
return {ids:[],source:''};
}
function summarizeRow(entry,index){
var parts=['Line '+(index+1)];
if(entry&&typeof entry==='object'){
var tier=entry.source_tier||entry.role;
if(tier){parts.push('source=' + String(tier));}
if(entry.event_type){parts.push('event=' + String(entry.event_type));}
if(entry.x_gripprobe_method||entry.x_gripprobe_path){
parts.push(String(entry.x_gripprobe_method||'') + ' ' + String(entry.x_gripprobe_path||''));
}
if(entry.payload&&typeof entry.payload==='object'&&entry.payload.tool_name){
parts.push('tool=' + String(entry.payload.tool_name));
}else if(entry.tool_name){
parts.push('tool=' + String(entry.tool_name));
}
var toolCallIds=extractToolCallIds(entry);
if(toolCallIds.ids.length>0){
parts.push('tool_call_ids=' + toolCallIds.ids.join(','));
parts.push('ids_source=' + toolCallIds.source);
}
}
return parts.join(' | ');
}
function compactEntryForRow(entry){
if(!entry||typeof entry!=='object'){return entry;}
var out={};
for(var key in entry){
if(!Object.prototype.hasOwnProperty.call(entry,key)){continue;}
var value=entry[key];
if((key==='x_gripprobe_body_excerpt'||key==='body_excerpt')&&typeof value==='string'){
if(value.length>600){
out[key]=value.slice(0,600)+'\\n... [truncated in compact view]';
}else{
out[key]=value;
}
continue;
}
if((key==='x_gripprobe_body_excerpt'||key==='body_excerpt')&&(value&&typeof value==='object')){
var previewLen=0;
try{previewLen=JSON.stringify(value).length;}catch(_previewErr){previewLen=1000;}
if(previewLen>600){
out[key]='[structured excerpt hidden in compact view]';
}else{
out[key]=value;
}
continue;
}
out[key]=value;
}
return out;
}
function formatViewerValue(value,indent,key){
var space=' '.repeat(indent);
var next=' '.repeat(indent+2);
if((key==='x_gripprobe_body_excerpt'||key==='body_excerpt')&&typeof value==='string'){
var lines=value.split(/\\r?\\n/);
return '|\\n'+lines.map(function(line){return next+line;}).join('\\n');
}
if(Array.isArray(value)){
if(value.length===0){return '[]';}
return '[\\n'+value.map(function(item){return next+formatViewerValue(item,indent+2,null);}).join(',\\n')+'\\n'+space+']';
}
if(value&&typeof value==='object'){
var keys=Object.keys(value);
if(keys.length===0){return '{}';}
return '{\\n'+keys.map(function(childKey){return next+JSON.stringify(childKey)+': '+formatViewerValue(value[childKey],indent+2,childKey);}).join(',\\n')+'\\n'+space+'}';
}
return JSON.stringify(value);
}
var payloadNode=document.getElementById(payloadId);
if(!payloadNode){return true;}
var popup=window.open('about:blank', '_blank');
if(!popup){return true;}
var payload=null;
try{payload=JSON.parse(payloadNode.textContent||'null');}catch(_err){payload=null;}
var doc=popup.document;
doc.open();
doc.write("<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Telemetry Viewer</title><style>body{font-family:system-ui,sans-serif;margin:1.25rem;background:#f7f7f3;color:#111;line-height:1.45}pre{white-space:pre-wrap;overflow:auto;background:#f0eee8;padding:1rem;border:1px solid #d6d1c4;border-radius:6px}a{color:#0b57d0}.muted{color:#666}.viewer-rows{display:none;margin-top:1rem}.tv-row{margin:.75rem 0;border:1px solid #d6d1c4;border-radius:8px;overflow:hidden}.tv-row-meta{font-size:.85rem;padding:.4rem .6rem;background:#ece8dc;color:#555;border-bottom:1px solid #d6d1c4}.tv-row pre{margin:0;border:none;border-radius:0;background:transparent}.tv-user{background:#eaf3ff}.tv-llm{background:#ecfdf3}.tv-tool{background:#fff7e8}.tv-tool-md{box-shadow:inset 0 0 0 2px #f2c14e}.hljs{background:#f0eee8 !important}.hljs-ln td{vertical-align:top}.hljs-ln-numbers{user-select:none;text-align:right;color:#7a7468;border-right:1px solid #d6d1c4;padding-right:.75rem;white-space:nowrap;width:1%}.hljs-ln-code{padding-left:.75rem;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere}</style><link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css'></head><body><h1>Telemetry Artifact Viewer</h1><p id='viewer-hint' class='muted'></p><div id='viewer-rows' class='viewer-rows'></div><pre id='viewer-pre'><code id='viewer-code'></code></pre><p><a id='viewer-raw-link' target='_blank' rel='noopener noreferrer'></a></p></body></html>");
doc.close();
var hint=doc.getElementById('viewer-hint');
var codeEl=doc.getElementById('viewer-code');
var preEl=doc.getElementById('viewer-pre');
var rowsEl=doc.getElementById('viewer-rows');
var rawLink=doc.getElementById('viewer-raw-link');
rawLink.setAttribute('href',rawHref);
try{
var viewerUrl=new URL(rawHref,window.location.href);
viewerUrl.hash='telemetry-viewer';
if(popup.history&&popup.history.replaceState){
popup.history.replaceState(null,'',viewerUrl.toString());
}
}catch(_urlErr){}
if(!payload||typeof payload!=='object'){
hint.textContent='Interactive preview is unavailable; open the raw artifact using the link below.';
rawLink.textContent='Open raw artifact';
return false;
}
var relpath=String(payload.relpath||'artifact');
rawLink.textContent='Open raw artifact: '+relpath;
hint.textContent='Interactive rendering for '+relpath+' · viewer v5';
var text=String(payload.content||'');
var kind=String(payload.kind||'text');
var renderedText='';
var language='plaintext';
var renderedRows=false;
function renderJsonlRows(entries){
if(!rowsEl||!preEl){return false;}
rowsEl.innerHTML='';
for(var i=0;i<entries.length;i++){
var rowEntry=entries[i];
var row=doc.createElement('div');
row.className=classifyViewerEntry(rowEntry);
var meta=doc.createElement('div');
meta.className='tv-row-meta';
meta.textContent=summarizeRow(rowEntry,i);
var pre=doc.createElement('pre');
var code=doc.createElement('code');
code.className='language-json tv-row-code';
code.textContent=formatViewerValue(compactEntryForRow(rowEntry),0,null);
pre.appendChild(code);
row.appendChild(meta);
row.appendChild(pre);
rowsEl.appendChild(row);
}
rowsEl.style.display='block';
preEl.style.display='none';
return true;
}
try{
if(kind==='json'){
renderedText=formatViewerValue(normalizeForView(JSON.parse(text)),0,null);
language='json';
}else if(kind==='jsonl'){
var lines=text.split(/\\r?\\n/).filter(function(line){return line.trim().length>0;});
var entries=[];
for(var i=0;i<lines.length;i++){
try{entries.push(normalizeForView(JSON.parse(lines[i])));}
catch(_lineErr){entries.push({line:i+1,parse_error:'invalid_json',raw:lines[i]});}
}
renderedRows=renderJsonlRows(entries);
if(!renderedRows){renderedText=formatViewerValue(entries,0,null);}
language='json';
hint.textContent=hint.textContent+' ('+lines.length+' line(s))';
}else{
renderedText=text;
language='plaintext';
}
}catch(_parseErr){
hint.textContent='Interactive preview failed; showing sanitized raw text.';
renderedText=text;
language='plaintext';
}
if(!renderedRows){
codeEl.textContent=renderedText;
codeEl.className='language-'+language;
if(preEl){preEl.style.display='block';}
if(rowsEl){rowsEl.style.display='none';}
}
function applyHighlight(){
try{
if(popup.hljs&&popup.hljs.highlightElement){
if(!renderedRows&&codeEl){popup.hljs.highlightElement(codeEl);}
var rowCodes=doc.querySelectorAll('.tv-row-code');
for(var i=0;i<rowCodes.length;i++){popup.hljs.highlightElement(rowCodes[i]);}
}
if(popup.hljs&&popup.hljs.lineNumbersBlock){
if(!renderedRows&&codeEl){popup.hljs.lineNumbersBlock(codeEl);}
}
}catch(_hlErr){}
}
var scriptHl=doc.createElement('script');
scriptHl.src='https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js';
scriptHl.onload=function(){
var scriptLn=doc.createElement('script');
scriptLn.src='https://cdnjs.cloudflare.com/ajax/libs/highlightjs-line-numbers.js/2.9.0/highlightjs-line-numbers.min.js';
scriptLn.onload=applyHighlight;
scriptLn.onerror=applyHighlight;
doc.head.appendChild(scriptLn);
};
scriptHl.onerror=function(){};
doc.head.appendChild(scriptHl);
return false;
}
</script>"""


def _render_json_preview(raw_text: str) -> str:
    if not raw_text.strip():
        return ""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text
    sanitized_payload = _sanitize_obj(payload)
    return json.dumps(sanitized_payload, indent=2, ensure_ascii=False)


def _compact_dict(data: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in data.items() if value is not None and value != ""}


def _summarize_jsonl_entry(payload: object, line_no: int) -> object:
    if not isinstance(payload, dict):
        return {"line": line_no, "value": _sanitize_obj(payload)}

    # Wrapper/telemetry events summary.
    if any(key in payload for key in ("event_type", "source_tier", "phase", "status")):
        event_payload = payload.get("payload")
        tool_name = None
        if isinstance(event_payload, dict):
            tool_name = event_payload.get("tool_name")
        return _compact_dict(
            {
                "line": line_no,
                "timestamp": payload.get("timestamp"),
                "phase": payload.get("phase"),
                "event_type": payload.get("event_type"),
                "source_tier": payload.get("source_tier"),
                "status": payload.get("status"),
                "tool_name": tool_name,
                "raw_artifact_ref": payload.get("raw_artifact_ref"),
            }
        )

    # Proxy capture summary.
    if any(
        key in payload
        for key in (
            "x_gripprobe_method",
            "x_gripprobe_path",
            "x_gripprobe_duration_ms",
            "x_gripprobe_tool_call_count",
            "x_gripprobe_tool_call_nonstructured_count",
            "x_gripprobe_tool_result_count",
        )
    ):
        response_status = payload.get("x_gripprobe_response_status")
        if response_status is None:
            response = payload.get("x_gripprobe_response")
            if isinstance(response, dict):
                response_status = response.get("x_gripprobe_status")
        return _compact_dict(
            {
                "line": line_no,
                "timestamp": payload.get("x_gripprobe_timestamp"),
                "method": payload.get("x_gripprobe_method"),
                "path": payload.get("x_gripprobe_path"),
                "duration_ms": payload.get("x_gripprobe_duration_ms"),
                "response_status": response_status,
                "tool_call_count": payload.get("x_gripprobe_tool_call_count"),
                "tool_call_nonstructured_count": payload.get("x_gripprobe_tool_call_nonstructured_count"),
                "tool_result_count": payload.get("x_gripprobe_tool_result_count"),
                "proxy_error": payload.get("x_gripprobe_proxy_error"),
            }
        )

    return _compact_dict(
        {
            "line": line_no,
            "keys": sorted(str(key) for key in payload.keys()),
        }
    )


def _render_jsonl_preview(raw_text: str, limit: int = _TELEMETRY_PREVIEW_JSONL_LIMIT) -> tuple[str, int, bool]:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    preview_entries: list[object] = []
    for line_no, line in enumerate(lines[:limit], start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            preview_entries.append(
                {
                    "line": line_no,
                    "parse_error": "invalid_json",
                    "raw": _sanitize_for_html(line),
                }
            )
            continue
        preview_entries.append(_sanitize_obj(_summarize_jsonl_entry(payload, line_no)))
    return json.dumps(preview_entries, indent=2, ensure_ascii=False), len(lines), len(lines) > limit


def _render_telemetry(
    case_dir: Path,
    detail_path: Path,
    case_json_raw: str,
    result: CaseResult,
    *,
    show_artifact_links: bool = True,
) -> str:
    metadata = _case_metadata_from_json_text(case_json_raw)
    if not metadata:
        metadata = result.metadata
    rows: list[str] = []
    fields = (
        ("Capture Status", "event_capture_status"),
        ("Proxy Mode", "telemetry_proxy_mode"),
        ("Proxy Status", "telemetry_proxy_status"),
        ("Proxy Skip Reason", "telemetry_proxy_skip_reason"),
        ("Capture Skip Reason", "telemetry_capture_skip_reason"),
        ("Source Tier", "telemetry_source_tier"),
        ("Event Count", "telemetry_event_count"),
        ("Warmup Events", "telemetry_warmup_event_count"),
        ("Measured Events", "telemetry_measured_event_count"),
        ("Tool Call Count", "telemetry_tool_call_count"),
        ("Warmup Tool Calls", "telemetry_warmup_tool_call_count"),
        ("Measured Tool Calls", "telemetry_measured_tool_call_count"),
        ("Proxy Non-Structured Tool Calls", "telemetry_proxy_tool_call_nonstructured_count"),
        ("Tool Result Count", "telemetry_tool_result_count"),
        ("Warmup Tool Results", "telemetry_warmup_tool_result_count"),
        ("Measured Tool Results", "telemetry_measured_tool_result_count"),
        ("Invoked Confidence", "telemetry_invoked_confidence"),
        ("Retry Loop Detected", "telemetry_retry_loop_detected"),
        ("Tool Event Verdict", "tool_event_verdict"),
        ("Tool Event Verdict Reason", "tool_event_verdict_reason"),
    )
    for label, key in fields:
        if key not in metadata:
            continue
        value = metadata.get(key)
        if value is None or value == "":
            continue
        rows.append(
            f"<li><strong>{escape(label)}:</strong> {escape(_sanitize_for_html(str(value)))}</li>"
        )
    summary_raw = _read_text(case_dir / "artifacts" / "events.summary.json")
    summary_pretty = _render_json_preview(summary_raw)
    summary_block = f"<h3>events.summary.json</h3>{_pre_block(summary_pretty)}" if summary_pretty.strip() else ""
    telemetry_artifact_items: list[str] = []
    telemetry_preview_blocks: list[str] = []
    viewer_payload_scripts: list[str] = []
    viewer_enabled = False
    if show_artifact_links:
        telemetry_files = (
            ("artifacts/events.warmup.jsonl", "jsonl"),
            ("artifacts/events.measured.jsonl", "jsonl"),
            ("artifacts/proxy.warmup.http.jsonl", "jsonl"),
            ("artifacts/proxy.measured.http.jsonl", "jsonl"),
            ("artifacts/events.summary.json", "json"),
        )
        for idx, (relpath, kind) in enumerate(telemetry_files):
            artifact = case_dir / relpath
            if not artifact.exists() or not artifact.is_file():
                continue
            href = escape(os.path.relpath(artifact, detail_path.parent))
            payload_id = f"telemetry-viewer-data-{idx}"
            content = _read_text(artifact)
            viewer_payload_scripts.append(
                "<script type='application/json' id='"
                + escape(payload_id)
                + "'>"
                + _json_for_script_tag(
                    {
                        "relpath": relpath,
                        "kind": kind,
                        "content": content,
                    }
                )
                + "</script>"
            )
            viewer_link = (
                f"<a href='{href}' target='_blank' rel='noopener noreferrer' "
                f"onclick=\"return gripprobeOpenTelemetryViewer('{escape(payload_id)}', this.href)\">"
                "Open Interactive Viewer</a>"
            )
            telemetry_artifact_items.append(
                f"<li><a href='{href}'>{escape(relpath)}</a> | {viewer_link}</li>"
            )
            viewer_enabled = True
            if kind != "jsonl":
                continue
            preview_json, line_count, is_truncated = _render_jsonl_preview(content)
            limit_info = (
                f"<p class='muted'>Showing first {_TELEMETRY_PREVIEW_JSONL_LIMIT} of {line_count} line(s).</p>"
                if is_truncated
                else f"<p class='muted'>{line_count} line(s).</p>"
            )
            telemetry_preview_blocks.append(
                f"<h4>{escape(relpath)}</h4>"
                + limit_info
                + _pre_block(preview_json)
            )
    telemetry_artifacts_block = (
        "<h3>Telemetry Artifacts</h3><ul>" + "".join(telemetry_artifact_items) + "</ul>"
        if telemetry_artifact_items
        else ""
    )
    telemetry_preview_section = (
        "<h3>Telemetry Preview</h3>"
        + summary_block
        + "".join(telemetry_preview_blocks)
        if show_artifact_links and (summary_block or telemetry_preview_blocks)
        else summary_block
    )
    viewer_script = (
        _render_telemetry_viewer_script() + "".join(viewer_payload_scripts)
        if show_artifact_links and viewer_enabled
        else ""
    )
    if not rows and not telemetry_preview_section and not telemetry_artifacts_block:
        return ""
    body = f"<ul>{''.join(rows)}</ul>" if rows else ""
    return body + telemetry_preview_section + telemetry_artifacts_block + viewer_script


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
    case_json_raw_for_metadata: str | None = None,
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
    metadata_source_json = case_json_raw_for_metadata if case_json_raw_for_metadata is not None else case_json_raw
    run_comparison_html = _render_run_comparison(metadata_source_json, result)
    trajectory_hints_html = _render_trajectory_hints(metadata_source_json, result)
    failure_reason_html = _render_failure_reason(metadata_source_json, result)
    telemetry_html = _render_telemetry(
        case_dir,
        detail_path,
        metadata_source_json,
        result,
        show_artifact_links=show_artifacts,
    )
    runtime_snapshots_html = _render_case_runtime_snapshots(metadata_source_json) if show_runtime_snapshots else ""
    cli_agent_commands_html = _render_cli_agent_commands(result)
    transcript_html = _render_transcript(case_dir)
    artifact_links = _render_artifact_links(case_dir, detail_path) if show_artifacts else ""
    modelfile_raw = _read_text(case_dir / "model.modelfile")
    summary_rel = escape(os.path.relpath(reports_dir / "summary.html", detail_path.parent))
    trajectory_class = TRAJECTORY_CLASS.get(result.trajectory, "unknown")
    invoked_class = INVOKED_CLASS.get(result.invoked, "unknown")
    match_class = _match_class(result.match_percent)
    cli_agent_version = _sanitize_for_html(get_cli_agent_version(result.metadata))
    cli_agent_label = _sanitize_for_html(format_cli_agent_label(result.cli_agent, result.metadata))

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
<p><strong>CLI Agent:</strong> <code>{escape(cli_agent_label)}</code> | <strong>CLI Agent Version:</strong> <code>{escape(cli_agent_version)}</code></p>
<p>{_status_badges(result)} <strong>Trajectory:</strong> <span class='badge {trajectory_class}'>{escape(result.trajectory)}</span> | <strong>Invoked:</strong> <span class='badge {invoked_class}'>{escape(result.invoked)}</span> | <strong>Match:</strong> <span class='badge {match_class}'>{result.match_percent}%</span></p>
{failure_reason_html}
{("<p class='ok'>The expected workspace artifact was present before the harness timeout elapsed.</p>") if _timeout_artifact_reached(result) else ''}
{('<section><h2>Telemetry</h2>' + telemetry_html + '</section>') if telemetry_html else ''}
{('<section><h2>CLI Agent Commands</h2>' + cli_agent_commands_html + '</section>') if cli_agent_commands_html else ''}
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
.message.msg-user{{background:#eaf3ff;border-left:4px solid #4a8cff;padding-left:.75rem}}
.message.msg-llm{{background:#ecfdf3;border-left:4px solid #3aa76d;padding-left:.75rem}}
.message.msg-tool{{background:#fff7e8;border-left:4px solid #d79a2b;padding-left:.75rem}}
.message.msg-tool-md{{box-shadow:inset 0 0 0 2px #f2c14e}}
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
    cases_dir: Path | None = None,
    detail_filenames: dict[str, str] | None = None,
    case_json_by_case_id: Mapping[str, str] | None = None,
    case_dirs_by_case_id: Mapping[str, Path] | None = None,
    show_artifacts: bool = True,
    show_runtime_snapshots: bool = True,
    show_case_json: bool = True,
) -> dict[str, str]:
    detail_links: dict[str, str] = {}
    for item in results:
        source_case_dir = (case_dirs_by_case_id or {}).get(item.case_id)
        if source_case_dir is None:
            if cases_dir is None:
                raise ValueError(f"Missing source case directory for case_id={item.case_id}")
            source_case_dir = cases_dir / item.case_id
        detail_links[item.case_id] = _write_case_detail(
            item,
            reports_dir,
            source_case_dir,
            detail_filename=(detail_filenames or {}).get(item.case_id),
            case_json_raw_for_metadata=(case_json_by_case_id or {}).get(item.case_id),
            show_artifacts=show_artifacts,
            show_runtime_snapshots=show_runtime_snapshots,
            show_case_json=show_case_json,
        )
    return detail_links


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
        cli_agent_label = _sanitize_for_html(format_cli_agent_label(item.cli_agent, item.metadata))
        rows.append(
            "<tr>"
            f"<td>{escape(cli_agent_label)}</td>"
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
<thead><tr><th>CLI Agent</th><th>Model</th><th>Backend</th><th>Hash</th><th>Format</th><th>Test</th><th>Status</th><th>Reason</th><th>Trajectory</th><th>Invoked</th><th>Match</th><th>Warmup (s)</th><th>Measured (s)</th><th>Details</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>"""
    badge_css = _render_conditional_css(summary_body)
    layout_css = _render_summary_layout_css(summary_body)
    html = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><title>GripProbe Summary</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#f7f7f3;color:#111}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.5rem;text-align:left;vertical-align:top}}
th{{background:#ece8dc}}
a{{color:#0b57d0}}
{layout_css}
{badge_css}
</style>
<script data-goatcounter="https://ryg-.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</head><body>
{summary_body}
</body></html>"""
    path.write_text(html, encoding="utf-8")
