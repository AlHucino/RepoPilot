# Notice

RepoPilot is a derivative work based on the MIT-licensed OpenHarness project.

This repository preserves the original MIT license notice and adds a separate project identity focused on repository-task coding agents.

Notable additions in this fork include:

- durable run timeline storage under `.repopilot/traces/`
- `repopilot trace list/show/export`
- deterministic local eval and SWE-bench smoke scorecards
- permission decision and tool-risk audit records
- RepoPilot dashboard for run review and scorecards
- updated README, architecture notes, evaluation report, and interview guide

Internal module names may keep compatibility with the upstream runtime to reduce migration risk. Public packaging and user-facing documentation are branded as RepoPilot.
