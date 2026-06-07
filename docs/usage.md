# Usage

## Quick Start

```bash
python -m gripprobe.cli --root . validate
python -m gripprobe.cli --root . run --cli-agent gptme --model local/qwen2.5:7b --backend ollama
```

If you have `qwen2.5-coder:7b` in Ollama (common), use the matching GripProbe model label:

```bash
python -m gripprobe.cli --root . run --cli-agent gptme --model local/qwen2.5-coder:7b --backend ollama
```

If you use the smaller coder variant, the matching label is `local/qwen2.5-coder:1.5b`:

```bash
python -m gripprobe.cli --root . run --cli-agent gptme --model local/qwen2.5-coder:1.5b --backend ollama
```

`--backend` is selected explicitly at runtime and defaults to `ollama`.
This avoids ambiguous backend choice when a model spec defines multiple backends.

## Docker

You can run GripProbe itself inside Docker while keeping Ollama outside the container.

Build:

```bash
docker compose build
```

Validate:

```bash
docker compose run --rm gripprobe python3 -m gripprobe.cli --root . validate
```

Run the default suite against an external Ollama endpoint:

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run-suite
```

Note: if you paste the command across multiple lines, keep the trailing `\`.
Without it, only `docker compose run ...` runs in the container and the next line (`python3 -m gripprobe.cli ...`) runs on your host Python (which may not have dependencies installed).

If runtime probes should be collected from the Ollama host over SSH, also set:

```bash
GRIPPROBE_OLLAMA_SSH_TARGET=ollama-host
```

The compose file mounts:
- the repository into `/work`
- `~/.continue` read-only for `continue-cli`
- `~/.config/opencode` read-only for `opencode`
- `~/.config/gptme` read-only for `gptme`
- `~/.ssh` read-only for remote host probes

The compose service also exports:
- `GRIPPROBE_CONTINUE_CONFIG=/tmp/gripprobe-home/.continue/config.yaml`
- `GRIPPROBE_OPENCODE_CONFIG=/tmp/gripprobe-home/.config/opencode/opencode.json`
- `HOME=/tmp/gripprobe-home` inside the container

By default, the service runs as `${UID}:${GID}` (falls back to `1000:1000`) so files in mounted `results/` are created as your host user.

Examples:

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run --cli-agent gptme --model local/qwen2.5:7b --backend ollama --formats tool
```

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run --cli-agent opencode --model local/qwen2.5:7b --backend ollama --formats tool
```

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run --cli-agent continue-cli --model local/qwen2.5:7b --backend ollama --formats tool
```

## Execution Model

GripProbe executes benchmarks as many short isolated case sessions, not as one long shared agent conversation.

Short form:

```text
run()
  -> matrix point
  -> case workspace
  -> warmup subprocess
  -> measured subprocess
  -> validators
  -> case.json
```

In practice, one matrix point is usually two short CLI agent sessions: `warmup` and `measured`, each with separate `stdout` and `stderr` logs.


## Real E2E Test

A live end-to-end test is available in `tests/e2e/test_real_model.py`.
It is opt-in and uses a real CLI agent plus a real local model, without mocks.

Default target:
- cli_agent: `gptme`
- model: `local/qwen2.5:7b`
- backend: `ollama`
- test: `shell_pwd`
- format: `markdown`

Run it explicitly:

```bash
GRIPPROBE_RUN_REAL_E2E=1 python -m pytest tests/e2e/test_real_model.py -q
```

You can override the target with environment variables such as `GRIPPROBE_REAL_MODEL`, `GRIPPROBE_REAL_SHELL`, `GRIPPROBE_REAL_BACKEND`, `GRIPPROBE_REAL_TIMEOUT_SECONDS`, and `GRIPPROBE_OPENAI_BASE_URL`. No local endpoint is stored in the repository. CLI agent binaries are expected to be available on `PATH`.


If a benchmark session crashes mid-run but the case artifacts already exist, you can rebuild summaries and HTML case pages from the run directory:

