# APM 1.0.1 - 任务派发指南

## 1. 概述

**阅读本指南的 Agent：** Manager

本指南定义你如何为 Worker 构造和交付 Task Prompt、管理版本控制工作区隔离、以及协调基于 bus 的交付。Task Prompt 是自包含的——Worker 收到执行任务所需的一切，无需引用 Spec 或 Plan。

### 1.1 产物

- *Task Prompt：* 写入 Task Bus 供 Worker 接收的内容。
- *跟进 Task Prompt：* 审查结果判定需要重试时，经过细化后的提示。
- *Feature branch：* 每个派发单元一个分支，从 base branch 创建。
- *Worktree：* 位于 `.apm/worktrees/` 下的隔离工作目录，供并行派发使用。

---

## 2. 执行规范

### 2.1 依赖上下文标准

任务可能依赖先前任务的产物。你包含的上下文取决于 Worker 对生产者工作的熟悉程度。

**同 Agent 依赖：** Worker 之前完成过生产者任务、有工作熟悉度。提供轻量上下文——回忆锚点、关键文件路径、对先前工作的简短引用。细节随依赖复杂度增加而增加。

**跨 Agent 依赖：** 不同 Worker 完成了生产者任务。Worker 零熟悉度。提供完整上下文——明确的文件读取指令、产物摘要、整合指引。不做任何假设。

**Worker Handoff 之后：** 新 Worker 只加载当前 Stage 的 Task Logs。当前 Stage 的同 Agent 依赖仍按同 Agent 处理。上一 Stage 的同 Agent 依赖要重分类为跨 Agent，因为新 Worker 缺乏那段工作上下文。依赖分析时检查 Tracker 中的 cross-agent overrides，确定哪些任务已被重分类。

**依赖识别：** 检查 Plan 中任务的 Dependencies 字段。跨 Agent 依赖已加粗。「None」表示无依赖。

**链式推理：** 依赖可能有自己的依赖。当上游祖先建立了当前任务必须遵循的模式、schema 或契约时，向上追溯。当中间节点已完全抽象了先前内容时停止追溯。不确定某祖先是否相关时，宁可包含也不要遗漏关键上下文。

### 2.2 Task Prompt 内容标准

Task Prompt 必须自包含。Worker 与任何 agent 拥有相同工具，但被有意限定在 Task Prompt、Rules 和累积的工作上下文内，以保持聚焦执行。你通过把 Spec、Plan 和权威来源的相关内容提取进每个提示、而不是按路径引用那些文档，来执行这种限定。绝不按路径引用 Spec、Plan、Tracker 或 Index——Worker 不应读取它们。Task Prompt 的指令和目标不引用 Stage 编号、其他 Task ID 或协调层概念（依赖上下文章节按需以 ID 引用生产者任务）。Validation Criteria 是 Worker 范围域的。

**嵌入** Worker 无法仅从代码库发现的内容：Spec 中的设计决策和约束、Plan 中的任务定义和指引、Tracker 中任务相关的协调上下文、Index 中的观察、先前任务的修正发现、以及 Spec 引用的权威用户文档内容。用精确约束保留具体性，而不是摘要。把所有嵌入内容呈现为直接事实上下文。绝不把内容归因于其来源产物或使用协调层词汇——Worker 不应意识到 Spec、Plan、Tracker、Index 或 Memory——显露这些概念会破坏他们聚焦执行的边界。

**用读取指令引用**代码库中存在的内容：源文件、现有模式、配置。给 Worker 指出具体文件及要关注什么——Worker 直接从自己的工作区读取它们。这既适用于依赖上下文，也适用于引用代码库模式的 Spec 内容。Manager 识别哪些文件重要、关注什么，而不是嵌入其内容。

**排除**与其他领域相关的内容、无可行需求的背景、或已记录在任务 Guidance 字段的内容。

### 2.3 跟进标准

审查结果判定为调查后需要重试时，产生跟进 Task Prompt。你带着：原 Task Log 发现、调查结果、对出了什么问题的理解、以及可能已修改的规划文档。

**内容原则：** 跟进是新的提示——Objective、Instructions、Output、Validation 基于出了什么问题重新细化。不要复制之前的提示。Worker 在限定上下文中操作；你的跟进弥合 Worker 所见与你通过调查、其他任务完成和规划文档更新所了解之间的差距。给 Worker 具体方向，而不是复述原 Task Prompt。

