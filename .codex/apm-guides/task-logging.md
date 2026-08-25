# APM 1.0.1 - 任务日志指南

## 1. 概述

**阅读本指南的 Agent：** Worker

本指南定义你如何记录任务结果和报告结果。Task Log 用结构化 Markdown 文件捕获任务级上下文，使 Manager 无需解析原始代码或聊天历史就能追踪进度和做审查决策。

### 1.1 产物

- *Task Log：* 位于 `.apm/memory/stage-<NN>/task-<NN>-<MM>.log.md` 的结构化日志，捕获结果、验证、交付物和标志。
- *Task Report：* 写入 Report Bus 供 Manager 处理的简明摘要。

---

## 2. 执行规范

### 2.1 标志评估标准

YAML frontmatter 里的布尔标志表示需要 Manager 注意的条件。基于执行中你观察到的、相对 Task Prompt 和工作上下文的情况来设置标志。

**`important_findings`：** 当执行揭示了 Task Prompt 之外、看似与项目相关的信息；你发现了 Task Prompt 未考虑的依赖、风险或约束；或某事暗示其他任务或 agent 可能受影响时，设为 `true`。

**`compatibility_issues`：** 当你的产出与你触及的现有代码、模式或约定冲突；你发现了可能影响系统其他部分的整合顾虑；或你的工作带来 breaking change 或迁移需求时，设为 `true`。

**默认：** 不确定某发现是否值得设标志时，设为 `true`。漏报比误报更伤协调。

### 2.2 结果标准

状态反映目标是否达成。基于最终状态选择，而非付出多少努力。

- *Success:* 目标达成，所有验证通过。
- *Partial:* 有进展但不完整；你需要指导才能继续。
- *Failed:* 目标未达成；你尝试了但无法解决。

以下情况用 Partial：验证含糊、出现了可能影响其他任务的重要发现、迭代停滞且失败反复、或方案不确定性取决于你范围之外的因素。验证失败但原因清晰且可修、无需 Manager 知晓、且正在取得进展时，继续迭代（先不记日志）。

### 2.3 详细程度标准

Task Log 服务于 Manager 的协调需求，而非存档文档。问：这个细节能帮 Manager 理解完成了什么吗？会影响 Manager 的下一次审查决策吗？直接读被引用的产物能找到它吗？

**默认：** 相比冗长的内联内容，更倾向简洁但全面的摘要加产物引用。按路径引用产物，而非包含大段代码块。只对新颖、复杂或关键逻辑包含代码片段（20 行以内）。对错误消息，包含相关堆栈跟踪或诊断细节。

---

## 3. 任务日志流程

任务完成后两个顺序步骤：写 Task Log，然后经 bus 交付 Task Report。按 `.codex/apm-guides/task-execution.md` 第 3.6 节任务完成之后执行。

### 3.1 Task Log 流程

任务执行后，在 Task Prompt 提供的路径（`log_path`）填入 Task Log。

执行以下动作：

1. 从聊天中已呈现的完成评估（按 `.codex/apm-guides/task-execution.md` 第 3.6 节任务完成）确定 Task Log 要捕获什么。
2. 完成 YAML frontmatter 字段：
   - 按第 2.2 节结果标准设 `status`。
   - 按第 2.1 节标志评估标准设 `important_findings` 和 `compatibility_issues`。
   - 从 Task Prompt 取 `stage`、`task`、`title` 和 `agent`。
3. 按第 4.1 节 Task Log 格式完成 Markdown 正文章节。始终包含：Summary、Details、Output、Validation、Issues。仅当对应标志为 `true` 时包含条件章节（Compatibility Concerns、Important Findings）。
4. 把 Task Log 写到 `log_path`。

### 3.2 Task Report 交付

执行以下动作：

1. 清空 incoming Task Bus：通过终端截断 `.apm/bus/<agent-slug>/task.md`（如 `truncate -s 0` 或 shell 重定向）。
2. 读 Report Bus，然后写入 Task Report：`.apm/bus/<agent-slug>/report.md`。报告是简明摘要——关键结果、状态、日志路径和任何标志。细节放 Task Log。
3. 按 `.agents/skills/apm-communication/SKILL.md` 第 2.1 节直接沟通，指引用户把报告交付给 Manager——给 `/apm-5-check-reports <agent-id>` 做定向检索，也给 `/apm-5-check-reports` 作为通用命令，因为多个 Worker 可能并发完成。

批处理执行时，完成所有任务（或因失败停止）后，按第 4.3 节批处理报告格式写一份批处理报告。

---

## 4. 结构规范

### 4.1 Task Log 格式

**位置：** `.apm/memory/stage-<NN>/task-<NN>-<MM>.log.md`

**命名约定：**

- `<NN>`：Stage 编号，零填充（如 01、02）。
- `<MM>`：Stage 内任务编号，零填充（如 01、02）。

**YAML Frontmatter Schema:**

