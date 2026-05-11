# Shell Behavior (High Level)

GripProbe compares **model × shell × backend** compatibility.
Different shells are expected to behave differently even on the same model and test prompt.

## Shell Comparison

| Shell | Interaction style | Formats in GripProbe | Model routing | Runtime isolation |
| --- | --- | --- | --- | --- |
| `gptme` | Explicit tool loop (`read/patch/shell/save`) | `markdown`, `tool` | CLI `-m` + `OPENAI_BASE_URL` from `OLLAMA_HOST` | Per-case `HOME`/XDG runtime dirs |
| `continue-cli` | Agent run with explicit `--allow` tool permissions | `markdown`, `tool` | Per-case generated `.continue/config.yaml` | Per-case `HOME` + isolated Continue config |
| `opencode` | JSON event stream execution (`opencode run --format json`) | `markdown`, `tool` | Per-case generated `opencode.json` + `--model` | Per-case `HOME`/XDG runtime dirs |
| `aider` | File-edit chat loop (no separate tool protocol in output) | `markdown` | CLI `--model` (`ollama/<model>` for Ollama) | Per-case `HOME` + isolated `.aider.conf.yml` |
| `codex` | OSS tool-call loop (`codex exec --oss --json`) | `tool` | CLI provider/model + `CODEX_OSS_BASE_URL` from `OLLAMA_HOST` | Per-case `CODEX_HOME`, ephemeral run |

## Why Results Differ Across Shells

- Tool invocation signals are shell-specific. Some shells emit explicit tool events; some only show textual traces.
- Permission and sandbox behavior differs, so the same command can pass in one shell and fail in another.
- Model wiring differs (`config file` vs `CLI flags`), which can change the effective provider endpoint or options.
- Patch/edit flows differ: one shell can use a native patch action, another can fall back to rewrite-style edits.

## How To Read Test Outcomes

- Compare shells as execution environments, not only as UI wrappers.
- Use `invoked`, `trajectory`, and `failure_reason` together with `PASS/FAIL`.
- For patch tasks, prefer comparing both:
  - `Patch File` (simple mutation path)
  - `Patch File From Prepared Patch` (strict read+patch flow)

## Codex Local Model Metadata

For local OSS models in Codex CLI, missing metadata can cause warnings like:
`Model metadata for <model> not found. Defaulting to fallback metadata`.

GripProbe includes a local catalog file:
- `configs/codex-model-catalog.local.json`
- contains entries for:
  - `cryptidbleh/gemma4-claude-opus-4.6:latest`
  - `aravhawk/qwen3.5-opus-4.6-text:9b`
  - `qwen3.5:9b`
  - `pleasecech/qwen3.6-plus:latest`
  - `gpt-oss:20b`

Interactive run example:

```bash
codex --oss --local-provider ollama \
  -m aravhawk/qwen3.5-opus-4.6-text:9b \
  -c 'model_catalog_json="/absolute/path/to/GripProbe-CLI/configs/codex-model-catalog.local.json"'
```

Persistent setup (`~/.codex/config.toml`):

```toml
oss_provider = "ollama"
model_catalog_json = "/absolute/path/to/GripProbe-CLI/configs/codex-model-catalog.local.json"
```
