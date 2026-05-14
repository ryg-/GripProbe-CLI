# Feature Request Spec: Event-Based Tool Evaluation via Proxy + Wrapper Telemetry

Use this feature request before implementing proxy/wrapper telemetry for real tool-call observation.
Scope: local workflow only (no PR requirements).

## 1. Change Summary

- Feature name: `tool_telemetry_proxy_wrapper`

## 2. Problem and Goal

- Problem:
    - `invoked` and `trajectory` are currently heuristic and adapter-specific; structured tool evidence is inconsistent across shells.
- Goal:
    - capture normalized `tool_call_start/tool_call_result/model_response` events from real runs and use them as evidence for a new event-based case evaluator.

- Non-goals:
    - do not change validator semantics
    - old `trajectory/invoked/match` compatibility is not required; all reports will be regenerated under the new result contract.


## 3. Scope

- In scope:
    - wrapper telemetry extraction from case artifacts (`stdout/stderr/transcript/json`).
    - optional per-case proxy capture; wrapper capture is mandatory
    - replacing canonical trace-based failure reason.
    - normalized event schema.
    - new `event_evaluator` that derives verdict fields from validators, process result, and telemetry/proxy events.
    - replacing canonical trace-based `failure_reason` and `trajectory` with event-based evaluation.

- Affected components:
    - `runner` (orchestration, proxy lifecycle, telemetry persistence)
    - `adapters` (base URL/env wiring where needed)
    - `event_evaluator` (new canonical verdict layer)
    - `reporters` (case/aggregate telemetry display)
    - `rebuild` (recompute from new artifacts; legacy fallback only if explicitly implemented)
    - `specs`/CLI flags (feature toggles)
    - `docs`

## 4. Definitions and Trigger Rules

- Telemetry source tiers:
    - `A`: structured protocol/proxy events.
    - `B`: structured agent output events.
    - `C`: wrapper parsing from unstructured stdout/stderr markers.
    - `D`: prompt-level self-report (fallback only, optional, for future).
- Feature flags (required):
    - `telemetry_proxy_mode: off|auto|force`
        - wrapper event extraction is always enabled.
- Trigger condition (fill exactly):
    - `always extract wrapper events after warmup/measured phases`
    - `if telemetry_proxy_mode != off and backend/protocol supports routing then run per-case proxy capture`
- Skip reasons taxonomy:
    - Skip reasons describe capture/proxy lifecycle only.
    - Verdict reasons describe evaluator evidence classification and may differ from skip reasons.
    - `disabled`, `unsupported_shell`, `unsupported_backend`, `capture_missing`, `wrapper_parse_error`, `budget_exceeded`
    - `proxy_bind_error`, `proxy_connect_error` if proxy mode is `auto|force`
- Notes about tier 'D'
    - Source tier `D` must never produce `confirmed_tool_use` for full `PASS`.
    - Tier `D` may only explain/debug inconclusive cases; validators pass + tier D only evidence maxes at `PASS_WITH_POLICY_VIOLATION`.


## 5. Current Behavior (As-Is)

- Today each case has 2 phases: `warmup` then `measured`.
- Existing invocation semantics are mostly heuristic:
    - gptme markers via `trace_analysis`.
    - shell-specific marker checks in adapters.


## 6. Proposed Behavior (To-Be)

- Existing fields/outputs that will be redefined:
    - `status`: derived by `event_evaluator` from validator result, process result, and telemetry events.
    - `trajectory`: derived from event timeline (`clean|recovered|violated` based on failed tool results, retries, timeout, and recovery).
    - `invoked`: derived from event evidence, not from shell-specific text heuristics.
    - `match_percent`: removed from the new result contract; reports use `artifact_match` and `overall_score`.
    - `failure_reason`: derived from event taxonomy, for example `no_tool_call_observed`, `tool_call_without_result`, `tool_result_error`, `tool_retry_loop`, `artifact_mismatch_after_success`, `protocol_malformed`, `backend_tool_unsupported`.
