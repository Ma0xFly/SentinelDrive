# APM 1.0.1 - Task Assignment Guide

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

**Reading Agent:** Manager

本指南定义 Manager 如何构造 Task Prompt、管理分支和 worktree、通过 Message Bus 向 Worker 交付任务。

Task Prompt 必须自包含。Worker 不读取 `Spec`、`Plan`、`Tracker` 或 `Index`，所以 Manager 必须把相关信息提取进 Task Prompt。

---

## 0. 中文 Task Prompt 强制规则

Manager 写入 Task Bus 的 Task Prompt 必须使用中文正文。

- `## Task Reference`、`## Context from Dependencies`、`## Objective`、`## Detailed Instructions`、`## Workspace`、`## Expected Output`、`## Validation Criteria` 等结构标题可以保留英文，以保持 APM 格式兼容。
- 标题下面的任务目标、背景、依赖说明、执行步骤、验证标准、注意事项、失败处理和用户提示必须使用中文。
- 从 `Spec`、`Plan`、Task Log 或代码库提取信息时，如果来源是英文，必须翻译/改写成中文再写入 Task Prompt。
- 只有命令、路径、代码标识、YAML 字段、状态值、Agent 名称、Task ID、mermaid 语法和专有技术名词可以保留英文。

---

## 2. 派发标准

### 2.0 Manager 职责边界

Manager 负责运行时协调：判断 Ready Tasks、选择 single/batch/parallel、创建分支或 worktree、写 Task Prompt、维护 Tracker、merge 已完成分支。Manager 不默认亲自实现功能，也不把协调层文档直接暴露给 Worker。

Worker 只接收 Task Prompt、`AGENTS.md` 和执行过程中自己积累的上下文。Task Prompt 必须把当前任务需要的 Spec 决策、Plan Guidance、依赖产物、验证标准和工作区信息都提取出来。

### 2.1 依赖上下文

任务可能依赖前序任务输出。根据 Worker 熟悉程度决定上下文深度：

- **Same-agent dependency**：同一个 Worker 之前完成过相关任务。提供轻量回忆锚点、关键路径和集成提示。
- **Cross-agent dependency**：其他 Worker 完成的工作。提供完整上下文，包括读取文件、产物摘要、接口、约束和集成步骤。
- **Worker Handoff 后**：新 Worker 只加载当前 Stage 的 Task Logs。此前 Stage 中该 Worker 完成的任务，要按 cross-agent dependency 处理。

依赖识别以 `Plan` 中的 Dependencies 字段为准。跨 Agent 依赖在 `Plan` 中应加粗。

依赖上下文的深度按风险决定：同一 Worker 在当前实例内连续执行的 same-agent dependency 可以轻量；跨 Agent、Handoff 前任务、上一 Stage 任务、用户修正过的任务、审查中发现过风险的任务，都要给更完整上下文。依赖产物必须指向具体文件、接口、数据结构或行为变化，不要只写“参考上一任务”。

### 2.2 Task Prompt 内容

Task Prompt 中应该：

- 嵌入 Worker 不能从代码库直接发现的事实；
- 指向 Worker 应该读取的具体代码文件；
- 提供目标、步骤、输出和验证标准；
- 给出工作区、分支或 worktree 路径；
- 说明遇到指令和代码事实冲突时，以目标和代码实际状态为准。

Task Prompt 中不应该：

- 让 Worker “去看 Spec/Plan/Tracker”；
- 暴露协调层结构；
- 包含与当前任务无关的背景；
- 使用空泛指令，例如“实现好这个功能”。

### 2.3 派发模式

从 `Tracker` 判断 Ready Tasks：

- `Ready`：依赖完成，可以派发；
- `Active`：已经派发；
- `Done`：审查完成；
- `Waiting: <deps>`：依赖未完成。

派发模式：

- **Single**：一个 Worker 一个任务；
- **Batch**：同一 Worker 多个 Ready Tasks，顺序执行；
- **Parallel**：多个 Worker 同时执行，需要版本控制隔离。

并行派发前必须确认 Git 已初始化，并且能为每个 dispatch unit 创建独立分支或 worktree。

如果一个 pending report 可能解锁更好的 batch 或 parallel 组合，可以建议用户优先返回该 report；否则不要为了追求完美组合而阻塞 Ready Tasks。

### 2.4 版本控制

Manager 负责：

- 创建分支；
- 创建 worktree；
- 记录 branch 到 Tracker；
- 后续 merge 和 cleanup。

Worker 只负责在指定工作区工作并 commit。

分支名、worktree 名、commit message 不出现 APM、Task ID、Stage、Worker 等框架词，只描述真实代码变化。

依赖任务派发前，必须确认前序成功任务的分支已经按需要 merge 到目标基线。并行分支之间的隔离和后续 merge 是 Manager 职责。

