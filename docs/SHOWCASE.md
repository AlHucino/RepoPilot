# RepoPilot Showcase

## Generate Demo Data

```bash
uv run repopilot eval run --suite local
uv run repopilot trace list
```

The local eval writes trace files under `.repopilot/traces/` and a scorecard under `.repopilot/evals/`.

## Export A Run

```bash
uv run repopilot trace export <run_id> --format markdown
```

The exported Markdown report summarizes request metadata, tool calls, permission decisions, errors, token usage, and duration.

## Run The Dashboard

```bash
cd repopilot-dashboard
npm ci
npm run dev
```

The dashboard consumes `snapshot.json` and renders run timeline, tool failures, permission audit counts, and eval scorecard metrics.
