# APM 1.0.1 - 任务审查指南

## 1. 概述

**阅读本指南的 Agent：** Manager

本指南定义你如何审查任务结果、确定审查结果、在发现值得改时修改规划文档、以及维护 Tracker。

### 1.1 产物

- *Stage 摘要：* 每个 Stage 完成后追加到 Index。
- *更新的 Tracker：* 每个审查周期后更新，反映任务状态变化、就绪变化、合并状态和协调上下文。
- *修改的规划文档：* 发现值得改时——更新 Spec、Plan 或 Rules。

---

## 2. 执行规范

### 2.1 Task Log 审查标准

提取下一次审查决策所需的信息。

**状态解读：** 评估状态和标志是否与日志正文一致——不一致是幻觉指标。状态值是 Success（目标达成、所有验证通过）、Partial（有进展、需指导）、Failed（目标未达成）。

**标志解读。** Worker 基于限定观察设置标志。以完整项目意识解读：

- `important_findings: true`——Worker 观察到了可能超出任务范围的东西。评估它是否影响规划文档或其他任务。发现表明 Task Prompt 的验证标准未被充分执行时，标记 Done 前需要调查。重要发现也可能含用户修正作为潜在 Rules 条目——评估是否按第 2.3 节规划文档修改标准补充 Rules。
- `compatibility_issues: true`——Worker 观察到与现有系统冲突。评估它是否表明 Plan、Spec 或 Rules 问题。

**内容审查：** 除标志和状态外，审查日志正文各节（Summary、Details、Output、Validation、Issues），理解发生了什么、为审查结果提供信息。发现与 Spec、Plan 或 Rules 内容矛盾时——事实不准确、假设错误、描述过时——无论 Worker 是否处理了该差异，都把受影响文档视为需要按第 3.4 节规划文档修改来纠正。

### 2.2 审查结果标准

审查 Task Log 后，确定审查结果。

**审查日志：** 一切良好——Success 状态、无标志、日志正文支持状态——继续任务追踪更新。有需要关注的点——标志被触发、非 Success 状态、或不一致——先调查再继续。

**调查范围：** 范围受限的检查直接调查；上下文密集的问题用 subagent。范围不明时，倾向用 subagent 以保留 Manager 上下文。当 subagent 返回发现时，在采取行动前先读它引用的关键文件核实关键断言。派发探索 subagent——它在独立上下文窗口中运行并返回汇总发现：`spawn_agent(agent_type="explorer", message="...")`。

**调查后的结果：**

- 未发现（误报、无可行动项），继续下一个任务。
- Worker 需要带细化指令重试，按 `.codex/apm-guides/task-assignment.md` 第 3.4 节跟进 Task Prompt 构造创建跟进 Task Prompt。Worker 还留下未提交改动时，在跟进指令中注明。
- 规划文档需要修改，进入第 3.4 节规划文档修改。
- 调查发现先前已 Done 的工作有缺陷，按第 2.3 节规划文档修改标准经 Plan 修改创建新任务。原任务保持 Done；在新任务中引用它，包含发现上下文，并指明需纠正什么。

小的封闭动作（孤立问题的跟进、小的规划文档纠正）可在审查周期内立即执行——行动后向用户呈现发现以知情。当改动大到影响项目方向或范围时，按第 2.3 节规划文档修改标准暂停求用户批准。

### 2.3 规划文档修改标准

**级联推理：** Spec 和 Plan 双向影响——一方的变化可能需要另一方调整。Rules 一般独立。修改任何文档前评估级联影响。区分设计意图内的执行调整（无级联）与被证伪的设计假设（应级联）。不确定时，评估相关文档，而非假设独立。

**修改权限：** 小的封闭改动属 Manager 权限（单个任务澄清或纠正、补充遗漏依赖、孤立的 Spec 添加、小的 Rules 调整）。重大改动需用户协作（多个任务受影响、设计方向变化、范围扩大或缩小、新增 Stage 或大规模重构）。多个小改动叠加成重大改动时需用户协作。权限不明时，倾向用户协作。

### 2.4 并行协调标准

多个 Worker 同时活跃时，异步协调。

**即时再评估：** 处理每份报告后，再评估就绪，并在同一轮继续派发评估——审查和下一次派发在单次响应中完成，不等用户输入。唯一暂停的理由是：无 Ready 任务（等待状态）或按第 2.2 节审查结果标准某修改需要用户协作。

**异步报告处理：** 报告任意顺序到达。逐份处理——完成审查、必要时 merge、再评估就绪、派发新就绪任务。每个报告到派发的循环是连续的。