- New status taxonomy:
    - `PASS`: validators pass and tool evidence is confirmed
    - `PASS_WITH_POLICY_VIOLATION`: validators pass, but required tool evidence is missing, inconclusive, or not observable.
    - `FAIL`: validators fail after observed execution.
    - `NO_TOOL_CALL`: validators fail and observable telemetry shows no tool event.
    - `TIMEOUT`: measured process timed out.
    - `TOOL_UNSUPPORTED`: shell/backend cannot execute the required tool capability.
    - `HARNESS_ERROR`: GripProbe infrastructure failed.
    - `SHELL_ERROR`: CLI agent process failed before a reliable measured result could be evaluated.

    - Aggregate scoring:
        - `PASS` counts as pass.
        - `PASS_WITH_POLICY_VIOLATION` is not a full pass and contributes `0.8` to `overall_score`, but `0.0` to `strict_pass_score`.
        - Reports may show it as a separate warning/soft-pass category, but it must not increase `strict_pass_score`.
- User-visible behavior:
    - case page - both public(aggregate) and internal - includes telemetry section (source tier, event counts, key timeline) and optional proxy section.
- Internal behavior:
    - wrapper telemetry extractor runs after each case and persists normalized events.
    - proxy captures protocol traffic per case and contributes higher-confidence events.
    - `event_evaluator` reads validator output, process output, and normalized events, then writes the canonical verdict fields.
- Prompt/mode policy:
    - optional diagnostic mode must be documented separately
    - proxy must be documented, default is auto.
- New/changed CLI flags (if any):
    - `--telemetry-proxy off|auto|force`
- Backward compatibility notes:
    - no
    - old case/result schema is not preserved.
    - old reports must be regenerated or treated as legacy.


## 7. Data and Contracts

- Normalized event contract (minimum):
    - `event_type`: `tool_call_start | tool_call_result | model_response`
    - `run_id`, `case_id`, `phase`, `event_id`, `trace_id`
    - `tool_call_id`, `response_id` (where applicable)
    - `source_tier`: `A|B|C|D`
    - `payload` (redacted fields only)
    - `timestamp`, `sequence`
    - `source: wrapper|proxy|agent_output`
    - `status: started|success|error|timeout|unknown`
    - `latency_ms`, `exit_code`, `error_type` where applicable
    - `raw_artifact_ref`
    - `redaction_status: raw_internal|redacted|summary_only`

- Storage/artifact paths:
    - `cases/<id>/artifacts/events.warmup.jsonl`
    - `cases/<id>/artifacts/events.measured.jsonl`
    - `cases/<id>/artifacts/events.summary.json`
    - `cases/<id>/artifacts/proxy.http.jsonl` (if proxy enabled)
- New metadata fields (proposed):
    - `event_capture_status: collected|partial|missing|wrapper_parse_error`
    -  wrapper event extraction is mandatory and is never `skipped`; unsupported parser capability must produce `tool_event_not_observable`, not skipped capture.
    - `telemetry_proxy_status: collected|skipped|error`
    - `telemetry_capture_skip_reason: str | null`
    - `telemetry_proxy_skip_reason: str | null`
    - `telemetry_source_tier: A|B|C|D|none`
    - `telemetry_event_count: int`
    - `telemetry_tool_call_count: int`
    - `telemetry_tool_result_count: int`
    - `telemetry_invoked_confidence: float`
    - `telemetry_retry_loop_detected: bool`
    - `tool_event_verdict: confirmed_tool_use|no_tool_event_observed|tool_event_not_observable|tool_event_inconclusive`
    - `tool_event_not_observable`: shell/backend may execute tools, but GripProbe cannot observe structured tool evidence.
    - `tool_event_verdict_reason: none|parser_not_capable_for_shell|capture_missing|proxy_error|structured_event_absent|wrapper_parse_error|source_parse_inconclusive`
    - `capture_missing`: telemetry artifacts were not produced or are unreadable.
    - `artifact_missing`: expected case output artifact for validator/evaluator is missing.
    - `capture_missing` means evaluator cannot trust telemetry; if required wrapper artifacts are missing, status is `HARNESS_ERROR`.
    - `strict_pass_score: float` where only `PASS` contributes `1.0`.
    - `overall_score: float` where `PASS_WITH_POLICY_VIOLATION` contributes `0.8`.
    - Aggregate headline must use `strict_pass_score`; `overall_score` is secondary.
    - `nonzero_exit` is treated as `SHELL_ERROR` even when validators pass, because the CLI agent process did not complete cleanly.

