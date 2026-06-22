# Architecture

RepoTrace adds an AgentOps layer on top of the existing agent runtime.

## Runtime Flow

1. A user request enters `QueryEngine`.
2. `QueryEngine` starts a `TraceRecorder` with a durable `run_id`.
3. The model loop emits stream events for assistant text, tool calls, tool results, errors, and compact progress.
4. RepoTrace serializes those events into `.repotrace/traces/run-<id>.jsonl`.
5. Tool execution records permission decisions before side effects run.
6. CLI, eval suites, exports, and dashboard snapshots read from the trace store.

## Why The Trace Layer Exists

The base runtime already had UI events and session snapshots, but those are optimized for rendering and resume. RepoTrace turns the same execution facts into an audit and evaluation product:

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