**合并协调：** 并行派发期间成功审查后，按第 2.5 节合并标准在派发依赖任务前先 merge 完成任务的 branch。Stage 结束时，按第 2.5 节执行合并清扫。

**等待状态：** 无 Ready 任务但有活跃 Worker 时，说明处理了什么、待处理什么、用户下一步该返回哪份报告。某份 pending report 能解锁更好的派发组合（按 `.codex/apm-guides/task-assignment.md` 第 2.4 节派发标准）时，建议用户优先返回该报告。

### 2.5 合并标准

合并状态是派发前提。在特定协调点把完成的 feature branch 合并进 base branch。

**合并时机：** 成功 Task Review 后合并完成分支。依赖派发前，若依赖任务需要已完成任务的产物，先合并。Stage 结束时，所有当前 Stage feature branch 必须合并。

**合并执行：** 干净合并无需用户介入。自主执行合并——切到 base branch（`git checkout <base-branch>`）、合并完成分支（`git merge <branch-name>`）、然后验证。

**冲突解决：** 用协调层上下文解决——两个任务的目标、项目设计和 Spec。对复杂冲突，派发 debugging subagent 或上报用户。

**分支保护适配：** base branch 有保护规则阻止直接合并时，适配（创建 PR、合并进中间分支，或询问用户）。被动发现并记入 working notes。

**清理：** 成功合并后，按顺序清理——先移除 worktree（如存在，`git worktree remove .apm/worktrees/<branch-slug>`），再删除已合并的 feature branch（`git branch -d <branch-name>`）。分支被 worktree 引用时无法删除。Stage 结束的合并清扫有多个分支时，先批量移除所有 worktree、再删除所有分支，在单次终端调用中完成。

### 2.6 Stage 摘要标准

Stage 摘要是 Stage 中发生什么的历史记录——写给未来的新 Manager 实例（Handoff 之后）和项目复盘。它捕获 Stage 的协调历史，并在蒸馏时吸收 working notes 里的 Stage 特化观察。写成描述性散文，覆盖结果、涉及的 agent、值得注意的发现、模式和关键决策——相关处指向 commit。实现细节放 Task Log，不放这里——但 working notes 捕获了涉及实现细节的重要事件时，那是 Stage 历史的一部分，应进摘要。随后附 Task Log 引用列表供查细节。保持简洁——是协调就绪上下文，不是全面文档。不把 Memory notes 当作单独章节重复。

### 2.7 笔记标准

笔记捕获结构化追踪之外、有助于协调和连续性的上下文。两类服务于不同目的：

**Working Notes（Tracker）：** Stage 中累积的协调上下文——待办考虑、用户偏好、临时约束、技术观察、审查中注意到的模式。审查产出值得记录的上下文时插入。Stage 推进中移除不再适用的条目。Stage 结束时，所有 working notes 蒸馏为两个去向（按第 3.5 节 Stage 摘要创建：按第 2.6 节的 Stage 摘要散文和 Memory notes）。

**Memory Notes（Index）：** 对后续 Stage、协调或任务分派有持久影响的观察——用户偏好、操作原则、架构洞见、影响后续决策的模式。不是所有 working notes 都成为 Memory notes。实现细节和 Stage 特化观察归 Stage 摘要，而非 Memory——它们是历史性的，非前瞻性的。

两类都用列表——一个条目一条 note，每条自包含、无需周边上下文即可理解。

### 2.8 Stage 验证标准

一个 Stage 所有任务都 Done 后，评估该 Stage 交付物在写 Stage 摘要和继续前是否需要整体验证。这是判断性决策，非强制步骤。

**何时验证：** 用户在理解摘要批准时确认了验证的 Stage；Task Reviews 显露出边缘情况或兼容性顾虑的 Stage；Stage 中需要跟进提示的 Stage；Worker 报告困难或重要发现的 Stage；Planner 在 Plan notes 标注了复杂度的 Stage；或累积的 working notes 表明交付物应整体检查的 Stage。Task Reviews 干净、无标志的简单 Stage 可直接进入摘要。

**如何验证：** 重跑 Worker 已执行的最重要验证检查、演练单个任务验证可能未覆盖的边缘情况、跨 Stage 交付物跑整体端到端检查、读源文件/产物/数据确认代码库处于预期状态。验证应匹配项目已确立的验证模式——整合层面的同类检查。对上下文密集的检查，派发 verification subagent，并在行动前对照引用文件核实其发现。

