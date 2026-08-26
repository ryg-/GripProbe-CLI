# GripProbe-CLI: Technical System Description

## 1. Purpose and Positioning

GripProbe is a benchmark harness for CLI agents that work with local or remote LLM backends (primarily Ollama in the current configuration).  
The system evaluates not only textual answers, but real side effects in the workspace (created/modified files, applied patch, executed shell command, HTTP fetch result, etc.).

The core comparison axis is:

- **model × cli_agent × backend × format × test**

This is important: the same model can behave very differently depending on the CLI agent (for example `gptme`, `continue-cli`, `codex`, `opencode`, `aider`, `pi`) and execution mode (`tool` / `markdown` where supported).

---

## 2. High-Level Architecture

Main modules:

- `gripprobe/cli.py` — entrypoint and CLI commands.
- `gripprobe/spec_loader.py` — loading YAML specs.
- `gripprobe/runner.py` — main execution pipeline.
- `gripprobe/adapters/*.py` — CLI-agent-specific adapters.
- `gripprobe/validator_runner.py` + `gripprobe/validators/*` — result validation layer.
- `gripprobe/reporters/*` — per-run reports (`summary.md`, `summary.html`, case pages).
- `gripprobe/rebuild.py` — rebuild run reports from existing artifacts.
- `gripprobe/aggregate.py` — cross-run aggregate report builder.
- `gripprobe/suite_runner.py` — matrix/suite orchestration and resume logic.

Specs are data-driven:

- `specs/models/*.yaml`
- `specs/cli_agents/*.yaml` (with compatibility fallback to `specs/shells/*.yaml`)
- `specs/tests/*.yaml`
- `specs/suites/*.yaml`
- `specs/hardware_profiles.yaml`

---

## 3. Data Model and Specs

Pydantic schemas are defined in `gripprobe/models.py`.

Key entities:

- **`TestSpec`**: prompt, validators, tags (`sanity`, `non_sanity`, `multilingual`, etc.), allowed tools, supported cli agents/formats.
- **`ModelSpec` / `BackendSpec`**: model identity, backend mapping (`model_id`, `cli_agent_model_id`), supported formats, optional policy overrides.
- **`CliAgentSpec`**: executable, default args, default tools, supported formats, timeout.
- **`SuiteSpec`**: reusable run matrix (cli_agents/models/tests/formats) with optional explicit `matrix` overrides.
- **`CaseResult`**: normalized case outcome: status, trajectory, invocation signal, match %, timings, metadata.

The system is strongly declarative: adding new tests/models/cli_agent combinations is usually a spec change first, not a code change.

---

## 4. Execution Pipeline (Single Run)

Command `run` and suite executor `run-suite` both call `runner.run(...)`.

For each run:

1. Load and resolve specs (`model`, `cli_agent`, `backend`, tests, formats).
2. Create run directory:
   - `results/runs/<RUN_ID>/cases/...`
   - `results/runs/<RUN_ID>/reports/...`
3. Resolve runtime metadata:
   - CLI agent executable/version
   - selected environment metadata
   - runtime probes (load/memory/GPU; Ollama `/api/ps` when applicable)
4. For each case:
   - prepare **warmup** and **measured** workspaces,
   - run CLI agent adapter twice (warmup + measured),
   - validate measured workspace,
   - classify status/trajectory/invoked/match,
   - persist `case.json` and text artifacts.
5. Build per-run summaries:
   - `reports/summary.md`
   - `reports/summary.html`
   - `manifest.json`

`RUN_ID` is UTC-based (`YYYYMMDDTHHMMSSZ`).

---

## 5. Warmup/Measured Design

Every case runs in two phases:

- **Warmup**: cold-start and first-behavior observation.
- **Measured**: evaluation phase used for scoring/validation.

This allows:

- more stable timing and behavior analysis,
- explicit consistency checks between run 1 and run 2,
- trajectory analysis (clean/recovered/violated) based on measured trace plus retry rules.

The adapters store command strings and phase timestamps in metadata (`warmup_command`, `measured_command`, `*_started_at`, `*_finished_at`).

---

## 6. Adapter Layer

Benchmark condition and proxy-normalization rules are defined in
[Benchmark Methodology](./benchmark-methodology.md). CLI-agent-specific
protocol and tool differences remain part of the compatibility target, while
any normalization used to make a comparison measurable must be reported.

All CLI agents implement `CliAgentAdapter` (`gripprobe/adapters/base.py`; legacy alias `ShellAdapter`), with one contract: `run_case(case, model_spec, test_spec) -> CaseResult`.

Current adapters:

- `GptmeAdapter`
- `ContinueCliAdapter`
- `CodexAdapter`
- `OpencodeAdapter`
- `AiderAdapter`
- `PiAdapter`

