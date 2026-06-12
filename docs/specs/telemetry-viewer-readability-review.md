# Telemetry Viewer Readability Review

Date: 2026-05-21

Source: Hilbert subagent review of the Telemetry Artifact Viewer changes.

## Context

The Telemetry Artifact Viewer renders proxy telemetry artifacts such as `proxy.measured.http.jsonl`.
The main readability issue was that `x_gripprobe_body_excerpt` values were displayed as JSON strings with escaped quotes, for example `{\"model\":\"...\"}`.
That made the popup hard to read and made browser search less useful.

Raw telemetry artifacts must stay unchanged. Any readability improvements belong in the HTML viewer layer.

## Findings

1. Avoid global post-processing after `JSON.stringify`.

   A display helper that runs after `JSON.stringify()` and globally replaces escape sequences can make the displayed JSON invalid. For example, a string value like `"{\"model\":\"x\"}"` can become `"{"model":"x"}"`. It can also corrupt unrelated string values that happen to contain escaped quotes or slashes.

   Preferred approach: normalize or parse only the target excerpt fields before formatting the object for display.

2. Decode candidate excerpt text before parsing it.

   Double-escaped JSON excerpts such as `{\\\"model\\\":...}` should be decoded first. Then the viewer should retry JSON parsing and SSE parsing on the decoded value. If decoding happens only after parsing fails and the result is kept as a plain string, the structured view is never reached.

3. Handle CRLF SSE streams.

   SSE parsing should normalize `\r\n` to `\n` or split with a CRLF-aware expression. Splitting only on `\n\n` can collapse multiple `data:` events into one payload and fail JSON parsing.

## Implementation Direction

- Keep raw artifacts unchanged.
- Normalize only `x_gripprobe_body_excerpt` and `body_excerpt`.
- For excerpt fields, use this order:
  1. Decode escaped text.
  2. Try JSON parsing.
  3. Try SSE `data:` chunk parsing.
  4. Fall back to readable raw text.
- Do not globally mutate the final formatted JSON string.
- Show an explicit viewer version in the popup so rebuilt HTML can be distinguished from stale HTML.

## Suggested Test Coverage

- JSON string excerpt.
- Double-escaped JSON excerpt.
- SSE `data: {...}` excerpt.
- CRLF SSE stream.
- Regression check that final rendering does not use global escape replacement after `JSON.stringify`.
