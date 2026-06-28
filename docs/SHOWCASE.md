# RepoPilot Showcase

## Generate Demo Data

```bash
uv run repopilot eval run --suite local
uv run repopilot trace list
uv run repopilot dashboard snapshot
```

The local eval writes trace files under `.repopilot/traces/` and a scorecard under `.repopilot/evals/`. The dashboard snapshot command converts those real artifacts into `repopilot-dashboard/public/snapshot.json`.

## Export A Run

```bash
uv run repopilot trace export <run_id> --format markdown
```

The exported Markdown report summarizes request metadata, tool calls, permission decisions, errors, token usage, and duration.

## Run The Dashboard

```bash
cd repopilot-dashboard
npm ci
npm run snapshot
npm run dev
```

The dashboard consumes the generated `snapshot.json` from `.repopilot` traces and renders run timeline, tool failures, permission audit counts, and eval scorecard metrics.
