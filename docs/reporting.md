# Reporting (Overview)

## 1) Process: where data is collected, stored, and by which command

1. `run` (or `run-suite`) executes cases and stores raw outputs in:
- `results/runs/<RUN_ID>/cases/<CASE_ID>/...`
- `results/runs/<RUN_ID>/cases/<CASE_ID>/case.json`

2. After `run` finishes, a run-level report is generated:
- `results/runs/<RUN_ID>/reports/summary.html`
- `results/runs/<RUN_ID>/reports/summary.md`
- plus `results/runs/<RUN_ID>/manifest.json`

3. `rebuild-reports` works on an existing `results/runs/<RUN_ID>`:
- regenerates `reports/summary.html` and `reports/summary.md`
- with `--recompute-case-json`, it recalculates `case.json` from artifacts first, then rebuilds reports

4. `aggregate-reports` reads multiple run directories from `results/runs/*`, copies required case data into an aggregate directory, and generates:
- `<OUTPUT_DIR>/reports/summary.html`
- `<OUTPUT_DIR>/reports/summary.md`

The repository usage example uses `--output-dir docs/report`, while `results/aggregate/<NAME>` remains a valid internal output convention.

## 2) Difference between the two report layers

- Run report (`results/runs/.../reports/...`) is for a single run and stays close to raw diagnostics.
  It is mainly used for debugging and navigation through raw artifacts (failure causes, timeouts, shell/model/tool behavior).

- Aggregate report (`<OUTPUT_DIR>/reports/...`) is a cross-run summary layer with grouping and comparison.

In practice, publishing run reports is usually unnecessary (and awkward on GitHub Pages), because they are diagnostic/raw.
The aggregate layer is the publication target.

## 3) Experimental conditions

Native runs, tool-normalized runs, request-tuned runs, and protocol-translated
runs are different experimental conditions. The reporting layer must preserve
that distinction. See [Benchmark Methodology](./benchmark-methodology.md) for
the required condition labels and proxy mutation details.

## 4) What gets sanitized

Sanitization is applied when building the aggregate layer:
- home/user paths
- local usernames
- local service/host addresses (for example Ollama/SSH)
- text artifacts and string fields in copied `case.json`

Raw run data in `results/runs/*` is not rewritten.
Only the aggregate publish projection is sanitized.
