# GripProbe-CLI

GripProbe is a benchmark framework for CLI AI agents, focused on small and local models and on artifact-first evaluation of tool use.

The goal is not to measure general intelligence, but to evaluate tool-use reliability in real local CLI setups and verify whether local LLMs actually use tools, modify files, and execute commands.

Results are environment-specific and may vary by runtime, quantization, prompt formatting, hardware, seed, and model version.

GripProbe produces:
- internal per-run diagnostic results `results/runs/...`
- sanitized aggregate reports for sharing `results/aggregate/...`
- HTML summaries for browsing and comparison

Publication rule:
- publish/share from `results/aggregate/...` only
- treat `results/runs/...` as internal diagnostic data

Reports:
- HTML report: [https://ryg-.github.io/GripProbe-CLI/report/summary.html]
- Markdown summary: report/summary.md

## What GripProbe Measures

Typical tool-calling benchmarks evaluate parsed tool calls in synthetic, API-like settings.
GripProbe evaluates observable side effects in real CLI agent environments.
It distinguishes textual success from executed success.
It is aimed at model/shell/backend compatibility rather than model-only ranking.


Documentation
Privacy and publication policy:
- Privacy policy [docs/privacy.md](docs/privacy.md)
- Preparation guide: [docs/preparation.md](docs/preparation.md)
- Usage and metadata keys [docs/usage.md](docs/usage.md)
- Test descriptions [docs/tests.md](docs/tests.md)

 
