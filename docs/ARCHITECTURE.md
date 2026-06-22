# Architecture

RepoPilot is organized around a model-tool runtime plus a durable run timeline.

## Runtime Flow

1. A user request enters `QueryEngine`.
2. `QueryEngine` starts a `TraceRecorder` with a durable `run_id`.
3. The model loop emits stream events for assistant turns, tool calls, tool results, errors, and compact progress.
4. RepoPilot serializes those events into `.repopilot/traces/run-<id>.jsonl`.
5. Tool execution records permission decisions before side effects run.
6. CLI commands, eval suites, exports, and dashboard snapshots read from the same trace store.

## Why The Run Timeline Exists

Agent failures are usually scattered across model text, tool arguments, file changes, permission prompts, retries, context compaction, and final answers. RepoPilot turns those runtime facts into inspectable project data:

- queryable run history
- reproducible Markdown/JSON exports
- permission and risk review
- tool-failure analysis
- token and latency scorecards

## Data Shape

Each JSONL event includes:

- `run_id`
- `kind`
- `timestamp`
- `elapsed_ms`
- `payload`

Common event kinds:

- `run_started`
- `assistant_turn`
- `tool_started`
- `permission_decision`
- `permission_confirmation`
- `tool_completed`
- `compact_event`
- `error`
- `run_completed`
