# RepoTrace Showcase

## Local Eval

```bash
uv run repotrace eval run --suite local
uv run repotrace trace list
```

The local suite creates deterministic traces for read-only tools, file writes, shell commands, credential-risk blocks, tool errors, network metadata, and compact-event continuity.

## Trace Export

```bash
uv run repotrace trace export <run_id> --format markdown
```

The exported report includes status, model, request summary, duration, tool calls, permission decisions, compact events, and token usage.

## Dashboard

```bash
cd agentops-dashboard
npm ci
npm run dev
```

The dashboard consumes `snapshot.json` and renders trace runs, a timeline, scorecard metrics, and risk-audit counts.