### 2.5 Message Bus 交付

Planner 已创建 bus 文件。Manager 不重新创建 bus。

交付前：

1. 清空 Worker 的 Report Bus；
2. 读取 Worker 的 Task Bus；
3. 写入 Task Prompt 到：

   ```text
   .apm/bus/<agent-slug>/task.md
   ```

---

## 3. 派发流程

### 3.1 Dispatch Assessment

每次派发前，用中文向用户展示：

- 哪些 Tasks 是 Ready；
- 它们之间的依赖关系；
- 哪些可以 batch；
- 哪些可以 parallel；
- 你选择当前派发方式的理由。

然后执行：

1. 从 `Tracker` 找 Ready Tasks。
2. 按 Worker 分组。
3. 评估 single、batch、parallel。
4. 如果 pending report 会解锁更优组合，可以建议先等待该 report；否则立即派发。

### 3.2 Per-Task Analysis

对每个待派发 Task：

1. 读取 Task 的 Dependencies。
2. 判断 same-agent 或 cross-agent。
3. 对 cross-agent 依赖读取 producer Task Log，提取产物、文件、接口和集成要点。
4. 从 `Spec` 提取相关设计决策和约束。
5. 从 `Plan` 提取 Objective、Steps、Guidance、Output、Validation。
6. 把这些内容转换成 Worker 可直接执行的 Task Prompt。

### 3.3 Task Prompt 构造和交付

1. 写 YAML frontmatter。
2. 写正文。
3. 创建 feature branch；并行时创建 worktree。
4. 更新 `Tracker` 中 Task 的 Branch 列。
5. 清空 Report Bus。
6. 写入 Task Bus。
7. 指导用户切换到对应 Worker 会话。

写入 Task Bus 前先读取现有 Task Bus，确认不会覆盖未处理任务；清空 Report Bus 前确认上一份报告已处理。Tracker 更新、分支创建、bus 写入应在同一轮完成，避免状态和实际派发不一致。

如果 Worker 尚未初始化：

```text
/apm-3-initiate-worker <agent-id>
```

Codex CLI：

```text
$apm-3-initiate-worker <agent-id>
```

如果 Worker 已初始化：

```text
/apm-4-check-tasks
```

Codex CLI：

```text
$apm-4-check-tasks
```

### 3.4 Follow-Up Task Prompt

当审查结果需要 Worker 重试时，创建新的 follow-up prompt：

- 不复制原 prompt；
- 说明上次出了什么问题；
- 说明 Manager 调查后的结论；
- 给出更具体的目标、步骤和验证标准；
- 使用原来的 `log_path`，Worker 会覆盖旧 Task Log。

---

## 4. Task Prompt 格式

YAML frontmatter：

```yaml
---
stage: 1
task: 2
agent: frontend-agent
log_path: ".apm/memory/stage-01/task-01-02.log.md"
has_dependencies: true
---
```

正文建议结构：

```markdown
# Task <N>.<M>: <Title>

## Task Reference

## Context from Dependencies

## Objective

## Detailed Instructions

## Workspace

## Expected Output

## Validation Criteria

## Instruction Accuracy

目标和 Expected Output 是权威的。Detailed Instructions 来自规划文档，可能包含过期假设；如果和代码库事实冲突，先验证实际状态，再做最小必要调整。

## Task Iteration

验证失败时先调查根因，每轮只做一个针对性修复；反复失败时使用 debug subagent；仍无法解决时以 Partial 报告。

## Task Logging

完成后按 `.codex\apm-guides\task-logging.md` 写 Task Log 到 `log_path`。

## Task Report

完成后写 Task Report 到 Report Bus。
```

---

## 5. Batch Envelope

多个 Tasks 一次交给同一 Worker 时，Task Bus 使用：

```yaml
---
batch: true
batch_size: <N>
tasks:
  - stage: 1
    task: 1
    log_path: ".apm/memory/stage-01/task-01-01.log.md"
  - stage: 1
    task: 2
    log_path: ".apm/memory/stage-01/task-01-02.log.md"
---
```

正文中放多个完整 Task Prompts，用 `---` 分隔。

---

## 6. 常见错误

- 在 Task Prompt 中写“去看 Spec”；
- cross-agent 依赖上下文过浅；
- Worker Handoff 后仍把旧同 Agent 依赖当 same-agent；
- 派发依赖任务前忘记 merge 前序分支；
- 分支名和 commit message 使用 APM 内部词；
- 没检查 Tracker 就派发任务。
- Task Prompt 没把 Spec 决策翻译成 Worker 可执行的中文上下文；
- 只写步骤，不写通过/失败边界；
- batch 中多个任务共享一个模糊验证标准。

---

**Guide 结束**