**验证暴露问题时：** 按范围确定响应。可自行解决的封闭问题，直接修。需聚焦调查的问题，派 subagent。需 Worker 级执行的问题，按第 2.3 节规划文档修改标准经 Plan 修改创建新任务。范围或方向不明的问题，把发现和评估及建议选项呈现给用户。验证需用户判断或操作时，呈现发现并暂停。

### 2.9 非 APM Agent 报告

报告来自不在 Worker tracking 中的 agent 时，它是独立加入会话的非 APM agent。这些报告不遵循标准处理流程——没有 Task Log、没有 Worker tracking 条目、也没有要更新的派发状态。按报告自身评估：该 agent 做了什么、是否影响规划文档或当前派发。在 Tracker 加一条 working note 记录该 agent 的身份和贡献。告知用户发现。需要后续工作时，按 `.codex/apm-guides/task-assignment.md` 第 2.7 节非 APM Agent 派发来分派。

---

## 3. 任务审查流程

每份报告三个顺序步骤（处理、日志审查、结果确定），并有规划文档修改和 Stage 摘要创建的条件分支。每个周期后更新 Tracker。

### 3.1 报告处理

用户运行 `/apm-5-check-reports` 或带回 Worker 的 Task Report（或批处理报告）时执行。

执行以下动作：

1. 从 Report Bus 读报告（`.apm/bus/<agent-slug>/report.md`）。
2. 批处理报告（frontmatter `batch: true`）：报告在 `tasks` 数组含逐任务结果（各有 `stage`、`task`、`status`）和字段 `completed`、`stopped_early`。每个已完成任务单独经第 3.2 节 Task Log 审查和第 3.3 节审查结果处理。状态为 `"Not started"` 的任务重新进入派发池。
3. 检查 Handoff 指示——找「Worker 是新实例」的陈述和已读的当前 Stage Task Logs 列表。存在先前 Stage 时，报告还会注明未加载上一 Stage 日志。检测到时，核实 Handoff Log 存在。更新 Tracker 中的 Worker tracking：该 Worker 实例号 +1。把已加载的 Task Logs 与该 Worker 先前完成的所有任务对比，对日志未加载的已完成任务在 Tracker 记 cross-agent overrides。此后，该 Worker 的上一 Stage 同 Agent 依赖按跨 Agent 对待。
4. 检查 auto-compaction 指示——从 auto-compaction 恢复的 Worker 会在 Task Report 注明。检测到时，更新 Tracker 中 Worker tracking 的 Notes（如「auto-compacted, recovered」）。无依赖重分类——Worker 继续作为同一实例。后续给该 Worker 的 Task Prompt 提供略更完整的依赖上下文。
5. 更新派发追踪：把该 Worker 标记为可用，记录完成的任务供就绪评估。
6. 依赖任务需要时，按第 2.5 节合并标准合并完成分支。

### 3.2 Task Log 审查

报告处理后执行。用自然语言可见地呈现你对 Task Log 的评估：声称的状态是否与证据一致、标志是否表明协调相关发现、合适的下一步是什么。

执行以下动作：

1. 读 Task Report 引用的路径上的 Task Log。
2. 按第 2.1 节 Task Log 审查标准解读内容：状态、标志、正文各节。评估状态/标志与正文的一致性。
3. 继续审查结果。

### 3.3 审查结果

Task Log 审查后执行。

执行以下动作：

1. 按第 2.2 节审查结果标准审查 Task Log 的发现。确定结果前，对照任务目标和验证标准评估交付物。版本控制活跃、任务成功但改动仍未提交在任务分支时，按 Rules 约定代其提交——无需跟进。一切良好，跳到步骤 3。有需关注的点，继续步骤 2。
2. 按第 2.2 节审查结果标准调查并确定结果：
   - 未发现，继续步骤 3。
   - Worker 需要跟进，按 `.codex/apm-guides/task-assignment.md` 第 3.4 节跟进 Task Prompt 构造创建跟进 Task Prompt，继续步骤 3。
   - 规划文档需要修改，进入第 3.4 节规划文档修改（完成后回到步骤 3）。
3. 按第 4.1 节任务追踪格式更新 Tracker：已完成任务标 Done、重新评估 Waiting 任务的就绪、更新分支。再评估就绪前按第 2.5 节合并标准执行待处理合并。评估审查是否产出值得记录、加入 working notes 的上下文——临时协调项和持久观察（供后续蒸馏）。移除过时 working notes。把本次审查-派发周期的所有改动批量合并为一次 Tracker 编辑。
4. 按第 2.4 节并行协调标准评估下一步：
   - 所有 Stage 任务 Done 且已合并，按第 4.1 节任务追踪格式折叠 Stage，进入第 3.5 节 Stage 摘要创建。
   - 有 Ready 任务，在同一轮继续 `.codex/apm-guides/task-assignment.md` 第 3.1 节派发评估。
   - 无 Ready 任务但有活跃 Worker，按第 2.4 节并行协调标准说明等待状态，指引用户返回下一份报告。

