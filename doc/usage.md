# Usage

This file lists the primary run metadata keys used in reports.

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

