# APM 1.0.1 - Task Review Guide

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

本指南定义 Manager 如何审查 Worker 的 Task Report 和 Task Log，如何决定通过、返工、修改计划，以及如何维护 `Tracker` 和 `Memory Index`。

---

## 0. 中文审查和记忆产物强制规则

Manager 的审查输出和记忆产物必须使用中文正文。

- 面向用户的审查结论、调查说明、风险判断、是否通过、是否返工、是否修改规划文档，必须使用中文。
- 写入 `Tracker` 的 Working Notes、写入 `Memory Index` 的 Memory Notes 和 Stage Summaries 必须使用中文。
- 如果 Task Log 中有英文命令输出、错误消息或代码片段，可以原样引用；但 Manager 的判断和解释必须中文。
- `Ready`、`Active`、`Done`、`Waiting: <deps>` 等状态值和表格字段保留英文，以保持 APM 格式兼容。

---

## 2. 审查标准

### 2.1 Task Log 审查

读取 Task Log 后，判断：

- `status` 是否和正文证据一致；
- `important_findings` 是否影响其他 Tasks、Spec、Plan 或 Rules；
- `compatibility_issues` 是否意味着集成风险、设计错误或计划错误；
- Validation 是否真的覆盖了 Task Prompt 的验收标准；
- Output 是否和 Objective 匹配。

如果状态、flags 和正文矛盾，视为需要调查。

审查时以 Task Log 正文证据为准，而不是只看 YAML `status`。如果 Worker 声称 Success，但 Validation 未覆盖 Task Prompt、Output 缺少交付物、Issues 仍有未解决项，必须调查或发 follow-up，不能直接 Done。

### 2.2 Review Outcome

审查后选择：

- **通过**：Task 达成目标，验证充分，无需处理 flags。
- **Follow-up**：Worker 需要带着更清晰指令重试。
- **修改规划文档**：Spec、Plan 或 Rules 中的假设被证伪或需要补充。
- **新增任务**：已 Done 的任务发现后续缺陷，原任务保持 Done，创建新 Task 处理。

小范围修正可以由 Manager 直接处理。影响范围、设计方向、项目范围或多个 Tasks 时，必须请求用户确认。

调查可以由 Manager 自己完成，也可以派 debug subagent。范围小、文件明确的问题直接查；跨模块、上下文密集或根因不明的问题用 subagent。subagent 返回后，关键结论必须通过读取文件或运行检查验证。

### 2.3 规划文档修改

修改前先判断级联影响：

- Spec 变化可能影响 Plan；
- Plan 变化可能反映 Spec 不完整；
- Rules 通常相对独立，但可能影响所有 Workers。

允许 Manager 直接处理：

- 单个 Task 澄清；
- 添加遗漏依赖；
- 小型 Spec 补充；
- 小型 Rules 调整。

需要用户确认：

- 多个 Tasks 受影响；
- 范围扩大或缩小；
- 设计方向变化；
- 新增 Stage；
- 多个小变化叠加成重大变化。

修改任何规划文档前先判断级联：Spec 改动是否要求 Plan 任务调整；Plan 任务调整是否说明 Spec 假设不完整；Rules 改动是否会影响所有 Workers。不要只改症状所在文档，要追到根因所在文档。

### 2.4 并行协调

并行 Workers 的报告可能乱序到达。每处理一份报告后：

1. 完成审查；
2. 必要时 merge；
3. 更新 Tracker；
4. 重新评估 Ready Tasks；
5. 如果有可派发任务，在同一轮继续派发。

只有没有 Ready Tasks、需要用户决策，或等待其他 Worker 报告时才暂停。

并行审查中，处理一份报告后应在同一轮继续完成 Tracker 更新、merge、Ready 评估和下一次派发判断。不要让用户在 Manager 中手动催下一步。

### 2.5 Merge

成功审查后，按 Tracker 中的版本控制约定 merge feature branch。

基本流程：

```bash
git checkout <base-branch>
git merge <branch-name>
```

并行 worktree 完成后，先移除 worktree，再删除已 merge 分支。

