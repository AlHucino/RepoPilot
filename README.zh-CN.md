# RepoTrace AgentOps 中文说明

RepoTrace AgentOps 是一个面向软件工程 Agent 的本地可观测、权限审计与评测平台。

项目重点不是再做一个聊天式 coding agent，而是补齐 Agent 工程化里最容易被忽略的一层：一次 agent run 到底调用了哪些工具、为什么被允许或阻止、哪里失败、消耗多少 token、是否发生上下文压缩，以及这些信息能不能被复盘和评测。

## 核心能力

- 每次运行生成 `.repotrace/traces/run-*.jsonl`
- 记录 assistant turn、tool call、tool result、error、compact event
- 记录 permission decision、风险类别、路径/命令摘要
- 提供 `repotrace trace list/show/export`
- 提供 deterministic local eval 和 SWE-bench smoke adapter
- 提供 AgentOps dashboard 展示 timeline、风险审计和 eval scorecard

## 快速体验

```bash
uv sync --extra dev
uv run repotrace eval run --suite local
uv run repotrace trace list
uv run repotrace trace export <run_id>
```

## 面试叙事

可以把 RepoTrace 讲成：我把一个通用 Agent runtime 改造成了可复盘、可度量、可治理的 AgentOps 平台。原 runtime 只有 UI 事件和会话恢复记录，我在执行链路上新增了持久化 trace store、权限审计、风险分类和 eval scorecard，使工具调用失败、权限拒绝、成本和上下文压缩都能被结构化追踪。

详见 [docs/INTERVIEW_GUIDE_ZH.md](docs/INTERVIEW_GUIDE_ZH.md)。