**日志路径连续性：** 使用与原任务相同的 `log_path`。Worker 覆盖先前的日志。Manager 在相关时把迭代模式捕获进 Stage 摘要。

### 2.4 派发标准

构造单个 Task Prompt 前，评估各 Ready 任务的派发机会。

**任务就绪：** 当任务的所有依赖都 Done 时，任务为 Ready。读 Tracker 查当前状态；对刚解锁的任务交叉引用 Dependency Graph。

**派发模式。** 评估所有 Ready 任务，按 Worker 分组，形成派发单元：

- *Batch：* 同一 Worker 的多个 Ready 任务，一起派发。候选要么形成顺序链（每个只依赖前一个或已完成任务），要么是独立组（彼此无依赖、同时 Ready）。形成链时，权衡是否有外部任务依赖中间结果——若有，单独派发可更早审查、更快解锁下游 Worker。软性指导为每批 2-3 个任务。
- *Single：* 一个 Worker 一个 Ready 任务。
- *Parallel：* 两个及以上派发单元（任意组合）彼此之间无未解决的跨 Agent 依赖，同时派发。需要版本控制工作区隔离。

**并行派发前提：** 版本控制必须已初始化（在 Manager 1 初始化时按 `.agents/skills/apm-2-initiate-manager/SKILL.md` 第 2.1 节首次 Manager 初始化确立）。版本控制未激活时，回退为顺序派发。建议用户为 Worker 配置平台工具审批，以最小化并行执行时的交互等待时间。

派发一个就绪单元前，检查是否有 pending report 能解锁与当前单元组合良好的任务。若它是唯一待处理报告，等待成本低。若有多个报告待处理或没有合理组合，立即派发。

**等待状态：** 无 Ready 任务但仍有活跃 Worker 时，说明处理了什么、待处理什么、用户下一步该做什么。指引用户返回下一份报告——若某份 pending report 能解锁更好的派发组合，建议优先返回该报告。

### 2.5 版本控制标准

版本控制在并行派发期间提供工作区隔离。每个派发单元在自己的 feature branch 上工作，你在 Task Review 期间协调所有合并。Tracker 的 Version Control 表列出多个仓库时，从 Spec 的 Workspace 节识别每个任务在哪个仓库操作。用户最初拒绝版本控制但会话中途又要求时，初始化它：必要时运行 `git init`、检测或确认 base branch、与用户确立约定、更新 Rules 和 Tracker，然后继续按分支派发。

**分支标准：** 每个派发单元按 Tracker 中的分支约定从 base branch 创建自己的 feature branch。APM 术语（Task ID、Stage 编号、agent 标识）不出现在分支名、提交消息或 worktree 目录名中——它们反映实际工作，而不是管理它的框架。同一 Worker 的顺序任务批次共享一个分支。

**Worktree 标准：** Worktree 只为并行派发创建。每个并行派发单元有自己的 worktree，使所有并行 Worker 在隔离目录中工作，主工作目录保持在 base branch 上供合并操作。顺序派发时，Worker 在自己的 feature branch 上的主工作目录中操作。

- *布局：* Worktree 按第 4.3 节分支与 worktree 标准放在 `.apm/worktrees/` 下。
- *并发上限：* 最多 3-4 个并行 worktree。
- *生命周期：* 短命——派发前创建，合并后移除。

Worktree 只含已跟踪文件；若 Worker 需要未跟踪资产，在 Task Prompt 中注明。当 `.apm/` 被跟踪（或部分跟踪）时，worktree 可能含 `.apm/` 文件，但所有 APM 运行时操作（Task Logs、bus 通信）必须指向项目根的 `.apm/`，而非 worktree 副本。审查前你需要读取 Task Logs 和 bus 文件，所以它们必须能从主工作目录访问。把这条指引写进 worktree 派发的 Task Prompt Workspace 节。

### 2.6 交付标准

