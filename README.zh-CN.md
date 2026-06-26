# RepoPilot 中文说明

**面向代码仓库任务的 AI Coding Agent**

RepoPilot 是一个本地代码 Coding Agent，围绕“调用工具、修改文件、运行检查、上下文管理、复盘执行过程”这一整条链路设计。

项目重点在于把 coding agent 做成一个可解释、可审计、可验证的工程系统：模型如何决定调用工具、工具执行前如何过权限、失败如何定位、一次任务的耗时和 token 如何统计，都能通过结构化运行记录复盘。

## 核心能力

- 面向 repository task 的工具调用 Agent loop
- 支持多模型/provider 配置
- 支持文件、shell、搜索、web、MCP、任务与记忆相关工具
- 高风险工具执行前进行权限判断
- 每次运行生成 `.repopilot/traces/run-*.jsonl`
- 支持 `repopilot trace list/show/export`
- 支持 deterministic local eval 和 SWE-bench smoke adapter
- Dashboard 展示 timeline、tool failure、permission audit 和 eval scorecard

## 快速体验

```bash
uv sync --extra dev
uv run repopilot eval run --suite local
uv run repopilot trace list
uv run repopilot trace export <run_id>
```

Dashboard:

```bash
cd repopilot-dashboard
npm ci
npm run dev
```

## 设计目标

RepoPilot 的目标是把一次 coding-agent 任务从“模型输出 + 临时终端日志”变成可复盘的工程流程。它保留工具调用、权限决策、错误、耗时和 token usage，方便开发者回看一次任务为什么成功、哪里失败，以及后续如何改进 agent 行为。
