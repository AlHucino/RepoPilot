# RepoPilot

**AI Coding Agent for Repository Tasks**

RepoPilot is a local coding-agent runtime for repository work: it can plan against a codebase, call tools, edit files, run checks, keep session context, and produce an inspectable execution record for each run.

The project is built for realistic software-engineering workflows rather than one-off chat demos. It focuses on the parts interviewers usually care about in agent systems: model-tool orchestration, permission boundaries, failure diagnosis, repeatable evaluation, and a dashboard that makes runs easy to review.

## Highlights

- Tool-aware agent loop for repository tasks
- Multi-provider model configuration
- File, shell, search, web, MCP, task, and memory-oriented tools
- Permission checks before risky tool execution
- Durable run timeline under `.repopilot/traces/`
- Trace export as JSON or Markdown
- Deterministic local evals and SWE-bench smoke adapter
- Static dashboard for run timeline, tool failures, permission audit, and scorecard review

## Quick Start

```bash
uv sync --extra dev
uv run repopilot eval run --suite local
uv run repopilot trace list
uv run repopilot trace show <run_id>
uv run repopilot trace export <run_id>
uv run repopilot dashboard snapshot
```

Dashboard:

```bash
cd repopilot-dashboard
npm ci
npm run snapshot
npm run dev
```

## Core Commands

```bash
repopilot trace list
repopilot trace show <run_id>
repopilot trace show <run_id> --raw
repopilot trace export <run_id> --format markdown
repopilot trace export <run_id> --format json
repopilot eval run --suite local
repopilot eval run --suite swebench-smoke
repopilot dashboard snapshot
```

## Architecture

RepoPilot keeps the live runtime event stream as the source of truth and adds a durable run record:

1. `QueryEngine` creates one `TraceRecorder` for each user run.
2. Runtime events are appended as assistant turns, tool starts, tool completions, errors, and compact events.
3. Tool execution records permission decisions and risk categories before side effects run.
4. `repopilot dashboard snapshot` exports those real traces and the latest scorecard to `repopilot-dashboard/public/snapshot.json`.
5. CLI summaries, Markdown exports, eval scorecards, and the dashboard read from the same trace store.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Evaluation

The local eval suite is deterministic. It validates RepoPilot's engineering surface: trace completeness, audit records, tool-failure visibility, compact-event continuity, and scorecard generation.

The SWE-bench smoke suite records public-benchmark-shaped metadata so the project can explain compatibility with SWE-bench Lite/Verified without pretending every demo run executes a full benchmark solve.

See [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md).

## Attribution

RepoPilot keeps upstream attribution in [NOTICE.md](NOTICE.md) and the license file while presenting RepoPilot as the public project identity.