```yaml
---
stage: <N>
task: <M>
title: <Task title from Plan>
agent: <agent-slug>
status: Success | Partial | Failed
important_findings: true | false
compatibility_issues: true | false
---
```

**字段说明：**

- `stage`：Task Prompt 中的 Stage 编号。
- `task`：Task Prompt 中的任务编号。
- `title`：Task Prompt 中的任务标题。
- `agent`：你的 agent 标识。
- `status`：按第 2.2 节结果标准的任务结果。`Success`、`Partial` 或 `Failed`。
- `important_findings`：发现是否对当前任务范围之外有影响（按第 2.1 节）。
- `compatibility_issues`：产出是否与现有系统冲突（按第 2.1 节）。

**Markdown 正文模板：**

```markdown
# Task <N>.<M> - <Title>

## Summary
[1-2 sentences describing main outcome]

## Details
[Work performed, decisions made, steps taken in logical order. Note subagent usage when applicable.]

## Output
- File paths for created/modified files
- Code snippets (if necessary, ≤20 lines)
- Configuration changes
- Results or deliverables

## Validation
[Description of validation performed and result]

## Issues
[Specific blockers or errors encountered, or "None"]

## Compatibility Concerns
[Only include if compatibility_issues: true]
[Description of compatibility issues identified]

## Important Findings
[Only include if important_findings: true]
[Project-relevant discoveries that Manager must know]
```

### 4.2 Task Report 格式

Task Report 是写入 Report Bus 供 Manager 处理的简明摘要。细节放 Task Log——报告提供足够信息让 Manager 评估结果并定位日志。

**位置：** `.apm/bus/<agent-slug>/report.md`

**YAML Frontmatter Schema:**

```yaml
---
stage: <N>
task: <M>
agent: <agent-slug>
status: Success | Partial | Failed
log_path: ".apm/memory/stage-<NN>/task-<NN>-<MM>.log.md"
important_findings: true | false
compatibility_issues: true | false
---
```

**字段说明：**

- `stage`：Task Prompt 中的 Stage 编号。
- `task`：Task Prompt 中的任务编号。
- `agent`：你的 agent 标识。
- `status`：按第 2.2 节结果标准的任务结果。
- `log_path`：本任务 Task Log 的路径。
- `important_findings`：与 Task Log 相同的值。
- `compatibility_issues`：与 Task Log 相同的值。

**Markdown 正文：** 1-2 句话总结结果。细节引用 Task Log。

批处理报告改用第 4.3 节批处理报告格式。

### 4.3 批处理报告格式

完成一批任务（或因失败提前停止）时，Report Bus 文件用此结构。

**位置：** `.apm/bus/<agent-slug>/report.md`

**YAML Frontmatter Schema:**

```yaml
---
batch: true
batch_size: <N>
completed: <M>
stopped_early: true | false
tasks:
  - stage: 1
    task: 1
    status: Success
  - stage: 1
    task: 2
    status: Failed
  - stage: 1
    task: 3
    status: "Not started"
---
```

**字段说明：**

- `batch`：批处理报告恒为 `true`。
- `batch_size`：批内任务总数。
- `completed`：已执行的任务（不含未开始）。
- `stopped_early`：批是否在完成所有任务前停止。
- `tasks[].stage`：Stage 编号。
- `tasks[].task`：Stage 内任务编号。
- `tasks[].status`：`Success`、`Partial`、`Failed`，未执行任务为 `"Not started"`。

**Markdown 正文模板：**

```markdown
# Batch Report

## Summary
[Brief overview: X of Y Tasks completed, stopped early if applicable]

## Task Outcomes

### <Title>
**Status:** [Success | Partial | Failed]
**Task Log:** `<log_path>`
[1-2 sentence summary of outcome]

...

## Batch Notes
[Any cross-cutting observations, patterns, or issues affecting multiple Tasks]
```

批因 Failed 任务提前停止时，指明是哪个任务触发停止，把剩余任务列为「Not started (batch stopped)」。

---

## 5. 内容指南

### 5.1 好日志 vs 差日志

- *Summary:* 「改了些东西、修了些问题」→「实现了 POST /api/users 并带校验。所有测试通过。」
- *Details:* 「我做了这个端点，有些问题」→「加了注册路由，用 express-validator 做邮箱/密码校验」
- *Output:* 「改了几个文件」→「修改：`routes/users.js`、`server.js`」
- *Validation:* 「现在能用了」→「测试套件：5/5 通过。手动测试确认预期响应。」

### 5.2 常见错误

- *忘记条件章节：* 标志为 `true` 时，必须包含对应章节（Compatibility Concerns、Important Findings）。
- *缺少产物引用：* 产出交付物时，在 Output 节列出文件路径。
- *推迟批处理日志：* 批处理执行时，完成每个任务后立刻写 Task Log——开始下一个之前。把全部日志推迟到批末尾，若中途发生自动压缩，有上下文丢失风险。

---

**指南结束**
