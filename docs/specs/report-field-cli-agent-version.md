# Report Field Change Spec (Template)

Use this template before implementing a new field in report output.
Scope: local workflow only (no PR requirements).

## 1. Change Summary

- Field name, it is one field: `cli agent version`
- Report layer: `run metadata -> case page -> aggregate summary (summary.html + filter)`
- Output format: `string`
- Date: `2026-05-10`

## 2. Problem and Goal

- Problem:
  - `no visioblity of tested cli version`
- Goal:
  - `give users possibility to see tested cli version and get quick filtering of tested cli version on summary reports/summary.html`
- Non-goals:
  - 

## 3. Exact Field Definition

- Source key/path:
  - `from runtime cli-agent version command output (agent-specific, e.g. --version)`
  - `parsed value is stored once in run JSON as cli_agent_version`
- Type:
  - `string`
- Allowed values:
  - `v?X.Y or v?X.Y.Z with optional suffix (-rc1, +build)`
  - `if parse fails -> use one set [\.\_\-\d\w]+ netween spaces`
  - `if parse fails -> unknown` 
- Missing value behavior:
  - `unknown`
- Calculation:
  - `should be reported by runtime call of cli agent`

## 4. Placement and Rendering

- Location in report:
  - summary.html (2 places):
    - `column renamed from "Shell" to "CLI Agent"`
    - `cell format: "<cli_agent> \n (in small gray text) <cli_agent_version>"`
    - `filter dropdown contains unique values for "<cli_agent>" and "<cli_agent> <cli_agent_version>"`
  - `cases/case-xxxx.html: add field "CLI Agent Version"`
  - `runs/xxxx.html: add field "CLI Agent Version"`
- Label shown to user:
  - `CLI Agent` instead of Shell in column name and filtering dropbox  
- Formatting:
  - just string
- Sorting/filtering impact:
  - `sorting by numbers separated by point and next alphabetically`
  - `sort parsed numeric segments first (1.9.0 < 1.10.0), then suffix, unknown last`
  - `if parse fails -> use just alphabetically`
  - `unknown must be present in filter if any run has unknown`
  - sorting in dropdown: cli agent name, then parsed numeric segments first (1.9.0 < 1.10.0), then suffix, unknown last

  
## 5. Privacy and Safety

- Can this field leak private data?
  - `no`
- Sanitization required:
  - `no`
- Publication suitability:
  - `yes`

## 6. Compatibility and Migration

- Backward compatibility:
  - `for old runs without key, render cli_agent_version as unknown`
- Rebuild behavior:
  - `if key is absent during rebuild; on failure set unknown`
- Aggregate behavior:
  - `read stored run value; do not rerun runtime version command`

## 7. Acceptance Criteria (Must Be Testable)

- [ ] `cli_agent_version` exists in run JSON after rebuild.
- [ ] Runtime version command is executed once per run. 
- [ ] Missing/old data paths render deterministic fallback.
- [ ] Case page shows `CLI Agent Version` with same value as run JSON.
- [ ] Summary page shows `<cli_agent> <cli_agent_version>` in `CLI Agent` column.
- [ ] Summary filter includes versioned option and `unknown` when applicable.
- [ ] Sorting validates `1.9.0 < 1.10.0`; `unknown` is last.
- [ ] No private host/user/path leakage in HTML/MD outputs.
- [ ] `python -m gripprobe.cli rebuild-reports --run-dir <run_id>` keeps behavior consistent.
- [ ] `python -m gripprobe.cli --root . aggregate-reports --runs-root results/runs --output-dir docs/report` completes and includes field correctly.

## 8. Test Plan

- Unit tests:
  - `version parse + fallback unknown + single-call-per-run behavior`
- Integration/regression tests:
  - `run/rebuild/aggregate commands`
  - `check from ready docker that all version are parsed and no unknown versions`
- Manual checks:
  - `all html report pages`

## 9. Local Review Checklist (No PR)

- [ ] Spec completed before code change.
- [ ] Code matches section 3 and 4 exactly.
- [ ] Privacy checks from section 5 completed.
- [ ] Docs updated (`docs/usage.md` / `docs/privacy.md` / `docs/tests.md`) if needed.
- [ ] Regenerated report artifacts validated locally.

## 10. Rollback Plan

- Revert files
- Rebuild command:
  - `python -m gripprobe.cli rebuild-reports --run-dir <run_id>`
- Aggregate refresh:
  - `python -m gripprobe.cli --root . aggregate-reports --runs-root results/runs --output-dir docs/report`
