# Contributing to RepoPilot

RepoPilot is focused on repository-task coding-agent workflows: tool orchestration, permission boundaries, run timelines, eval scorecards, and a dashboard for reviewing agent behavior.

## Development

```bash
uv sync --extra dev
uv run pytest -q tests/test_runlog tests/test_engine tests/test_permissions
uv run ruff check src tests scripts
```

Dashboard:

```bash
cd repopilot-dashboard
npm ci
npm run build
```

## Hygiene

Do not commit credentials, local traces, caches, virtualenvs, or generated build output.

Ignored local data includes `.repopilot/`, `.openharness/`, `.env`, `.venv/`, `node_modules/`, and `dist/`.