Bus 目录和文件由 Planner 在规划阶段创建——不要重新创建。给 Worker 的 Task Bus 写入前，先通过终端清空 Worker 的 Report Bus（`.apm/bus/<agent-slug>/report.md`，如 `truncate -s 0` 或 shell 重定向）。Worker 尚无报告存在时，首次 Task Prompt 跳过清空。按 `.agents/skills/apm-communication/SKILL.md` 第 4 节 Message Bus 协议，写入前先读 Task Bus。给同一 Worker 派发多个顺序任务时，按第 4.5 节批处理封装格式，在单条 Task Bus 消息中作为一批发送。

### 2.7 非 APM Agent 派发

当非 APM agent 加入会话、你需要给它派后续工作时，向它的 Task Bus 写一份普通任务说明——不是完整 Task Prompt。包含要做什么和要产出什么，并指示它回报。不要包含日志路径、日志指令或 Handoff 元数据——非 APM agent 不向 Memory 记日志，也不参与 Worker tracking。

---

## 3. 任务派发流程

先做派发评估，然后对派发计划中的每个任务做逐任务分析和提示构造。审查结果需要重试时，跟进提示走单独的构造路径。

### 3.1 派发评估

按第 2.4 节派发标准，从当前项目状态评估派发机会。每次派发决策前，在聊天中可见地评估当前项目状态，标题为 **Dispatch Assessment:**，覆盖哪些任务是 Ready、它们之间的依赖关系、以及哪种派发模式最利于进展和效率。每个派发周期都是一次全新评估。

执行以下动作：

1. 从 Tracker 识别 Ready 任务。交叉引用 Dependency Graph 找刚解锁任务。
2. 检查是否有 pending report 能解锁与当前 Ready 任务组合良好的任务。等待成本低则考虑，否则继续。
3. 按指定 Worker 分组 Ready 任务。按第 2.4 节派发标准形成派发单元——承诺派发计划前评估全部三种模式（single、batch、parallel）。
4. 评估并行机会：若存在 2+ 个无未解决跨 Agent 依赖的派发单元——并行派发。
5. 形成派发计划：哪些 Worker 收到哪些单元、是否并行。对每个任务，继续逐任务分析。

### 3.2 逐任务分析

对派发计划中的每个任务执行。

执行以下动作：

1. 从 Plan 读任务的 Dependencies 字段。「None」则跳过依赖上下文步骤。
2. 对每个依赖，按第 2.1 节依赖上下文标准确定上下文深度——检查 Tracker 中的 Worker Handoff 状态和 auto-compaction 备注，分类为同 Agent 或跨 Agent，检查 cross-agent overrides，祖先相关时向上追溯。对从 auto-compaction 恢复的 Worker，提供更完整的同 Agent 依赖上下文，因为重建的上下文可能缺乏工作细节。
3. 对跨 Agent 依赖，读唯一的生产者 Task Logs，记下关键产物、文件路径和整合细节。本派发周期多个任务依赖同一生产者时，读一次并从上下文提取供后续任务使用。
4. 按第 2.2 节 Task Prompt 内容标准提取与本任务相关的 Spec 内容。Spec 从会话开始就在上下文中，任何修改后刷新。新 Stage 首次派发开始时值得重读一次；对未变的 Spec 无需逐任务重读。
5. 从 Plan 提取任务定义字段：Objective、Steps、Guidance、Output、Validation。Guidance 引用 Spec 章节时，解析这些引用并按第 2.2 节内容标准提取被引内容。把 Steps 转化为可执行指令，纳入 Guidance 和相关 Spec 内容。

### 3.3 Task Prompt 构造

组装 Task Prompt 并经 Message Bus 交付。

执行以下动作：

1. 按第 4.1 节 Task Prompt 格式构造 YAML frontmatter。
2. 构造提示正文：Task Reference、Context from Dependencies（如适用）、Objective、Detailed Instructions、Workspace、Expected Output、Validation Criteria、Instruction Accuracy、Task Iteration、Task Logging 指令、Reporting Instructions。
3. 按第 2.5 节版本控制标准从仓库 base branch 创建 feature branch。并行派发时创建 worktree：`git worktree add .apm/worktrees/<branch-slug> -b <branch-name>`。Workspace 节包含分支名（顺序）或 worktree 路径（并行）。
4. 更新 Tracker 时，把分支名记入任务行的 Branch 列。
5. 按第 2.6 节交付标准清空 incoming Report Bus。
6. 读 Worker 的 Task Bus，然后写入 Task Prompt：`.apm/bus/<agent-slug>/task.md`。批处理用第 4.5 节批处理封装格式。
7. 按 `.agents/skills/apm-communication/SKILL.md` 第 2.1 节直接沟通，指引用户去 Worker 的会话：
   - Worker 尚未初始化——指引用户开新会话并运行 `/apm-3-initiate-worker <agent-id>`。Worker 在初始化时检测到待处理 Task Prompt 并开始执行。仅首次派发到该 Worker。
   - Worker 已初始化——指引用户在 Worker 会话运行 `/apm-4-check-tasks`。
   - 批处理派发——总结 Worker 将收到什么（任务数量、顺序执行）。
   - 并行派发——列出每个 Worker 及其所需动作。

