# Privacy and Publication Policy

GripProbe keeps two different result layers, and they are treated differently.

## Internal Run Results

Path pattern:

```text
results/runs/<run_id>/
```

This is the primary run output layer.

It is considered internal diagnostic data and may contain environment-specific details such as:

- local or remote hostnames
- Ollama endpoints
- SSH targets
- local filesystem paths
- sanitized or unsanitized shell/runtime metadata depending on the capture point
- raw stdout/stderr and case transcripts

These artifacts are preserved for debugging and forensic analysis.

Default policy:

- do not aggressively sanitize `results/runs/...`
- do not remove host-specific execution evidence from primary run artifacts
- treat this layer as non-publishable unless explicitly reviewed

## Aggregate Results

Path pattern:

```text
results/aggregate/<name>/
```

This is the derived presentation layer built from multiple run directories.

It is the preferred layer for sharing and publication.

Default policy:

- sanitize copied source reports
- hide or rewrite direct server addresses
- hide or rewrite local user-identifying paths
- remove broken or unsafe artifact links from aggregate-visible HTML

Current aggregate sanitization includes:

- replacing Ollama HTTP endpoints with neutral placeholders such as `http://ollama-host:11434`
- replacing SSH targets such as `ssh source-host ...` with neutral placeholders such as `ssh ollama-host ...`
- replacing local home paths with `$HOME`
- replacing local usernames with `$USER`
- removing `Raw Artifacts` sections from aggregate case pages and copied source-report case pages

## Operational Rule

Use the layers like this:

- `results/runs/...` for investigation
- `results/aggregate/...` for review, comparison, and sharing

If a report may leave the local machine, prefer generating or publishing from the aggregate layer, not directly from `results/runs/...`.

For routine benchmarking, it is recommended to run GripProbe inside a container (`docker compose run ...`). Container execution reduces accidental host-path/user leakage in runtime artifacts, avoids root-owned file issues in shared result directories, and makes runs more reproducible across environments.
