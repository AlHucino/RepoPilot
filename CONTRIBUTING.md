# Contributing to RepoTrace AgentOps

RepoTrace is focused on local AgentOps capabilities for software-engineering agents.

Good contributions improve one of these areas:

- trace completeness
- permission audit quality
- deterministic eval coverage
- scorecard clarity
- dashboard readability
- documentation that explains real engineering tradeoffs

## Development

```bash
uv sync --extra dev
uv run pytest -q tests/test_agentops tests/test_engine tests/test_permissions
uv run ruff check src tests scripts
```

Dashboard:

```bash
cd agentops-dashboard
npm ci
npm run build
```

Do not commit local `.repotrace/` traces or credentials.
