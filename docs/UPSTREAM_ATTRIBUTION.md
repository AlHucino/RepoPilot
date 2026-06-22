# Upstream Attribution

RepoPilot is a derivative work based on the MIT-licensed OpenHarness project.

This repository keeps the upstream copyright and license notice in `LICENSE` and records the relationship here for clarity. RepoPilot's public product identity, CLI, dashboard, README, and interview materials are separate from the upstream project.

## RepoPilot Additions

- durable run timeline storage under `.repopilot/traces/`
- `repopilot trace list/show/export`
- deterministic local eval and SWE-bench smoke scorecards
- permission decision and tool-risk audit records
- RepoPilot dashboard focused on run timeline, tool failures, permission audit, and eval scorecards
- resume/interview-oriented architecture and evaluation documentation

## Compatibility Note

Some internal runtime modules intentionally keep compatibility-oriented names to avoid a broad package migration. Public packaging and user-facing documentation are branded as RepoPilot.
