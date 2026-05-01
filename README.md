# GripProbe-CLI

GripProbe is a benchmark framework for CLI AI agents, focused on small and local models and artifact-first tool-use evaluation.

The goal is not to measure general intelligence, but to evaluate tool-use reliability in real local setups and
verify whether local LLMs in CLI agent environments actually use tools, modify files, and execute commands.

Results are environment-specific and may vary by runtime, quantization, prompt formatting, hardware, seed, and model version.

## What GripProbe Measures

Typical tool-calling benchmarks evaluate parsed tool calls in synthetic, API-like settings.
GripProbe evaluates observable side effects in real CLI agent environments.
It distinguishes textual success from executed success.
It is aimed at model x shell x backend compatibility rather than model-only ranking.

Privacy and publication policy:
- `results/runs/...` is the internal diagnostic layer
- `results/aggregate/...` is the sanitized sharing/publication layer
- see [docs/privacy.md](docs/privacy.md)
- preparation guide: [docs/preparation.md](docs/preparation.md)
- run metadata keys: [docs/usage.md](docs/usage.md)

Current MVP slice:
- shell executables are resolved from `PATH`, not from machine-specific absolute paths
- YAML specs validated into Pydantic models
- one working adapter: `gptme`
- one scaffold adapter: `continue-cli`
- canonical JSON results
- generated Markdown and HTML summaries
- Docker scaffolding for isolated execution

