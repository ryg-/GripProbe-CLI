# GripProbe-CLI

GripProbe is a benchmark framework for CLI AI agents, focused on small and local models and artifact-first tool-use evaluation.

The goal is not to measure general intelligence, but to evaluate tool-use reliability in real local setups and
verify whether local LLMs in CLI agent environments actually use tools, modify files, and execute commands.

Results are environment-specific and may vary by runtime, quantization, prompt formatting, hardware, seed, and model version.

Privacy and publication policy:
- `results/runs/...` is the internal diagnostic layer
- `results/aggregate/...` is the sanitized sharing/publication layer
- see [docs/privacy.md](docs/privacy.md)
- preparation guide: [doc/preparation.md](doc/preparation.md)
- run metadata keys: [doc/usage.md](doc/usage.md)

Current MVP slice:
- shell executables are resolved from `PATH`, not from machine-specific absolute paths
- YAML specs validated into Pydantic models
- one working adapter: `gptme`
- one scaffold adapter: `continue-cli`
- canonical JSON results
- generated Markdown and HTML summaries
- Docker scaffolding for isolated execution

## Quick Start

```bash
python -m gripprobe.cli --root . validate
python -m gripprobe.cli --root . run --shell gptme --model local/qwen2.5:7b --backend ollama
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
  python3 -m gripprobe.cli --root . run --shell gptme --model local/qwen2.5:7b --backend ollama --formats tool
```

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run --shell opencode --model local/qwen2.5:7b --backend ollama --formats tool
```

```bash
OLLAMA_HOST=http://ollama-host:11434 docker compose run --rm gripprobe \
  python3 -m gripprobe.cli --root . run --shell continue-cli --model local/qwen2.5:7b --backend ollama --formats tool
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

In practice, one matrix point is usually two short shell sessions: `warmup` and `measured`, each with separate `stdout` and `stderr` logs.

Full execution-flow document:
- `docs_execution_flow.md`

## Real E2E Test

A live end-to-end test is available in `tests/e2e/test_real_model.py`.
It is opt-in and uses a real shell plus a real local model, without mocks.

Default target:
- shell: `gptme`
- model: `local/qwen2.5:7b`
- backend: `ollama`
- test: `shell_pwd`
- format: `markdown`

Run it explicitly:

```bash
GRIPPROBE_RUN_REAL_E2E=1 python -m pytest tests/e2e/test_real_model.py -q
```

You can override the target with environment variables such as `GRIPPROBE_REAL_MODEL`, `GRIPPROBE_REAL_SHELL`, `GRIPPROBE_REAL_BACKEND`, `GRIPPROBE_REAL_TIMEOUT_SECONDS`, and `GRIPPROBE_OPENAI_BASE_URL`. No local endpoint is stored in the repository. Shell binaries are expected to be available on `PATH`.


If a benchmark session crashes mid-run but the case artifacts already exist, you can rebuild summaries and HTML case pages from the run directory:

```bash
python -m gripprobe.cli rebuild-reports --run-dir results/runs/<run_id>
```

This command recreates `summary.md`, `summary.html`, and per-case HTML detail pages from the saved artifacts.

## Current Limitations

- `continue-cli` adapter is scaffolded but not yet implemented end-to-end
- container execution is scaffolded in `docker/`, but the first runner executes on the host
- publication sanitization policy is not yet implemented in code

## Shell Configuration

`gptme` and `cn` are resolved from `PATH`.

For `continue-cli`, provide the config path from the outside when needed:

```bash
GRIPPROBE_CONTINUE_CONFIG=/path/to/config.yaml python -m gripprobe.cli --root . run --shell continue-cli --model local/qwen2.5:7b --backend ollama
```
