# APM 1.0.1 - Work Breakdown Guide

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

**Reading Agent:** Planner

本指南定义 Planner 如何把已批准的理解摘要转换为 3 份规划产物：

- `Spec`：定义要构建什么；
- `Plan`：定义工作如何组织；
- `AGENTS.md`：定义所有 Agent 如何执行工作。

每份文档都必须先展示分析，再写入文件，然后等待用户批准。

---

## 0. 中文产物强制规则

Planner 生成的 `.apm/spec.md`、`.apm/plan.md` 和 `AGENTS.md` 必须以中文正文为主。

- `# APM Spec`、`## Overview`、`## Workspace`、`# APM Plan`、`## Workers`、`## Stages`、`## Dependency Graph` 等 APM 结构标题可以保留英文，以保证 Manager 后续定位章节。
- 这些结构标题下面的说明、设计决策、范围、需求、约束、Task Objective、Output、Validation、Guidance、Steps、Notes 和 Rules 内容必须使用中文。
- 可以保留英文的内容仅限命令、路径、代码标识、YAML 字段、状态值、Agent 名称、Task ID、mermaid 语法和库/框架专有名词。
- 不得直接把后文英文原版模板中的说明性句子复制到项目产物正文里；需要引用流程细节时，先理解后用中文重写。

---

## 2. 文档职责

### 2.0 工作流上下文

Planner 产出的 3 份文档服务于不同读者：

- `Spec` 给 Manager 抽取设计决策，用于构造每个 Task Prompt。
- `Plan` 给 Manager 协调派发、追踪进度、构造 Task Prompt。
- `AGENTS.md` 会被 Worker 直接读取，必须自包含。

Worker 不读取 `Spec`、`Plan`、`Tracker` 或 `Memory Index`。任何 Worker 需要知道的内容，要么由 Manager 从 `Spec`/`Plan` 抽取进 Task Prompt，要么直接写入 `AGENTS.md`。因此，Planner 放错位置会直接导致 Worker 上下文缺失。

给 Manager 的观察备注使用 `> **Notes:** ...`，但备注只能帮助 Manager 判断，不能替代正文规则。项目环境、仓库状态、用户偏好写入 Spec notes；任务边界、关键路径、并行机会、整体验证建议写入 Plan notes。

### 2.1 Spec

`Spec` 记录项目级事实：

- 需求和范围；
- 设计决策；
- 技术约束；
- 业务规则；
- 工作区结构；
- 权威材料；
- 验收标准。

Manager 会读取 `Spec`，再把相关内容提取进 Task Prompt。Worker 不直接读取 `Spec`。

放入 `Spec` 的内容应是影响整个项目或多个任务的设计决策：做什么、为什么这样做、有哪些约束、哪些需求已有权威来源。单个任务的实现细节放入 Plan 的 Guidance；所有或大多数 Worker 都要遵守的执行方式放入 Rules。

### 2.2 Plan

`Plan` 记录工作组织方式：

- Workers；
- Stages；
- Tasks；
- 依赖关系；
- 每个 Task 的 Objective、Output、Validation、Guidance 和 Steps；
- Dependency Graph。

Manager 用 `Plan` 派发任务。Worker 不直接读取 `Plan`。

Plan 中每个 Task 必须足够让 Manager 构造自包含 Task Prompt：目标、交付物、验收标准、实现指导、依赖和步骤都要清楚。设计决策已经在 `Spec` 中时，Plan 的 Guidance 可以引用 Spec 章节，不要重复改写同一决策，避免后续分叉。

### 2.3 Rules

`AGENTS.md` 记录所有 Worker 都要遵守的执行规则。

Rules 必须自包含，不能写“参考 Spec”或“参考 Plan”。因为 Worker 会直接读取 Rules，但不会读取协调层文档。

Rules 只写执行方式，不写“要构建什么”。输出格式、接口契约、业务状态值、数据 schema 属于 Spec 或 Task Guidance；编码纪律、测试要求、提交习惯、错误处理习惯等通用执行模式才属于 Rules。

---

## 3. 拆解原则

### 3.1 Domains

按专业领域或心智模型划分，例如 frontend、backend、data、QA、infra。

领域不同且上下文差异大时拆开；领域强耦合且分开会增加误解时合并。

### 3.2 Stages

Stage 是顺序里程碑。Stage N+1 默认在 Stage N 完成后开始。

并行发生在同一个 Stage 内的不同 Tasks，而不是多个 Stage 并行。

### 3.3 Tasks

每个 Task 应该：

- 属于一个 Worker；
- 产生明确交付物；
- 可以独立验证；
- 有清晰依赖；
- 不跨越过多领域；
- 不包含无关重构。

