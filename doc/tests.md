# Test Descriptions

This document is the baseline catalog for test scenarios in `specs/tests`.
It starts with complex scenarios and web-specific cases, and can be extended over time.

## Web Nonce Proof (`web_nonce_proof`)

- Goal: verify that the model performs a real HTTP fetch and computes a derived value.
- Input files in workspace:
  - `challenge-url.txt`
- Required action:
  - fetch JSON from the URL (`nonce`, `payload`);
  - write `web-proof.txt` with:
    - `NONCE=<nonce>`
    - `PAYLOAD=<payload>`
    - `PROOF=<sha256(nonce:payload)>`
- Validation:
  - output file content is exact;
  - measured challenge path was actually requested (request log hit).

## Web Search JSON Ranked (`web_search_json_ranked`)

- Goal: verify realistic API-style web search flow with parsing and ranking.
- Local server contract:
  - method: `GET`
  - path: `/search/<token>`
  - query params:
    - `q` (required, from `query.txt`)
    - `format=json` (optional hint)
    - `limit=8` (optional hint)
  - response body (JSON):
    - `query` (echoed query string)
    - `results` (array of objects with `id`, `title`, `url`, `snippet`, `score`, `lang`)
    - `total`, `returned`
    - `error` (empty on valid query)
- Input files in workspace:
  - `search-url.txt`
  - `query.txt`
  - `required-token.txt`
- Required action:
  - call search endpoint with `q=<query>`;
  - choose the highest-score result among those where `snippet` contains `required-token`;
  - write `search-result.json` with keys:
    - `query`
    - `selected_id`
    - `selected_url`
    - `selected_score`
- Validation:
  - structured JSON fields must match expected measured values;
  - measured search path must be requested (request log hit).

## Web Fetch JSON Raw (`web_fetch_json_raw`)

- Goal: isolate pure web/API access without ranking logic.
- Local server contract:
  - method: `GET`
  - path: `/search/<token>`
  - query params:
    - `q` (required, from `query.txt`)
    - `format=json` (optional hint)
    - `limit=8` (optional hint)
  - response body (JSON):
    - `query`
    - `results`
    - `total`, `returned`
    - `error`
- Input files in workspace:
  - `search-url.txt`
  - `query.txt`
- Required action:
  - call search endpoint with `q=<query>`;
  - save raw JSON as-is into `search-response.json`.
- Validation:
  - JSON must contain expected measured `query`, `total`, `returned`;
  - measured search path must be requested (request log hit).

## JSON Rank From File (`json_rank_from_file`)

- Goal: isolate JSON parsing/ranking logic without network calls.
- Input files in workspace:
  - `search-response.json` (pre-seeded fixture)
  - `required-token.txt`
- Required action:
  - pick highest-score result among snippets containing required token;
  - write `search-result.json` with:
    - `query`
    - `selected_id`
    - `selected_url`
    - `selected_score`
- Validation:
  - JSON fields are checked structurally against expected values;
  - no request-hit check is required for this file-only scenario.

## Weekly Plan Next Week (`weekly_plan_next_week`)

- Goal: verify structured edit in the middle of Markdown, not append-only behavior.
- Input file in workspace:
  - `Plan.md` with week sections and trailing `Monthly Summary` section.
- Required action:
  - add task into the **next week** section only.
- Validation:
  - unchecked checkbox with exact expected task text must appear in next-week section;
  - appending the task after `Monthly Summary` does not pass.
