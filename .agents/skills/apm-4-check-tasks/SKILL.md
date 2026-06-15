---
name: apm-4-check-tasks
description: 将 Task Prompt 交付给 APM Worker。
user-invocable: true
---

## 0. 纯中文本土化执行规范

本文件是 APM 中文本土化版本。执行时必须遵守以下规则：

- 本文件的中文说明就是实际执行口径，不需要再参考英文原文。
- 面向用户的解释、提问、分析、总结、风险说明、审查意见和下一步指令必须使用中文。
- APM 项目产物正文必须使用中文，包括 `.apm/spec.md`、`.apm/plan.md`、`AGENTS.md` 中的 APM 规则、Task Prompt、Task Log、Task Report、Handoff Log、Recovery Summary、Stage Summary、Memory Notes 和 Working Notes。
- 可以保留英文的内容仅限命令、路径、代码标识、YAML 字段、Markdown 结构标题、状态值、Agent 名称、Task ID、mermaid 语法、协议字段、库名、框架名和行业通用缩写。
- 不得为了节省上下文而删除流程约束。必须保留审批门槛、上下文边界、依赖判定、验证标准、日志格式、Message Bus、Handoff、Recovery、Tracker 和 Memory 相关规则。
- 如果发现规则缺口，用中文补足；不要回退到英文说明。

---
# APM 1.0.1 - Worker 检查任务命令

检查当前 Worker 的 Task Bus 是否有待执行的 Task Prompt。如果你是 Planner、Manager 或非 APM agent，请简要拒绝并停止。

本命令替代手动引用文件。你需要从已注册身份或 `[agent-id]` 参数解析 bus 路径。

参数：可选 `[agent-id]`。如果当前 Worker 已注册，忽略该参数；如果未注册，则必须提供该参数来解析身份。

**流程：**

1. 判断注册状态：
   - 如果已注册，从注册信息得到 bus 路径，进入第 3 步。
   - 如果未注册，必须使用 `(the text provided by the User after the command invocation, if any)`。如果未提供参数，告知用户需要 agent-id。

2. 解析 agent-id：仅适用于未注册 Worker。按 `.agents\skills\apm-communication\SKILL.md` 的规则解析 `(the text provided by the User after the command invocation, if any)`，并执行 `.agents\skills\apm-3-initiate-worker\SKILL.md` 的启动流程。

3. 读取 Task Bus：

   ```text
   .apm/bus/<agent-slug>/task.md
   ```

   - 如果为空，告知用户当前没有待处理任务。
   - 如果有内容，进入第 4 步。

4. 校验 Task Prompt YAML frontmatter 中的 `agent` 字段是否匹配当前身份。如果不匹配，说明路由错误，拒绝执行并提示用户切换到正确 Worker。如果匹配，按 `.codex\apm-guides\task-execution.md` 执行任务。

---

**命令结束**
