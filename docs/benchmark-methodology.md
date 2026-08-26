# Benchmark Methodology

This document defines how GripProbe separates native benchmark results from
controlled request normalization and protocol experiments.

## Experimental Stages

Each model and CLI-agent combination should be evaluated in the following
order.

### Stage 0: Native Baseline

Run the CLI agent against the backend without proxy request mutations.

Record:

- CLI-agent and model versions;
- backend, endpoint, and model digest;
- protocol used by the agent;
- timeout and first-tool-call budget;
- original tool schema;
- first tool-call latency;
- whether a structured tool call was observed.

The native baseline is the reference for diagnosing model and agent behavior.

### Stage 1: Tool Normalization

If the native baseline does not produce a tool call within the declared
diagnostic budget, the telemetry proxy may normalize the request for the
specific test.

Allowed normalization includes:

- filtering tools that are irrelevant to the test;
- removing agent-specific instruction noise;
- preserving the semantic capability required by the test.

For example, a shell test may retain only `exec_command` and `write_stdin`.
This is a compatibility normalization, not a native baseline. Different CLI
agents expose different tool inventories, so tool normalization may be a
reasonable comparison condition when it is explicit and reproducible.

### Stage 2: Request Tuning

The proxy may set request fields such as reasoning effort or temperature.

Every requested field must be classified independently as:

- requested by the experiment;
- applied by the proxy;
- confirmed by the upstream endpoint;
- unknown or ignored by the upstream endpoint.

Presence in the outgoing request does not prove that the model or backend
accepted the field. This is particularly important for backend-specific
thinking controls such as `think`.

### Stage 3: Protocol Translation

Translation between protocols, such as Responses API and native Ollama Chat
API, is a separate experimental mode.

Protocol translation must not be enabled implicitly. Its results must not be
compared directly with native baseline results without an explicit condition
label, because the adapter is then part of the system under test.

## Timeout Policy

Timeout is an evaluation boundary, not a model fix. The first-tool-call
budget and the full case timeout should be declared before comparing runs.
Changing either value creates a different experimental condition and must be
recorded in run metadata.

## Reporting Requirements

Every case using proxy normalization should expose the experimental condition
in its diagnostic metadata and, where the report has room, in the case view:

- protocol and endpoint type;
- proxy mode and normalization profile;
- original and effective tool counts;
- original and effective tool names when safe to show;
- removed instruction categories;
- request fields changed;
- whether protocol translation was used;
- timeout and first-tool-call budget;
- proxy lifecycle or upstream errors.

The result should distinguish at least these causes:

- model did not produce a tool call;
- CLI-agent and backend protocol were incompatible;
- request was normalized by the proxy;
- proxy lifecycle or capture failed;
- case timed out.

Low-level proxy artifacts remain the detailed evidence source. Aggregate
reports should show the condition label and a sanitized summary rather than
linking raw proxy traffic.

## Comparison Rules

- Native baseline results answer whether the unmodified agent/backend path
  works.
- Tool-normalized results answer whether the same test works under an explicit
  reduced tool contract.
- Request-tuned results answer whether a declared request control changes the
  outcome, subject to confirmation that the backend applied it.
- Protocol-translated results answer whether the compatibility bridge works;
  they are not native agent results.

When a later stage succeeds after an earlier stage fails, report both results
and the changed condition. Do not rewrite the native failure as a clean pass.