Statuses matrix:
| validators | process | tool_event_verdict | reason | status |
|---|---|---|---|---|
| any | timeout | any | any | TIMEOUT |
| any | shell_error | any | process_error | SHELL_ERROR |
| any | harness_capture_failed | any | capture_missing | HARNESS_ERROR |
| pass | nonzero_exit | confirmed_tool_use | validators_pass_after_nonzero | SHELL_ERROR |
| pass | ok | confirmed_tool_use | any | PASS |
| pass | ok | no_tool_event_observed | structured_event_absent | PASS_WITH_POLICY_VIOLATION |
| pass | ok | tool_event_not_observable | parser_not_capable_for_shell | PASS_WITH_POLICY_VIOLATION |
| pass | ok | tool_event_inconclusive | proxy_error | PASS_WITH_POLICY_VIOLATION |
| pass | ok | tool_event_inconclusive | source_parse_inconclusive | PASS_WITH_POLICY_VIOLATION |
| fail | ok | confirmed_tool_use | any | FAIL |
| fail | ok | no_tool_event_observed | structured_event_absent | NO_TOOL_CALL |
| fail | ok | tool_event_not_observable | parser_not_capable_for_shell | FAIL |
| fail | ok | tool_event_inconclusive | source_parse_inconclusive/proxy_error | FAIL |
| fail | ok | tool_event_inconclusive | wrapper_parse_error/capture_missing | HARNESS_ERROR |

- Deterministic fallbacks for missing/not collected data:
    - `verdict_source: event_evaluator`
    - `artifact_match: float`
    - `tool_invocation_match: float` where `1.0` means required tool evidence confirmed, `0.0` means missing/not observable/inconclusive.
    - `protocol_match: float | null`
    - `strict_pass_score: float`
    - `overall_score: float`
    - `evaluator_reason_code: str`
        - `artifact_missing`: expected validator/evaluator artifact is missing; this is not a tool-event verdict reason.
    - `evaluator_reason_text: str`
- Deterministic behavior for missing data:
    - `proxy_error`: optional evidence source failed; never overrides confirmed lower-tier evidence.
    - `wrapper_parse_error`: mandatory wrapper extraction failed; status is `HARNESS_ERROR`.
    - `source_parse_inconclusive`: artifact was readable, but shell output is not structured enough; max status is `PASS_WITH_POLICY_VIOLATION` when validators pass.
    - `validators_pass + no_tool_event_observed` produces `PASS_WITH_POLICY_VIOLATION`.
    - `validators_fail + no_tool_event_observed` produces `NO_TOOL_CALL`.
    - Optional proxy errors do not override confirmed wrapper/agent-output tool evidence.
    - `proxy_error` only causes `tool_event_inconclusive` when no lower-tier source can confirm required tool use.
    - Required wrapper artifact parse failure is `HARNESS_ERROR` if artifacts are missing/corrupt, not agent policy violation.
    - Process precedence: `timeout` > `shell_error` > `harness_capture_failed` > `nonzero_exit` > validator/tool verdict.
    - `nonzero_exit` with readable artifacts and passing validators is `SHELL_ERROR`, not `PASS_WITH_POLICY_VIOLATION`.
