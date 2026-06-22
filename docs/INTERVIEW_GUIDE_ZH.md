# RepoTrace AgentOps 面试指南

## 60 秒项目介绍

RepoTrace AgentOps 是我基于一个通用 Agent runtime 改造出的本地可观测与评测平台，目标是解决软件工程 Agent 难复盘、难审计、难评测的问题。原 runtime 能执行工具和恢复会话，但运行结束后缺少结构化 trace；我新增了持久化 trace store、权限审计、风险分类、eval scorecard 和 dashboard，让每次 agent run 的工具调用、权限决策、错误、耗时和 token 使用都能被查询和导出。

## 技术难点

- 如何在不大改模型循环的情况下捕获完整运行链路。
- 如何把 UI 事件和 session snapshot 区分为可长期分析的 trace 数据。
- 如何在工具真正执行前记录权限决策和风险类别。
- 如何设计 deterministic eval，让项目不依赖在线 LLM 也能稳定展示工程能力。
- 如何用公开 benchmark smoke 作为背书，同时避免夸大成完整 SWE-bench 性能。

## 简历 Bullet

- 设计并实现 AgentOps trace layer，将 assistant turn、tool call/result、permission decision、error、compact event 和 token usage 持久化为 JSONL run timeline，支持按 run 查询和 Markdown/JSON 导出。
- 针对 coding agent 难审计的问题，在工具执行链路中加入权限决策记录和风险分类，覆盖 read-only、filesystem-write、shell-command、network、credential-risk 等场景。
- 构建 deterministic local eval 与 SWE-bench smoke adapter，输出 pass rate、tool error rate、permission block、token footprint 等 scorecard 指标，用于回归验证和面试演示。
- 重构项目对外叙事与 dashboard，将原有通用 Agent runtime 包装为可复盘、可度量、可治理的 AgentOps 平台。

## 高频追问

**为什么不直接用日志？**  
日志适合排错，但缺少稳定 schema、run_id、事件类型和可导出 scorecard。RepoTrace 的 trace 是产品数据，不只是 debug 文本。

**原项目不是已经有 ToolExecutionStarted/Completed 吗？**  
有，但它们主要服务 UI 实时渲染。RepoTrace 把这些事件持久化，并补上权限审计、风险分类、耗时、scorecard 和导出能力。

**为什么需要本地 eval？**  
本地 eval 验证的是 AgentOps 产品能力：trace 是否完整、权限是否可审计、工具错误是否可见。公开 benchmark 更适合验证 coding-agent 解题能力，二者目标不同。

**SWE-bench smoke 是不是完整跑分？**  
不是。它是公开 benchmark 兼容性 smoke test。完整跑分需要更重的 Docker 和算力环境，项目文档里明确不夸大。

**如果扩展到生产环境，下一步做什么？**  
下一步会做 SQLite/OpenTelemetry exporter、多项目 trace index、PII 脱敏、trace retention policy，以及真实 SWE-bench Lite 子集执行。
