# Notice

RepoTrace AgentOps is a derivative work based on the MIT-licensed OpenHarness project.

The original license is preserved in `LICENSE`.

This fork adds the following project-specific work:

- durable AgentOps trace storage under `.repotrace/traces/`
- `repotrace trace list/show/export`
- deterministic local eval scorecards
- SWE-bench smoke adapter metadata flow
- permission audit events with risk classification
- AgentOps dashboard focused on trace timelines and scorecards
- architecture, evaluation, change, and interview packaging documentation

Internal module names may keep compatibility with the upstream runtime to reduce migration risk. Public packaging and user-facing documentation are branded as RepoTrace AgentOps.