### 3.4 规划文档修改

审查结果确定规划文档需要修改时执行。总是从第 3.3 节审查结果触发。

执行以下动作：

1. 捕获触发上下文：哪个 Task Log 揭示了发现、哪些具体发现表明要修改、任务状态和标志、调查后结果。
2. 应用第 2.3 节规划文档修改标准：评估受影响文档、分析级联影响、确定权限范围。
3. 任何修改大到需要用户输入时，简明呈现：触发了什么、需改什么、为何超出你单独决定的范围、带权衡的选项、你的建议。整合用户指导。
4. 按第 4.5 节规划文档修改指南、遵循现有文档模式执行修改。核实一致性：文档间的引用完整性（相同数据描述匹配）、术语一致、Spec 与 Plan 的范围对齐。纠正 Spec 时，检查 Plan 是否引用相同内容并相应更新。
5. 修改 Plan 任务（增、删、改依赖）时，按第 4.5 节规划文档修改指南更新 Dependency Graph。
6. 记录：按第 4.4 节修改日志格式更新 Spec 和/或 Plan YAML frontmatter 的 `modified` 字段。
7. 进入第 3.3 节审查结果步骤 4 更新追踪。对照更新后的 Plan 再评估就绪并相应继续。

### 3.5 Stage 摘要创建

Stage 所有任务 Done 时执行。任务 Done = 审查结束时无未解决跟进。所有跟进周期结束后写一次 Stage 摘要。

执行以下动作：

1. 用目录列举已完成 Stage 的 Task Logs，如 `ls .apm/memory/stage-<NN>/`（或平台等价）。从各 Task Review 已审查的日志综合——日志未变且仍在上下文时无需重读。
2. 按第 2.8 节 Stage 验证标准评估是否需要 Stage 验证。需要时，先验证再继续。
3. 按第 2.7 节笔记标准蒸馏 working notes：对后续工作有持久影响的观察成为 Index 的 Memory notes，Stage 特化观察成为 Stage 摘要散文。下一 Stage 需要的 working notes 保留。本次审查立即触发 Stage 摘要（Stage 最后任务）时，本次审查的观察可直接写去向，不必先经 working notes。
4. 综合 Stage 级观察，按第 4.3 节 Index 格式把 Stage 摘要追加到 Index。Index 结构（Memory notes 在 Stage summaries 之上）使步骤 3、4 可作为一次连续编辑完成。

---

## 4. 结构规范

### 4.1 任务追踪格式

Tracker 中的 Task Tracking 节按 Stage 追踪任务状态、agent 指派和分支状态。每个审查周期后更新。

**位置：** `.apm/tracker.md` 的 `## Task Tracking` 节。

**格式：**

```markdown
**Stage 1:** Complete

**Stage 2:**

| Task | Status | Agent | Branch |
|------|--------|-------|--------|
| 2.1 | Done | frontend-agent | |
| 2.2 | Active | backend-agent | feat/backend-models |
| 2.3 | Active | frontend-agent | feat/frontend-auth |
| 2.4 | Waiting: 2.1 | backend-agent | |
| 2.5 | Ready | frontend-agent | |
```

**任务状态：** `Ready`、`Active`、`Done`、`Waiting: <deps>`。

**任务生命周期：**

- `Waiting: N.M`——依赖未满足。可列多个依赖。
- `Ready`——所有依赖完成，可派发。
- `Active | branch-name`——已派发，Worker 在分支上。
- `Done | branch-name`——已审查，分支待合并。
- `Done`（无分支）——已合并。

写每个任务在审查-派发周期的末状态。任务同一轮解锁并派发时，直接从 Waiting 写 Active。任务解锁但无法派发——指定 Worker 有 Active 任务、或某 pending report 能解锁更好派发（按 `.codex/apm-guides/task-assignment.md` 第 2.4 节派发标准）——写 Ready。

**分支清理：** 按第 2.5 节合并标准合并完成分支后，清空该任务行的 Branch 列。

**Stage 折叠：** Stage 所有任务 Done 且无剩余分支时，把所有任务行替换为 `**Stage N:** Complete`。

