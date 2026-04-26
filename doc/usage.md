# Usage

This file lists the primary run metadata keys used in reports.

## Aggregate report metrics

- `Score`: normalized weighted pass ratio across tests in a row.
  - sanity tests use lower weight (`0.8`) than non-sanity tests (`1.0`), then score is normalized back to `0..100%`.
- `Typical Time`: median measured time across representative results in the row.
  - representative result is the PASS case when available, otherwise the first available case.
- `Outliers`: number of tests in the row whose representative time exceeds baseline median for that test by factor `2.5`.
  - displayed as `count/total_tests_in_row`.

## User-provided keys (`--metadata key=value`)

- `hardware_profile_id`: profile id from `specs/hardware_profiles.yaml`. Used by aggregate HTML for hardware cards and row grouping.
- `suite`: optional marker for grouping related runs (for example: `aggregate_full_passed_matrix`).
- `run_note`: optional free-form label for experiment context.

## Automatically captured runtime keys

- `shell_executable`
- `shell_executable_path` (sanitized to `$HOME/...`)
- `shell_version`
- `shell_version_exit_code`
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
