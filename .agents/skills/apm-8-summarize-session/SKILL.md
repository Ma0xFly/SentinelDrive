---
name: apm-8-summarize-session
description: 总结并可选归档 APM 会话。
user-invocable: true
---

# APM 1.0.1 - Summarize Session 命令

本命令用于总结当前 APM 会话，并可选择归档。你是独立总结 agent，不是 Planner、Manager 或 Worker。如果你正处于这些角色中，请简要拒绝并停止。

## 流程

1. 读取以下产物：
   - `.apm/spec.md`
   - `.apm/plan.md`
   - `.apm/tracker.md`
   - `.apm/memory/index.md`

   如果 working notes 或 Stage summaries 引用了特定 Task Logs 且需要验证，读取对应日志。不要无差别读取所有 Task Logs。

2. Spawn a dedicated explorer subagent - it runs in its own context window and returns findings when complete: `spawn_agent(agent_type="explorer", message="...")`. 要求它读取 `.apm/` 下所有产物，包括 `.apm/memory/` 中的 Task Logs，并和当前代码库交叉验证。它需要报告：
   - 每个 Stage 的结果；
   - deliverables 是否实际存在；
   - commit、branch 和验证结果是否与 `.apm/` 状态一致；
   - 代码库是否已经偏离规划文档。

3. 写入：

   ```text
   .apm/session-summary.md
   ```

   摘要必须明确说明它是某一时间点的快照。

4. 向用户展示摘要，询问是否需要补充、修正或强调。用户反馈后更新摘要。

5. 询问是否归档当前会话。如果用户同意，询问是否使用自定义归档名。

6. 运行：

   ```bash
   apm archive --force
   ```

   或：

   ```bash
   apm archive --force --name <name>
   ```

7. 读取或创建：

   ```text
   .apm/archives/index.md
   ```

   将本次归档追加到索引表顶部。

8. 告知用户归档完成。若要开始新 APM 会话，需要在终端运行 `apm init` 或 `apm custom`，然后在 AI 助手中启动 Planner。

## Session Summary 结构

位置：

```text
.apm/session-summary.md
```

YAML frontmatter：

```yaml
---
date: <YYYY-MM-DDTHH:MM:SSZ>
project: <project name>
stages_completed: <number>
total_tasks: <number>
outcome: <complete | partial | incomplete>
---
```

正文必须包含：

- **Project Scope**：项目目标和范围；
- **Stages and Outcomes**：每个 Stage 的目标、完成情况和结果；
- **Key Deliverables**：主要交付物和路径；
- **Codebase State**：实际代码库与计划产物的差异；
- **Notable Findings**：执行中形成的重要经验、修复、恢复事件和协调洞察；
- **Known Issues**：未解决问题、开放问题和注意事项；
- **Snapshot Notice**：说明该总结反映的是创建时间点的状态，之后代码库可能已变化。

## Archive Index 格式

位置：

```text
.apm/archives/index.md
```

```markdown
# APM Archive Index

| Archive | Date | Scope | Stages | Tasks |
|---------|------|-------|--------|-------|
```

最新归档放在表格顶部。

---

**命令结束**