如果出现复杂冲突，先基于 Spec、Plan 和 Task Log 判断；必要时使用 debug subagent 或请求用户决策。

---

## 3. 审查流程

### 3.1 Report Processing

用户运行 `apm-5-check-reports` 后：

1. 读取 `.apm/bus/<agent-slug>/report.md`。
2. 如果是 batch report，逐个处理已完成 Tasks；未开始 Tasks 回到调度池。
3. 检查是否为 Handoff 后的新 Worker。如果是，更新 Worker tracking 和 cross-agent overrides。
4. 检查是否发生 Recover 或 auto-compaction，写入 Worker notes。
5. 将 Worker 标记为空闲。

### 3.2 Task Log Review

1. 读取 Report 中的 `log_path`。
2. 用中文展示审查判断：
   - 状态是否可信；
   - 验证是否充分；
   - flags 是否需要处理；
   - 下一步是什么。
3. 进入 Review Outcome。

### 3.3 Outcome Handling

1. 如果通过，更新 Tracker。
2. 如果需要 follow-up，按 `.codex\apm-guides\task-assignment.md` 创建 Follow-Up Task Prompt。
3. 如果需要修改 Spec、Plan 或 Rules，先做影响评估，必要时请求用户确认。
4. 如果任务完成且分支需要 merge，执行 merge。
5. 重新评估下一步：
   - Stage 完成：写 Stage Summary；
   - 有 Ready Tasks：回到 Dispatch Assessment；
   - 没有 Ready Tasks 但有 active Workers：告诉用户等待哪份报告。

### 3.4 Stage Summary

当一个 Stage 所有 Tasks 都 Done 且分支已 merge：

1. 列出该 Stage 的 Task Logs。
2. 判断是否需要整体 Stage verification：如果本 Stage 有 follow-up、flags、兼容性风险、复杂汇合点、Planner notes 提醒或用户要求验收，必须做整体验证；简单且审查干净的 Stage 可以直接总结。
3. 把 working notes 归类：
   - 对后续有长期影响的，写入 Memory Notes；
   - 只属于本 Stage 历史的，写入 Stage Summary。
4. 追加到 `.apm/memory/index.md`。

Stage Summary 写历史事实和协调结论，不复制 Task Log 细节。Memory Notes 只保留对后续 Stage 有长期影响的偏好、架构事实、风险或执行原则。

---

## 4. Tracker 格式

Task Tracking：

```markdown
**Stage 1:**

| Task | Status | Agent | Branch |
|------|--------|-------|--------|
| 1.1 | Done | frontend-agent | |
| 1.2 | Active | backend-agent | feat/api-auth |
| 1.3 | Waiting: 1.2 | frontend-agent | |
```

状态：

- `Waiting: N.M`
- `Ready`
- `Active`
- `Done`

Worker Tracking：

```markdown
| Agent | Instance | Notes |
|-------|----------|-------|
| frontend-agent | 2 | Handoff after Stage 1 |
```

Cross-Agent Overrides：

```markdown
**Cross-Agent Overrides:**
- frontend-agent: Tasks 1.1, 1.3 (pre-Handoff) - treat as cross-agent
```

---

## 5. Index 格式

`.apm/memory/index.md` 包含：

- `## Memory Notes`
- `## Stage Summaries`

Stage Summary 建议结构：

```markdown
### Stage <N>: <Name>

<Stage 结果、参与 Workers、主要交付物、关键发现、风险和后续影响。>

**Task Logs:**
- `.apm/memory/stage-<NN>/task-<NN>-<MM>.log.md`
```

---

## 6. 常见错误

- 只看 Report，不读 Task Log；
- Worker 标记 Success 就直接 Done；
- flags 为 true 但不调查；
- follow-up 仍复制原任务，不补充调查结论；
- Stage 完成后不做必要的整体验证；
- merge 前就派发依赖任务；
- Handoff 后不更新 dependency classification。
- 发现 Spec 错误却只在 Tracker 里写 note；
- Stage Summary 把实现细节堆进去，反而淹没后续 Manager 需要的协调信息；
- 自动压缩或 Recover 后不记录上下文重建风险。

---

**Guide 结束**
