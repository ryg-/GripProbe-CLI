# GripProbe-CLI
[GitHub project](https://github.com/ryg-/GripProbe-CLI/)

GripProbe is a compatibility benchmark for local CLI AI agents. It checks whether LLM-powered agents actually execute commands, modify files, and produce verifiable artifacts in real CLI environments.

GripProbe measures observable side effects in real CLI agent environments.

## Published report
The checked-in published snapshot covers 23 models and 5 CLI agents. The current source supports 6 CLI agents, including Pi; regenerate the report after new benchmark runs.
- [View the CLI-agent compatibility report](https://local-agent-bench.org/docs/report/reports-v1/summary.html)
- [Markdown summary](https://github.com/ryg-/GripProbe-CLI/blob/main/docs/report/reports-v1/summary.md)

## What the report shows

- CLI agent × model × backend compatibility for local LLM and CLI-agent setups.
- Pass/fail results based on executed artifacts, not just parsed tool calls or text answers.
- Links from aggregate results to case details for inspecting what actually happened.

The goal is not to measure general intelligence or produce a model-only leaderboard.
GripProbe evaluates tool-use reliability in real local CLI setups and verifies whether local LLMs actually use tools, modify files, and execute commands.

Results are environment-specific and may vary by runtime, quantization, prompt formatting, hardware, seed, and model version.

## What GripProbe Measures

Typical tool-calling benchmarks evaluate parsed tool calls in synthetic, API-like settings.
It distinguishes textual success from executed success.
It is aimed at CLI agent/model/backend compatibility rather than model-only ranking.

### Early observations from the first report

These initial results suggest that CLI agent choice is a first-order variable.
The same model can perform strongly in one CLI agent and fail badly in another, which supports GripProbe's focus on CLI agent × model × backend compatibility rather than model-only ranking.

In the current published runs, `continue-cli` is the strongest CLI agent.
It delivers the highest pass rates across multiple local 9B–12B class models and is currently the most consistent CLI agent in the published report.
Other CLI agents show lower pass rates in the same published environment, which is why the report should be read as compatibility evidence rather than a universal ranking.

Within `continue-cli`, the top result comes from `local/aravhawk/qwen3.5-opus-4.6-text:9b`, followed by official `local/qwen3.5:9b`.
This suggests that fine-tuning or distillation can materially affect CLI execution reliability, not just general chat quality.

Within `codex`, `local/aravhawk/qwen3.5-opus-4.6-text:9b` shows stronger results when the patch-apply workflow is available.

For public recommendations, official `local/qwen3.5:9b` with `continue-cli` is the safer reference point.
Its results are close to the top of the current report, while its provenance and licensing surface are clearer than third-party distilled variants.

These observations are preliminary.
GripProbe results are environment-specific and may change with runtime, model version, backend, quantization, prompt formatting, hardware, CLI agent version, and future benchmark coverage.


## Documentation
Privacy and publication policy:
- Privacy policy [docs/privacy.md](docs/privacy.md)
- Preparation guide: [docs/preparation.md](docs/preparation.md)
- Usage and metadata keys [docs/usage.md](docs/usage.md)
- Test descriptions [docs/tests.md](docs/tests.md)

## GripProbe produces:
- internal per-run diagnostic results `results/runs/...`
- sanitized aggregate reports for sharing in the configured output directory, for example `docs/report/reports/...`
- HTML summaries for browsing and comparison

## Publication rule:
- publish/share from an aggregate output directory only; the checked-in snapshot is `docs/report/reports-v1/...`
- treat `results/runs/...` as internal diagnostic data


If you would like to add a new test, refine an existing one, support another shell or backend, or suggest improvements to the benchmark, reporting, or documentation, contributions are welcome. Feel free to open an issue or submit a pull request.