如果一个 Task 需要独立验收多个结果，考虑拆分。如果拆得太碎只会增加协调成本，考虑合并。

### 3.4 Validation

每个 Task 都必须有具体可执行验收标准：

- 测试命令；
- 构建或 lint；
- 文件和产物检查；
- 行为验证；
- 需要用户参与的审查点。

不要写“质量良好”“实现正确”这种不可执行标准。

Validation 必须是 Worker 范围内可判断的通过/失败条件。需要用户审美判断、外部平台确认、账号权限或线上环境验证的内容，要明确写成“需要用户参与”的验收点。跨任务、跨 Stage 的整体验证由 Manager 运行时判断，不要伪装成单个 Worker Task 的验收标准。

### 3.5 依赖和并行

依赖只记录直接依赖，不画传递闭包。跨 Agent 依赖必须在 `Dependencies` 中加粗，并在 Dependency Graph 中用虚线；同 Agent 依赖用普通文本和实线。并行发生在同一 Stage 内的不同 Ready Tasks，不要设计“并行 Stage”。

---

## 4. Spec 生成

先在聊天中输出：

```markdown
**Spec Analysis:**
```

分析：

- 项目目标；
- 关键需求；
- 范围和非范围；
- 设计决策和约束；
- 权威材料；
- 工作区结构；
- 哪些内容属于 Spec，哪些属于 Plan 或 Rules。

然后读取 `.apm/spec.md`，写入完整 Spec。YAML frontmatter：

```yaml
---
title: <project name>
modified: Spec creation by the Planner.
---
```

写完后暂停，请用户审查。用户批准后才能进入 Plan。

---

## 5. Plan 生成

先在聊天中输出：

```markdown
**Plan Analysis:**
```

必须覆盖：

- **Domain Analysis:** 领域划分和 Worker 名称；
- **Stage Structure:** Stage 顺序和每个 Stage 交付物；
- **Stage N:** 每个 Stage 的 Tasks；
- **Dependency Analysis:** 依赖审计，特别是 cross-agent dependencies；
- **Pre-write Checks:** Task 是否粒度合适、验证是否明确、Worker 分配是否合理。

每个 Stage 分析时，先说明该 Stage 的交付物，再解释这些交付物为什么拆成当前 Tasks。不要直接列任务清单。每个 Task 都必须覆盖 Worker 分配、任务范围、Guidance、Validation、Dependencies 和 Steps。分析完成后做依赖审计，逐项确认 same-agent 与 cross-agent 分类是否正确。

然后读取 `.apm/plan.md`，写入完整 Plan。YAML frontmatter：

```yaml
---
title: <project name>
modified: Plan creation by the Planner.
---
```

Plan 格式：

```markdown
# APM Plan

## Workers

| Worker | Domain | Description |
|--------|--------|-------------|

## Stages

| Stage | Name | Tasks | Agents |
|-------|------|-------|--------|

## Dependency Graph

```mermaid
graph TB
```

---

> **Notes:** 给 Manager 的工作结构观察。

## Stage 1: <Name>

### Task 1.1: <Title> - <Domain> Agent

* **Objective:** ...
* **Output:** ...
* **Validation:** ...
* **Guidance:** ...
* **Dependencies:** None

1. ...
2. ...
```

跨 Agent 依赖必须加粗，例如：

```markdown
* **Dependencies:** **Task 1.2 by Backend Agent**
```

写完后暂停，请用户审查。用户批准后才能进入 Rules。

---

## 6. Rules 生成

先在聊天中输出：

```markdown
**Rules Analysis:**
```

分析：

- 哪些规则适用于所有或大多数 Tasks；
- 哪些只是 Task-specific guidance，不应进入 Rules；
- 现有 `AGENTS.md` 中哪些内容需要保留或引用；
- 是否存在用户特别强调的执行纪律。

然后读取或创建 `AGENTS.md`，写入 APM_RULES block。

建议格式：

```markdown
<!-- APM_RULES_START -->

## APM Rules

### 通用执行规则

- ...

### 测试和验证

- ...

### 版本控制

- ...

<!-- APM_RULES_END -->
```

如果 `AGENTS.md` 已有内容，保留 APM_RULES block 外的所有内容。

写完后暂停，请用户审查。用户批准后，声明 Work Breakdown 完成，并回到 Planner 启动命令中的规划阶段完成步骤。

---

## 7. 常见错误

- Spec 写成任务列表；
- Plan 缺少验证标准；
- Worker 过多导致协调成本过高；
- Task 跨多个领域；
- Rules 引用 Spec 或 Plan；
- 没有让用户逐份批准；
- Dependency Graph 和 Task Dependencies 不一致。

---

**Guide 结束**
