---
name: apm-7-handoff-worker
description: 执行 APM Worker Handoff。
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
# APM 1.0.1 - Worker Handoff 命令

## 1. 目标

当 Worker 的上下文窗口接近上限、发生自动压缩、输出质量下降，或用户要求交接时，执行本命令。

你需要创建两类产物：

- **Handoff Log**：记录当前 Worker 实例的工作上下文，保存到 `.apm/memory/handoffs/<agent>/`。
- **Handoff Prompt**：写入 `.apm/bus/<agent-slug>/handoff.md`，指导下一个 Worker 如何恢复。

新的 Worker 需要结合 Handoff Log 和当前 Stage 的 Task Logs 恢复上下文。它还必须在第一份 Task Report 中说明自己是 Handoff 后的新实例，方便 Manager 正确处理依赖上下文。

---

## 0. 中文交接产物强制规则

Worker Handoff 产物必须使用中文正文。

- Handoff Log 中的已完成工作、技术判断、实现方式、已尝试方法、未记录细节和恢复事件必须中文。
- Handoff Prompt 中的当前状态、下一步动作、待读 Task Logs、mid-task 或 mid-batch 状态说明必须中文。
- YAML 字段、路径、命令、Task ID、Agent 名称、分支名、状态值可以保留英文。
- 如果引用英文命令输出、错误消息或代码片段，必须补充中文解释。

---

## 2. 执行流程

### 2.1 创建 Handoff Log

执行以下动作：

1. 判断当前 Worker instance number 和下一个 Worker instance number。
2. 创建 Handoff Log，记录过去发生的事情。内容使用过去时，不写当前待办状态。
3. 必须覆盖：
   - 当前实例完成的 Tasks；
   - 当前 Stage 中该 Worker 的进度；
   - 已形成的工作模式、技术判断和实现方式；
   - Task Logs 中没有记录但对后续执行有价值的技术细节；
   - 如果任务执行到一半，记录已完成步骤和尝试过的方法；
   - 当前实例是否发生过自动压缩或 Recover。

### 2.2 创建 Handoff Prompt

执行以下动作：

1. 创建 Handoff Prompt，记录当前状态和下一步动作。内容必须可执行、使用现在时。
2. 根据状态选择：
   - **Mid-Task**：说明任务仍在 `task.md` 中，列出已完成步骤和下一步。
   - **Mid-batch**：说明 batch 仍在 `task.md` 中，逐个列出哪些完成、哪些进行中、哪些未开始。
   - **Between-Tasks**：说明当前没有 active Task，等待用户运行 `apm-4-check-tasks`。
3. 包含 Handoff Log 路径、需要读取的当前 Stage Task Logs，以及第一份 Task Report 必须声明 Handoff 状态的提醒。

### 2.3 用户审查和完成

1. 写入 Handoff Prompt：

   ```text
   .apm/bus/<agent-slug>/handoff.md
   ```

2. 向用户展示 Handoff Log 路径和 Handoff Bus 路径，请用户审查。
3. 指导用户新开 Worker 会话并运行：

   ```text
   /apm-3-initiate-worker <agent-id>
   ```

   Codex CLI 使用：

   ```text
   $apm-3-initiate-worker <agent-id>
   ```

4. 如果用户要求修改，更新产物后再结束。完成后，当前 Worker 不再继续执行。

---

## 3. Handoff Log 结构

位置：

```text
.apm/memory/handoffs/<agent>/handoff-<NN>.log.md
```

YAML frontmatter：

```yaml
---
agent: <agent-slug>
outgoing: <N>
incoming: <N+1>
handoff: <N>
stage: <N>
---
```

正文结构：

```markdown
# <Display Name> Handoff <N> (<Display Name> <N> -> <Display Name> <N+1>)

## Summary

## Working Context

## Working Notes
```

---

## 4. Handoff Prompt 结构

写入：

```text
.apm/bus/<agent-slug>/handoff.md
```

必须包含：

- outgoing 和 incoming instance number；
- Handoff Log 路径；
- 当前 Stage 中需要读取的该 Worker Task Logs；
- 当前任务状态和继续方式；
- 第一份 Task Report 必须声明 Handoff 状态；
- 要求新 Worker 先用中文确认已读取上下文，再继续或等待任务。

---

**命令结束**
