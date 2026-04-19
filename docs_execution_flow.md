# Execution Flow

This document describes how GripProbe executes one benchmark run and one individual matrix point.

## Core Idea

GripProbe does not keep one long-lived agent session for a whole benchmark.
Instead, each matrix point is isolated into its own short case directory and is usually executed as two short shell sessions:
- `warmup`
- `measured`

This keeps runs easier to reason about, easier to retry, and easier to inspect from logs.

## Matrix Expansion

A single `gripprobe run` expands into a matrix over:
- shell
- model
- backend
- tool format
- test

Current entry point:
- `gripprobe.runner.run(...)`

High-level flow:

```text
CLI
  -> load specs
  -> select shell/model/backend
  -> build run directory
  -> expand formats x tests
  -> for each matrix point:
       create case directory
       prepare isolated workspace
       run adapter
       write case.json
  -> write summary.md
  -> write summary.html
  -> write manifest.json
```

## One Matrix Point

A single matrix point becomes one `CaseDefinition`.
That case has:
- its own `case_id`
- its own `case_dir`
- its own `workspace_dir`
- its own logs and artifacts

Current shape:

```text
run()
  -> CaseDefinition
  -> adapter.run_case(case, model_spec, test_spec)
     -> prompt.txt
     -> warmup subprocess
     -> measured subprocess
     -> expected.txt / observed.txt
     -> validator evaluation
     -> CaseResult
  -> case.json
```

## Process Model

For real shells such as `gptme` and `continue-cli`, GripProbe uses `subprocess.run(...)` in `ShellAdapter.run_command(...)`.

That means:
- each shell execution is a separate OS process
- stdout is written directly to a file
- stderr is written directly to a file
- timeout is enforced per process
- process working directory is the case workspace

Current default behavior for one case:
- 1 warmup process
- 1 measured process

So one matrix point usually means two short-lived subprocesses.

## Detailed Runtime Flow

```text
run()
  -> load_test_specs()
  -> load_model_specs()
  -> load_shell_specs()
  -> select backend
  -> create_run_paths()
  -> loop over tool formats
     -> loop over tests
        -> prepare workspace
        -> build CaseDefinition
        -> adapter.run_case(...)
           -> write prompt.txt
           -> run_command(... warmup ...)
              -> subprocess.run(...)
              -> warmup.stdout
              -> warmup.stderr
           -> run_command(... measured ...)
              -> subprocess.run(...)
              -> measured.stdout
              -> measured.stderr
           -> read measured logs back
           -> evaluate validators
           -> write expected.txt
           -> write observed.txt
           -> build CaseResult
        -> write case.json
  -> write summary.md
  -> write summary.html
  -> write manifest.json
```

## Isolation Model

Isolation is at case level.
Each case gets a separate workspace under its case directory.

```text
results/runs/<run_id>/
  manifest.json
  reports/
    summary.md
    summary.html
  cases/
    <case_id>/
      prompt.txt
      warmup.stdout
      warmup.stderr
      measured.stdout
      measured.stderr
      expected.txt
      observed.txt
      case.json
      workspace/
        ... test-created files ...
```

## Container Mode

If `container_image` is set for a case, GripProbe still follows the same warmup/measured process model.
The difference is only that the subprocess command is wrapped with `docker run`.

So the conceptual model remains:
- one case
- two short sessions
- separate logs
- separate workspace

## Why Short Separate Sessions

GripProbe intentionally avoids one long benchmark-wide conversational session.
Benefits:
- reduced cross-test contamination
- easier log inspection
- simpler retry behavior
- cleaner attribution of stdout/stderr to a single test case
- more stable artifact-first validation

## Current Limitations

Current implementation still has some simplifications:
- cases are executed sequentially, not in parallel
- warmup and measured are both full subprocess launches
- the same shell adapter decides both execution and result classification
- summary generation happens only after the full run loop finishes
