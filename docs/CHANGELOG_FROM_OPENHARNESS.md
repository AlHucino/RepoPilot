# Changes From The Base Runtime

## What Changed

- Added a persistent AgentOps trace store.
- Added permission decision audit events.
- Added risk classification for tools and commands.
- Added trace list/show/export CLI commands.
- Added deterministic local evals and scorecards.
- Added SWE-bench smoke metadata flow.
- Replaced the old project-facing README with RepoTrace AgentOps positioning.
- Reworked the dashboard from task kanban to trace timeline and eval scorecard.

## Why It Changed

The base runtime was useful for running an agent, but it was harder to explain failures after the run ended. RepoTrace addresses that gap by making every run inspectable:

- what the model asked to do
- which tools were called
- why permissions allowed or blocked actions
- how long tools took
- where errors occurred
- how much token budget was consumed

## Pain Points Solved

- Debugging no longer depends on scrolling through terminal output.
- Permission prompts become auditable events instead of transient UI moments.
- Eval runs produce stable scorecards instead of informal manual demos.
- Interview discussion can focus on trace design, data flow, safety, and validation.
