# RepoTrace AgentOps

RepoTrace AgentOps is a local observability, permission-audit, and eval-scorecard layer for software-engineering agents.

It turns an agent runtime from a live chat/tool loop into a system that can be inspected after the fact: every run gets a durable trace, every tool call can be audited, and deterministic eval suites can produce a scorecard without depending on an external LLM call.

## Why This Project Exists

Coding agents are hard to debug because failures are usually spread across model output, tool arguments, file-system effects, permission prompts, retries, context compaction, and final answers. RepoTrace focuses on the engineering layer around the model:

- persistent JSONL traces under `.repotrace/traces/`
- permission decisions with risk categories
- tool duration, error flags, and output previews
- token usage and compact-event capture
- deterministic local evals plus a lightweight SWE-bench smoke adapter
- a static dashboard for trace timelines and eval scorecards

## Quick Start

```bash
uv sync --extra dev
uv run repotrace eval run --suite local
uv run repotrace trace list
uv run repotrace trace show <run_id>
uv run repotrace trace export <run_id>
```

Dashboard:

```bash
cd agentops-dashboard
npm ci
npm run dev
```

## Core Commands

```bash
repotrace trace list
repotrace trace show <run_id>
repotrace trace show <run_id> --raw
repotrace trace export <run_id> --format markdown
repotrace trace export <run_id> --format json
repotrace eval run --suite local
repotrace eval run --suite swebench-smoke
```

## Architecture

RepoTrace keeps the original runtime event stream as the source of truth and adds a durable AgentOps layer:

1. `QueryEngine` creates one `TraceRecorder` for each user run.
2. Runtime stream events are appended to JSONL as assistant turns, tool starts, tool completions, errors, and compact events.
3. Tool execution records permission decisions and risk categories before side effects run.
4. The trace store powers CLI summaries, Markdown exports, local eval scorecards, and the static dashboard.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Eval Strategy

The local eval suite is deterministic by design. It validates RepoTrace's own product surface: trace completeness, audit records, tool-failure visibility, compact-event continuity, and scorecard generation.

The SWE-bench smoke suite is intentionally lightweight. It records public-benchmark-shaped metadata so the project can explain compatibility with SWE-bench Lite/Verified without pretending that every demo run executes a full Docker-heavy benchmark solve.

See [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md).

## Attribution

RepoTrace AgentOps is a derivative work based on the MIT-licensed OpenHarness codebase. The new AgentOps trace store, eval scorecards, `repotrace` CLI, dashboard rewrite, and interview-oriented documentation are added in this fork.

See [NOTICE.md](NOTICE.md).