- Missing measured events must be classified by observability:
- `capture_missing`: required artifacts are absent or unreadable.
- `no_tool_event_observed`: telemetry was captured with sufficient observability, but no tool event was found.
- `parser_not_capable_for_shell`: shell/output mode cannot provide reliable structured tool evidence. Evaluator may use validators/process result for artifact correctness, but final status cannot be `PASS`; if validators pass, maximum status is `PASS_WITH_POLICY_VIOLATION`.
- `validators_pass + tool_event_not_observable(reason=parser_not_capable_for_shell)` produces `PASS_WITH_POLICY_VIOLATION`.

Evaluator must not treat `parser_not_capable_for_shell` the same as `no_tool_event_observed`.


## 8. Design Options and Tradeoffs

### Option A: Wrapper parsing only
- Description:
    - derive telemetry solely from existing case artifacts.
- Pros:
    - minimal risk to comparability and runtime.
- Cons:
    - limited confidence for shells with unstructured logs, low value for debug.

### Option B: Protocol proxy only
- Description:
    - capture tool-related evidence only from backend protocol traffic.
- Pros:
    - high-confidence event capture where protocol is structured.
- Cons:
    - integration complexity across shells/configs, PII handling burden, must be sanitized before publishing.

### Option C: Hybrid (wrapper baseline + optional proxy hardening)
- Description:
    - always collect wrapper telemetry; enrich with proxy when available.
- Pros:
    - best coverage/portability tradeoff without forcing mode changes.
- Cons:
    - more fields and reporting complexity.

### Selected option
Why selected:
- (C) Hybrid option provides the broadest evidence base for the new evaluator.
- Use (A) when no proxy available

## 9. Privacy and Safety

- Can this change leak private data (user, host, path, IP, prompts)?
- Sanitization/redaction required for telemetry artifacts:
    - redact authorization headers, API keys, local paths, hostnames, user identifiers.
- Failure mode safety:
    - telemetry proxy failure must not crash case result generation; proxy failures are recorded in metadata and reports.
- Publication suitability:
    - raw `proxy.http.jsonl` is internal-only under `results/runs`.
    - aggregate reports never link raw proxy traces.
    - aggregate may show only sanitized summaries/excerpts/problematic lines.

## 10. Implementation Plan

0. Extend/verify `CaseResult.status` enum supports `PASS_WITH_POLICY_VIOLATION` and `SHELL_ERROR`.
1. Replace adapter-local final classification with `event_evaluator` output after validators and telemetry extraction.
2. Update aggregate cell label/class/score logic to render `PASS_WITH_POLICY_VIOLATION` separately from `PASS`.
3. Add mandatory wrapper event extraction and event schema.
4. Add optional per-case proxy lifecycle in runner and adapter routing hooks.
5. Add `event_evaluator` that derives canonical `status`, `trajectory`, `invoked`, scoring fields, and `failure_reason`.
6. Add metadata/artifact persistence and report rendering.
7. Add tests for event extraction, evaluator verdicts, proxy skip/error paths, and new taxonomy.



## 11. Acceptance Criteria (Must Be Testable)