### 3.4 跟进 Task Prompt 构造

审查结果（按 `.codex/apm-guides/task-review.md` 第 3.3 节审查结果）判定需要跟进时执行。

执行以下动作：

1. 捕获跟进上下文：出了什么问题、调查发现、所需细化、任何规划文档修改。
2. 规划文档已改时，按第 3.2 节逐任务分析提取相关的更新内容。
3. 按第 2.3 节跟进标准细化所有内容节。含一个跟进上下文章节，说明问题和所需细化。
4. 按第 4.2 节跟进格式构造跟进提示。与原任务同 `log_path`。
5. 按第 2.6 节交付标准清空 incoming Report Bus。
6. 读 Worker 的 Task Bus，然后写入：`.apm/bus/<agent-slug>/task.md`。
7. 按第 3.3 节 Task Prompt 构造步骤 7 指引用户去 Worker。

---

## 4. 结构规范

### 4.1 Task Prompt 格式

Task Prompt 是 Markdown 文件。按任务需要调整——不是每个任务都需要所有节。

**YAML Frontmatter Schema:**

```yaml
---
stage: 1
task: 2
agent: frontend-agent
log_path: ".apm/memory/stage-01/task-01-02.log.md"
has_dependencies: true
---
```

**字段说明：**

- `stage`：Stage 编号。
- `task`：Stage 内的任务编号。
- `agent`：Worker 标识（kebab-case）。
- `log_path`：预构造的 Task Log 路径。路径模式：`.apm/memory/stage-<NN>/task-<NN>-<MM>.log.md`（相对于项目根）。同一 Stage 的所有任务共享同一 Stage 目录。你构造路径；Worker 直接写入。
- `has_dependencies`：是否存在依赖上下文。

**提示正文节：**

- *Title.* 用 Task ID 和标题做 `#` 标题。各节用 `##` 标题：
- *Task Reference:* Task ID 和指定 agent。
- *Context from Dependencies.* `has_dependencies: true` 时包含。格式按第 2.1 节依赖上下文标准取决于依赖类型。
  - *同 Agent.* 「Building on your previous work:」开头——`**From Task <N>.<M>:**` 带关键产物和回忆点——`**Integration Approach:**` 带简短指引。
  - *跨 Agent.* 「This Task depends on work completed by [Producer Agent]:」开头——`**Integration Steps:**` 编号的文件读取指令——`**Producer Output Summary:**` 关键功能、文件、接口、约束——`**Upstream Context:**` 用于相关祖先。
- *Objective:* 单句任务目标，可选以协调层上下文增强。
- *Detailed Instructions:* Plan 步骤转化为可执行指令，整合 Spec 内容和指引。
- *Workspace:* 顺序派发的工目录和分支名，或并行派发的 worktree 路径和项目根。worktree 派发时，指示 Worker 在 worktree 做代码工作，但从项目根解析所有 `.apm/` 路径（Task Log、bus 文件）。Worker 在指定工作区操作、在那里提交，并在 Task Log 注明。Worker 不 merge。
- *Expected Output:* 来自 Plan Output 字段的交付物。
- *Validation Criteria:* 来自 Plan Validation 字段。
- *Instruction Accuracy:* 目标和 Expected Output 是权威的——交付它们。但详细指令和步骤是从规划文档构造的，可能包含不准确细节、遗漏前提或过时的代码库假设。当某条具体指令与代码库实际状态矛盾时，验证实际状态，而不是坚持按指令执行。
- *Task Iteration:* 验证失败时先调查再修复——读错误输出、追溯原因、理解出了什么问题。每轮应用一个针对性改动。修复未解决问题时，派发 debugging subagent 并给结构化指令：错误输出、你调查和尝试了什么、相关文件路径、预期 vs 实际行为。指示它追根因并提出修复。应用前验证 subagent 的发现。根因可能来自多个独立区域时，并行派发多个 subagent。subagent 调查后仍未解决，以 Partial 状态报告。
- *Task Logging:* 路径和引用 `.codex/apm-guides/task-logging.md` 第 3.1 节任务日志流程。
- *Task Report:* 告知输出 Task Report 供用户返回给 Manager。

