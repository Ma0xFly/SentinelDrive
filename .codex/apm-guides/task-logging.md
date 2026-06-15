# APM 1.0.1 - Task Logging Guide

## 0. 纯中文本土化执行规范

本文件是 APM 中文本土化版本。执行时必须遵守以下规则：

- 本文件的中文说明就是实际执行口径，不需要再参考英文原文。
- 面向用户的解释、提问、分析、总结、风险说明、审查意见和下一步指令必须使用中文。
- APM 项目产物正文必须使用中文，包括 `.apm/spec.md`、`.apm/plan.md`、`AGENTS.md` 中的 APM 规则、Task Prompt、Task Log、Task Report、Handoff Log、Recovery Summary、Stage Summary、Memory Notes 和 Working Notes。
- 可以保留英文的内容仅限命令、路径、代码标识、YAML 字段、Markdown 结构标题、状态值、Agent 名称、Task ID、mermaid 语法、协议字段、库名、框架名和行业通用缩写。
- 不得为了节省上下文而删除流程约束。必须保留审批门槛、上下文边界、依赖判定、验证标准、日志格式、Message Bus、Handoff、Recovery、Tracker 和 Memory 相关规则。
- 如果发现规则缺口，用中文补足；不要回退到英文说明。

---
## 1. 适用角色

**Reading Agent:** Worker

本指南定义 Worker 如何写 Task Log 和 Task Report。Task Log 保存任务级事实，Task Report 是给 Manager 的简短交付消息。

---

## 0. 中文日志和报告强制规则

Worker 写入的 Task Log 和 Task Report 必须使用中文正文。

- `## Summary`、`## Details`、`## Output`、`## Validation`、`## Issues`、`## Compatibility Concerns`、`## Important Findings` 等结构标题可以保留英文，以保持 APM 格式兼容。
- 标题下面的结果摘要、执行细节、文件变更说明、验证结果、问题、兼容性风险和重要发现必须使用中文。
- 如果验证命令输出、错误消息或代码片段是英文，可以原样引用；但必须在旁边用中文说明它代表什么、是否通过、还有什么风险。
- Task Report 的正文也必须中文，不能只写英文状态句。

---

## 2. 状态和标记

### 2.1 Outcome

`status` 只能使用：

- `Success`：目标达成，所有验证通过；
- `Partial`：有进展但未完成，需要指导；
- `Failed`：目标未达成，已尝试但无法解决。

不要因为“做了很多努力”就标记 `Success`。状态只看结果。

`Success` 必须同时满足：Objective 达成、Output 完整、所有自主 Validation 已执行并通过、需要用户参与的验收点已明确暂停或已获得反馈、没有未解释的阻塞。只完成部分交付物、测试未跑、验证不完整、或关键风险未解决时，不能标记 `Success`。

### 2.2 Flags

`important_findings`：

- 发现 Task Prompt 未覆盖的重要事实；
- 发现可能影响其他 Tasks 或 Workers 的风险；
- 发现依赖、约束、用户纠正或系统行为差异。

`compatibility_issues`：

- 输出与现有代码、接口、约定、依赖或运行环境冲突；
- 引入 breaking change 或迁移要求；
- 发现集成风险。

不确定时设为 `true`。误报比漏报更容易处理。

flags 不是失败标记，而是 Manager 注意力路由。`important_findings: true` 表示可能需要更新 Spec、Plan、Rules 或影响后续任务；`compatibility_issues: true` 表示可能需要集成判断、迁移处理或返工。

---

## 3. Task Log

位置由 Task Prompt 的 `log_path` 指定，通常为：

```text
.apm/memory/stage-<NN>/task-<NN>-<MM>.log.md
```

YAML frontmatter：

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

正文模板：

```markdown
# Task <N>.<M> - <Title>

## Summary

用 1-2 句话说明主要结果。

## Details

说明完成的工作、关键决策、执行步骤和使用的 subagent（如有）。

## Output

- 新增或修改的文件路径
- 配置变化
- 交付物
- 必要代码片段（尽量不超过 20 行）

## Validation

列出执行的测试、构建、检查命令和结果。

## Issues

列出阻塞、错误或未解决问题；没有则写 `None`。

## Compatibility Concerns

仅当 `compatibility_issues: true` 时包含。

## Important Findings

仅当 `important_findings: true` 时包含。
```

Task Log 的正文要让 Manager 不读完整聊天记录也能判断任务是否可接受。Validation 中必须写清楚命令、结果、失败修复过程和未执行项原因。Output 中必须列出关键文件路径和交付物，不要只写“已完成”。

---

## 4. Task Report

写入：

```text
.apm/bus/<agent-slug>/report.md
```

写入前先清空 incoming Task Bus：

```text
.apm/bus/<agent-slug>/task.md
```

YAML frontmatter：

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

正文用 1-2 句话总结结果，并引用 Task Log 路径。详细内容放 Task Log，不要塞进 Report。

Task Report 是触发 Manager 审查的信号，不是完整复盘。Report 必须准确反映 `status` 和 flags，不能为了简短省略 `important_findings` 或 `compatibility_issues`。

完成后提示用户回到 Manager 会话运行：

```text
/apm-5-check-reports <agent-id>
```

Codex CLI 使用：

```text
$apm-5-check-reports <agent-id>
```

---

## 5. Batch Report

Batch report 写入同一个 Report Bus。

YAML frontmatter：

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

正文包含：

```markdown
# Batch Report

## Summary

## Task Outcomes

### <Title>

**Status:** Success | Partial | Failed
**Task Log:** `<log_path>`
```

Batch 中每个 Task 都必须有独立 Task Log。某个 Task 失败导致 batch 提前停止时，未开始任务必须标记为 `"Not started"`，不要伪造成 Failed。

---

**Guide 结束**
