# GripProbe-CLI

GripProbe is a benchmark framework for CLI AI agents, focused on small and local models and on artifact-first evaluation of tool use.

The goal is not to measure general intelligence, but to evaluate tool-use reliability in real local CLI setups and verify whether local LLMs actually use tools, modify files, and execute commands.

Results are environment-specific and may vary by runtime, quantization, prompt formatting, hardware, seed, and model version.

## What GripProbe Measures

Typical tool-calling benchmarks evaluate parsed tool calls in synthetic, API-like settings.
GripProbe evaluates observable side effects in real CLI agent environments.
It distinguishes textual success from executed success.
It is aimed at model/shell/backend compatibility rather than model-only ranking.

## Published Reports:
- HTML report: [https://ryg-.github.io/GripProbe-CLI/report/summary.html]
- Markdown summary: report/summary.md

### Early observations

These initial results suggest that shell choice is a first-order variable.
The same model can perform strongly in one CLI shell and fail badly in another, which supports GripProbe’s focus on model × shell × backend compatibility rather than model-only ranking.

In the current published runs, `continue-cli` is the strongest shell.
It delivers the highest pass rates across multiple local 9B–12B class models and is currently the most consistent shell in the published report.

Within `continue-cli`, the top result comes from `local/aravhawk/qwen3.5-opus-4.6-text:9b`, followed by official `local/qwen3.5:9b`.
This suggests that fine-tuning or distillation can materially affect CLI execution reliability, not just general chat quality.

For public recommendations, official `local/qwen3.5:9b` is the safer reference point.
Its results are close to the top of the current report, while its provenance and licensing surface are clearer than third-party distilled variants.

These observations are preliminary.
GripProbe results are environment-specific and may change with runtime, quantization, prompt formatting, hardware, shell version, and future benchmark coverage.


## Documentation
Privacy and publication policy:
- Privacy policy [docs/privacy.md](docs/privacy.md)
- Preparation guide: [docs/preparation.md](docs/preparation.md)
- Usage and metadata keys [docs/usage.md](docs/usage.md)
- Test descriptions [docs/tests.md](docs/tests.md)

## GripProbe produces:
- internal per-run diagnostic results `results/runs/...`
- sanitized aggregate reports for sharing `results/aggregate/...`
- HTML summaries for browsing and comparison

## Publication rule:
- publish/share from `results/aggregate/...` only
- treat `results/runs/...` as internal diagnostic data


If you would like to add a new test, refine an existing one, support another shell or backend, or suggest improvements to the benchmark, reporting, or documentation, contributions are welcome. Feel free to open an issue or submit a pull request.