- [ ] Events are produced deterministically from process artifacts and proxy captures.
- [ ] Proxy telemetry is optional in `auto` mode and failure-safe; proxy errors are represented as evaluator evidence, not harness crashes.
- [ ] Canonical measured verdict/scoring is produced by `event_evaluator`.
- [ ] Deterministic fallback + skip reason rendered when telemetry is missing/skipped.
- [ ] Existing commands (`run`, `rebuild-reports`, `aggregate-reports`) work with the new result contract.
- [ ] No private data regression in publishable outputs.
- [ ] Performance overhead stays within +20% in comparing with current time.
- [ ] `validators_pass + tool_event_not_observable(reason=parser_not_capable_for_shell)` produces `PASS_WITH_POLICY_VIOLATION`.
- [ ] `validators_pass + no_tool_event_observed` produces `PASS_WITH_POLICY_VIOLATION`.
- [ ] `validators_fail + no_tool_event_observed` produces `NO_TOOL_CALL`.
- [ ] `validators_pass + confirmed_tool_use` produces `PASS`.
- [ ] `validators_pass + tool_event_inconclusive` produces `PASS_WITH_POLICY_VIOLATION`.
- [ ] Optional `proxy_error` does not downgrade `PASS` when wrapper/agent-output telemetry confirms tool use.
- [ ] `PASS_WITH_POLICY_VIOLATION` is rendered separately and is not counted as full `PASS` in aggregate scoring.
- [ ] `shell_error` produces `SHELL_ERROR`.
- [ ] `nonzero_exit + validators_pass + confirmed_tool_use` produces `SHELL_ERROR`.
- [ ] `harness_capture_failed + capture_missing` produces `HARNESS_ERROR`.
- [ ] Aggregate headline uses `strict_pass_score`.
- [ ] `PASS_WITH_POLICY_VIOLATION` contributes `0.8` to `overall_score` and `0.0` to `strict_pass_score`.
- [ ] `wrapper_parse_error` produces `HARNESS_ERROR`.

## 12. Test Plan

- Unit tests:
    - parser matrix by shell, skip reasons, metadata schema, redaction rules.
- Integration tests:
    - full run with wrapper-only and with proxy-enabled modes.
- Regression checks:
    - old baseline is not expected to match exactly; verify intentional status/reason changes against evaluator fixtures.
- Manual verification:
    - case page and aggregate view for collected/skipped/error telemetry scenarios.

## 13. Observability and Reporting Impact

- New report fields/cells/tooltips:
- Source labeling:
    - canonical failure source: `event_evaluator`
    - telemetry evidence source: `wrapper|proxy` with tier `A|B|C|D`
- How to debug failures:
    - where to inspect `events.*.jsonl`, `events.summary.json`, `proxy.http.jsonl`.
- How this appears in case pages vs aggregate pages:
    - in aggregate page only reinvented fail statuses
    - in internal case pages - link to full traces and reasons for calculated status
    - in aggregate case pages reasons for new statuses.
    - aggregate never links raw proxy trace; it shows only sanitized summary/excerpt/problematic lines.


## 14. Rollout and Rollback

- Rollout strategy:
    - wrapper extraction always on; proxy default `auto`
- Migration strategy (if needed):
    - all publishable reports must be regenerated under the new evaluator contract.
- Rollback steps:
    - restore previous evaluator/reporting code and regenerate reports from old-compatible artifacts if still available.

## 15. Local Review Checklist (No PR)

- [ ] Spec completed before code change.
- [ ] Source-tier and skip matrix are explicit and testable.
- [ ] Benchmark comparability constraints are explicit.
- [ ] Acceptance criteria are measurable.
- [ ] Privacy/redaction impact reviewed.
- [ ] Docs update list is complete.
- [ ] Regeneration commands were validated locally.

## 16. Implementation Notes

- `2026-05-14`: in current MVP implementation, `--telemetry-proxy force` is treated as a strict requirement.
- If proxy capture is not available/collected, the runner upgrades the case to:
  - `status=HARNESS_ERROR`
  - `invoked=no`
  - `match_percent=0`
  - `failure_reason=proxy_required_but_not_available`
- Telemetry metadata for this path is deterministic:
  - `telemetry_proxy_status=error`
  - `telemetry_proxy_skip_reason=unsupported_backend` (until active proxy capture is implemented)
  - `tool_event_verdict=tool_event_inconclusive`
  - `tool_event_verdict_reason=proxy_error`
- `--telemetry-proxy auto` remains non-fatal (`skipped` when proxy routing is unsupported).
- Internal case report (raw/internal report) must include direct links to telemetry JSONL artifacts when present:
  - `artifacts/events.warmup.jsonl`
  - `artifacts/events.measured.jsonl`
  - `artifacts/proxy.http.jsonl`