```bash
python -m gripprobe.cli rebuild-reports --run-dir results/runs/<run_id>
```

This command recreates `summary.md`, `summary.html`, and per-case HTML detail pages from the saved artifacts.

## Generate Aggregate Report

Build one top-level report from all run directories under `results/runs`:

```bash
python -m gripprobe.cli --root . aggregate-reports \
  --runs-root results/runs \
  --output-dir docs/report
```

Docker variant:

```bash
docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . aggregate-reports \
  --runs-root results/runs \
  --output-dir docs/report
```

Result files:
- HTML: `docs/report/reports/summary.html`
- Markdown: `docs/report/reports/summary.md`

If needed, you can aggregate only specific runs via `--run-dirs` instead of `--runs-root`.



This file lists the primary run metadata keys used in reports.

## Aggregate report metrics

- `Score`: normalized weighted pass ratio across tests in a row.
  - sanity tests use lower weight (`0.8`) than non-sanity tests (`1.0`), then score is normalized back to `0..100%`.
- `Typical Time`: median measured time across representative results in the row.
  - representative result is the PASS case when available, otherwise the first available case.
- `Outliers`: number of tests in the row whose representative time exceeds baseline median for that test by factor `2.5`.
  - displayed as `count/total_tests_in_row`.

## Aggregate report methodology and reproducibility

- HTML and Markdown aggregate summaries include:
  - status code glossary (`PASS`, `FAIL`, `TIMEOUT`, `NO_TOOL_CALL`, `TOOL_UNSUPPORTED`, `SHELL_ERROR`, `HARNESS_ERROR`, `SKIPPED`)
  - resume semantics note (`--resume-suite` resumes by case key `cli_agent+model+backend+format+test`)
  - reproducibility block (`generated at`, git commit, suite id, test tags, cli agent set, model set, format set, hardware profile id)
- Aggregate HTML includes links to:
  - test descriptions (`docs/tests.md`) when available
  - hardware profile spec (`specs/hardware_profiles.yaml`) when available

## User-provided keys (`--metadata key=value`)

- `hardware_profile_id`: profile id from `specs/hardware_profiles.yaml`. Used by aggregate HTML for hardware cards and row grouping.
- `suite`: optional marker for grouping related runs (for example: `aggregate_full_passed_matrix`).
- `run_note`: optional free-form label for experiment context.

## Automatically captured runtime keys

- `cli_agent_executable`
- `cli_agent_executable_path` (sanitized to `$HOME/...`)
- `cli_agent_version`
- `cli_agent_version_exit_code`
- legacy aliases are still present in run metadata: `shell_executable*`, `shell_version*`
- `ollama_context_length` (from `OLLAMA_CONTEXT_LENGTH`, if set)
- `ollama_num_parallel` (from `OLLAMA_NUM_PARALLEL`, if set)
- `ollama_flash_attention` (from `OLLAMA_FLASH_ATTENTION`, if set)
- `ollama_kv_cache_type` (from `OLLAMA_KV_CACHE_TYPE`, if set)
- `runtime_snapshots` (loadavg/meminfo/nvidia-smi and ollama `/api/ps` probe payloads)

## Recommended baseline command

```bash
python3 -m gripprobe.cli --root . run-suite \
  --suite default_cli_matrix \
  --metadata hardware_profile_id=unspecified
```
## Current Notes

- `--resume-suite` works per case (`cli_agent+model+backend+format+test`) and skips already completed cases from `results/runs/...`.
- `default_cli_matrix` is sanity-first and currently runs with `formats: tool`.
- For publication/share, use `results/aggregate/...`; keep `results/runs/...` as internal diagnostic artifacts.
- For report field changes, start from `docs/specs/report-field-change-template.md`.

## Shell Configuration

`gptme` and `cn` are resolved from `PATH`.

For `continue-cli`, provide the config path from the outside when needed:

```bash
GRIPPROBE_CONTINUE_CONFIG=/path/to/config.yaml python -m gripprobe.cli --root . run --cli-agent continue-cli --model local/qwen2.5:7b --backend ollama
```
