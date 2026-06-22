# Eval Report

RepoTrace uses two eval layers.

## Local Deterministic Eval

Command:

```bash
uv run repotrace eval run --suite local
```

Purpose:

- validate trace creation
- validate permission audit records
- validate tool error visibility
- validate compact-event continuity
- validate scorecard generation

The local suite includes eight deterministic cases:

- read code
- search risk patterns
- apply a small file-write style change
- run a shell command
- block a credential-risk path
- preserve a tool error
- record network metadata
- keep compact events in the timeline

## SWE-bench Smoke

Command:

```bash
uv run repotrace eval run --suite swebench-smoke
```

Purpose:

- show compatibility with public benchmark-shaped metadata
- avoid requiring a heavyweight Docker benchmark solve in every local demo

This is not a claim of full SWE-bench solve performance. It is an adapter smoke test that prepares the project for future public-benchmark runs.

## Metrics

- pass rate
- tool calls
- tool error rate
- permission decisions
- permission blocks
- total tokens
- per-run duration