**批量编辑：** Task ID 列保证编辑工具唯一定位个别行。同一审查-派发周期多行或 working notes 变化时，把所有 Tracker 更新批量合并为一次编辑。

### 4.2 Tracker 格式

**位置：** `.apm/tracker.md`

**YAML Frontmatter Schema:**

```yaml
---
title: <project name>
completed_at: <datetime>  # set by Manager at project completion - absence means in-progress, ISO 8601 UTC
---
```

**Tracker 节：**

- *`## Task Tracking`：* 按第 4.1 节任务追踪格式的逐 Stage 任务状态。
- *`## Worker Tracking`：* 记录 Worker 状态、实例号和协调备注。首次派发 Worker、检测到 Handoff、报告 auto-compaction 恢复时更新 Worker tracking。Worker Handoff 重分类依赖时，cross-agent overrides 记录在 Worker 表下方，列出受影响的具体任务并引用触发重分类的 Handoff。
- *`## Version Control`：* 按 `.codex/apm-guides/task-assignment.md` 第 4.4 节 Tracker VC 条目格式的逐仓库 base branch、分支约定和提交约定。分支状态在任务表的 Branch 列逐任务跟踪。
- *`## Working Notes`：* 按第 2.7 节笔记标准的临时协调上下文。内容随上下文演进插入和移除。

**Worker Tracking 表：**

```markdown
| Agent | Instance | Notes |
|-------|----------|-------|
| frontend-agent | 2 | Handoff after Stage 1 |
| backend-agent | 1 | |
```

**Cross-Agent Overrides**（适用时，在 Worker Tracking 表下方）：

```markdown
**Cross-Agent Overrides:**
- frontend-agent: Tasks 1.1, 1.3 (pre-Handoff) - treat as cross-agent
```

### 4.3 Index 格式

**位置：** `.apm/memory/index.md`

**YAML Frontmatter Schema:**

```yaml
---
title: <project name>
---
```

**Index 节：**

- *`## Memory Notes`：* 按第 2.7 节笔记标准的持久观察。跨 Handoff 持续的模式、偏好和洞见。
- *`## Stage Summaries`：* 每个 Stage 完成后追加。每条：

```markdown
### Stage <N> - <Stage Name>

[Prose summary: outcome, agents involved, notable findings, patterns, key commits]

**Task Logs:**
- task-<NN>-<MM>.log.md
- task-<NN>-<MM>.log.md
```

### 4.4 修改日志格式

修改 Spec 或 Plan 时更新 YAML frontmatter 的 `modified` 字段：

```yaml
modified: Task 2.3 scope clarified based on task-02-02.log.md findings. Modified by the Manager.
```

### 4.5 规划文档修改指南

**Spec：** 维持现有章节结构。在相关标题下添加内容。顶层类别用 `##`。保持规格具体可行动——影响所构建之物、跨多个任务适用的设计决策。任务特化细节放任务指引，不在这里。

**Plan：**

- *加任务：* 插到合适 Stage 下，维持编号顺序，指定所有字段（Objective、Output、Validation、Guidance、Dependencies、Steps）。
- *改任务：* 保留现有结构，只更新受影响字段。
- *删任务：* 删除任务节，并更新任何引用它为依赖的其他任务。

**Rules：** 修改只待在 `APM_RULES {}` 区块内。类别用 `##` 标题。只加真正普适的模式。

**Dependency Graph：** 任务依赖变化时，重新生成相关图节。同 Agent 依赖用 `-->`，跨 Agent 用 `-.->`。agent 变化时更新节点样式。

---

## 5. 常见错误

- *状态不一致：* Worker 声称 Success 但日志正文显示验证不完整、有未解决问题或缺交付物时，把正文视为比状态字段更权威，接受前先调查。
- *接受不充分报告：* 验证标准未充分执行或交付物不全时就标 Done。接受前用跟进 Task Prompt 打回。
- *跳过 Handoff 检测：* 不追踪 Worker Handoff 会导致依赖上下文处理错误。
- *未确认恢复：* Worker 报告表明发生 auto-compaction 时，把它纳入评估——重建的上下文可能影响报告完整性。
- *单文档隧道视野：* 更新 Spec 却不检查 Plan 是否引用相同内容，或改 Plan 却不评估 Spec 的设计假设是否仍成立。一个规划文档的变化常级联到另一个。
- *治标：* 修改一个文档以绕开本应在另一文档解决的问题。问题在执行中显露时，追到根因所在文档，而不是在别处打补丁。

---

**指南结束**