### 4.2 跟进格式

跟进 Task Prompt 使用与第 4.1 节相同的结构，做如下修改：

- *Title:* `APM Follow-Up Task: <Task Title>`
- *Task Reference 之后有跟进上下文章节*——先前问题、调查发现、所需细化、额外指引。
- *所有内容节*基于出了什么问题细化，而不是从上次尝试复制。
- *与原 Task Prompt 同 `log_path`。*

### 4.3 分支与 worktree 标准

分支命名遵循 Tracker Version Control 表记录的约定。分支名描述实际工作；批处理时，名称反映批范围。Worktree 放在 `.apm/worktrees/` 下。每个子目录名从分支名派生（如把 `/` 换成 `-`）。每个 worktree 目录含所有已跟踪文件的完整检出。未跟踪文件不存在。

### 4.4 Tracker VC 条目格式

VC 配置记录在 Tracker 的 Version Control 表，每个仓库一行。分支状态在任务表的 Branch 列逐任务跟踪——新 Manager 读任务行重建工作 VC 上下文。

**格式：**

```markdown
## Version Control

| Repository | Base Branch | Branch Convention | Commit Convention |
|-----------|-------------|-------------------|-------------------|
| <repo-name> | <branch-name> | <convention> | <convention> |
```

### 4.5 批处理封装格式

给 Worker 批量发送多个任务时，Task Bus 文件用此结构：

**YAML Frontmatter Schema:**

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

**字段说明：**

- `batch`：批处理封装恒为 `true`。
- `batch_size`：批内任务总数。
- `tasks[].stage`：Stage 编号。
- `tasks[].task`：Stage 内任务编号。
- `tasks[].log_path`：预构造的 Task Log 路径，遵循与单个 Task Prompt 相同的模式。

**正文：** 单个 Task Prompt 由 `---` 分隔符隔开。每个 Task Prompt 保留其完整结构（YAML frontmatter 和正文），如同独立存在。

---

## 5. 常见错误

- *Task Prompt 里的规划文档路径：* Worker 被限定在 Task Prompt 和 Rules——Spec 和 Plan 不在他们的上下文中。写「看 Spec」或「查 Plan」破坏自包含性。改为提取并嵌入相关内容。
- *跨 Agent 上下文过浅：* 跨 Agent 依赖无论看起来多简单都需要完整上下文。Worker 不与 Memory 交互、也无法访问其他 Worker 的工作——他们收到的唯一跨 Agent 上下文就是你在 Task Prompt 里嵌入的内容。
- *Handoff 后依赖分类陈旧：* 检测到 Worker Handoff 时，上一 Stage 的同 Agent 依赖必须重分类为跨 Agent。构造依赖上下文前检查 Tracker 的 cross-agent overrides。
- *依赖链过浅：* 任务的直接依赖可能又依赖更早建立了模式、schema 或契约的工作。向上追溯，直到中间节点完全抽象了先前内容。
- *指令含糊：* 「把功能实现好」vs「实现 POST /api/users，用 express-validator 做邮箱校验，成功返回 201」。
- *merge 依赖前就派发：* 任务 B 依赖任务 A 的产物、且 A 在独立分支上时，必须先 merge A 再创建 B 的分支。
- *假设 base branch 名：* 从 Tracker 的 Version Control 表读相关仓库的 base branch。不要假设 `main` 或 `master`。
- *Handoff 时忘记 VC 状态：* Handoff 前确保任务行反映当前分支状态。Handoff Log 中包含活跃分支、worktree 和待处理合并。
- *提交构建产物：* 不提交生成文件。为构建目录创建或更新 `.gitignore`。

---

**指南结束**