Common behavior:

- isolated per-case runtime dirs (`HOME`, `XDG_*`, `TMPDIR`),
- subprocess execution with timeout and explicit start/finish markers in stdout/stderr,
- CLI-agent-specific environment/config preparation,
- post-run classification + validator-based pass/fail decision.

CLI-agent-specific nuances are intentionally preserved, because compatibility differences are the benchmark target, not noise.

---

## 7. Validation System

Validation is file/effect based (`validator_runner.py`):

- `file_equals`
- `patch_applied`
- `web_nonce_proof`
- `web_search_result`
- `weekly_plan_task`

Each test can combine multiple validators; final pass requires all validators to pass.

Observed/expected text artifacts are written per case:

- `expected.txt`
- `observed.txt`

This keeps failures explainable and rebuildable.

---

## 8. Built-In Dynamic Test Fixtures (Web/Scenario)

`runner.py` can launch ephemeral local HTTP challenge servers per case:

- **Web Nonce Proof**: return nonce/payload and verify proof derivation.
- **Web Search JSON**: return ranked JSON results and validate selection/raw fetch behavior.

Dynamic validator patching inserts measured nonce/query/path expectations into active `TestSpec` at runtime.  
This prevents static prompt memorization and enforces real fetch behavior.

---

## 9. Status, Trajectory, and Failure Semantics

Case status (`CaseResult.status`) includes:

- `PASS`, `FAIL`, `TIMEOUT`, `NO_TOOL_CALL`, `TOOL_UNSUPPORTED`,
- `SHELL_ERROR`, `HARNESS_ERROR`, `SKIPPED`.

Additional dimensions:

- **`invoked`**: `yes | no | maybe`
- **`trajectory`**: `clean | recovered | violated`
- **`match_percent`**: currently practical binary behavior for most tests (`0`/`100`)

Failure reason is inferred separately (`failure_reason.py`), e.g.:

- `tool unsupported by backend`
- `answered without invoking tool`

---

## 10. Rebuild and Resume

### Rebuild

`rebuild-reports` regenerates run reports from `results/runs/<RUN_ID>`.  
With `--recompute-case-json`, case status and metadata are recalculated from artifacts/validators if needed.

This is required when raw cases exist but report files are missing or stale.

### Resume

`run-suite --resume-suite` resumes at **case key granularity**:

- `(cli_agent, model, backend, format, test)`

Completed keys are loaded from existing `results/runs/*/cases/*/case.json` (or fallback manifest expansion).  
Only missing cases are executed.

---

## 11. Reporting Layers

### Run-level report (diagnostic)

Generated per run:

- `results/runs/<RUN_ID>/reports/summary.html`
- `results/runs/<RUN_ID>/reports/summary.md`

Used to investigate individual failures, timings, traces, and per-case detail pages.

### Aggregate report (publication/comparison)

Generated by `aggregate-reports`:

- `.../reports/summary.html`
- `.../reports/summary.md`

The aggregate groups rows by:

- cli_agent + CLI agent version + model + model hash + format + hardware profile.

It computes:

- **Score** (weighted normalized pass ratio; sanity tests have reduced weight),
- **Typical Time** (median representative measured time),
- **Outliers** (count of tests slower than baseline median × factor).

It also provides filters/sorting and links to per-case aggregate detail pages and source run summaries.

---

## 12. Privacy and Sanitization

Two layers have different policy:

- `results/runs/*` — internal/raw diagnostics (not aggressively sanitized).
- aggregate output — sanitized publication projection.

Sanitization includes:

- host/user path masking (`$HOME`, `$USER`),
- local endpoint normalization (e.g. Ollama host placeholders),
- SSH target normalization.

System-message stripping from transcripts is available and used by default for sensitive prompt minimization (`strip_system_messages_from_transcripts`).

---

## 13. Operational Notes and Limits

- No database layer yet; storage is filesystem-first (`case.json` + artifacts).
- Aggregate currently builds a compact publish surface; raw diagnostic navigation remains run-level.
- Tool invocation detection is adapter- and trace-heuristic dependent by design.
- Performance and behavior are hardware-sensitive; hardware profile metadata is first-class in aggregate comparison.

---

## 14. Practical Lifecycle

Typical workflow:

1. `validate` specs.
2. `run` (single point) or `run-suite` (matrix).
3. inspect run-level summaries for debugging.
4. optionally `rebuild-reports` for repaired/updated interpretation.
5. `aggregate-reports` for cross-run comparison/publication.
6. `backfill-model-hashes` or `list-runs` for maintenance and run discovery.

This separation keeps debugging forensics and publication artifacts decoupled, while preserving reproducibility.
