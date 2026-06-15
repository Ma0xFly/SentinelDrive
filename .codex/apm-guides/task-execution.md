# APM 1.0.1 - Task Execution Guide

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

本指南定义 Worker 如何执行 Manager 通过 Task Prompt 分派的任务，包括接收、依赖上下文整合、实现、验证、修正循环、提交、日志和报告。

---

## 2. 执行标准

- 遵循当前代码库已有结构、命名、风格和测试习惯。
- 小步实现，每完成一个有意义的修改就验证一次。
- Task Prompt 和 `AGENTS.md` 优先于通用最佳实践。
- 不做无关重构，不扩大任务范围。
- 面向用户的说明使用中文；代码、命令、路径、字段保持原样。

Worker 不读取 `Spec`、`Plan`、`Tracker`、`Memory Index` 或其他 Agent 的协调文档。若 Task Prompt 不足以执行，不要自行翻协调层文档补上下文；应说明缺口并通过用户/Manager 获取补充。

### 2.1 上下文整合

如果 Task Prompt 中 `has_dependencies: true`，先读取依赖上下文。

- **Same-agent dependency**：这是你自己之前完成的工作。使用轻量回忆上下文，必要时读取提示中的路径。
- **Cross-agent dependency**：这是其他 Worker 完成的工作。必须完整读取依赖说明中的文件、接口和产物摘要，不要靠猜测集成。

如果依赖基础不稳定：

- 跨 Agent 依赖不清楚时，暂停并请求用户或 Manager 指导；
- 同 Agent 的轻微歧义可以按最合理解释继续，但必须在 Task Log 中说明。

如果代码库事实与 Task Prompt 指令冲突，先验证实际状态，再按最小必要调整执行；不要为了匹配过期指令破坏已有正确实现。冲突和处理理由必须写入 Task Log。

### 2.2 验证标准

按 Task Prompt 的 Validation Criteria 执行所有可自主验证项：

- 运行测试；
- 运行构建或 lint；
- 验证文件和产物存在；
- 验证行为符合要求。

如果自主验证失败，先自行修复，不要要求用户审查失败状态。

如果验证需要用户判断或外部环境，例如设计确认、线上平台操作、账号权限、外部 API 行为，必须在自主验证全部通过后暂停，并清楚说明用户需要检查什么、怎么反馈。

不能执行某个验证命令时，要说明原因、替代检查和残余风险。不能把“未运行测试”写成“验证通过”。

### 2.3 修正循环

验证失败时：

1. 先读错误输出，定位根因。
2. 每轮只做一个有针对性的修复。
3. 修复后重新验证。
4. 如果同类问题反复出现、根因不清、或多个独立区域都可能导致问题，使用 debug subagent。For complex cross-agent dependencies or multi-file exploration, spawn a dedicated explorer subagent rather than inline searching - it runs in its own context window and returns consolidated findings: `spawn_agent(agent_type="explorer", message="...")`. Structure the prompt with specific files to read and questions to answer.
5. subagent 返回后，必须验证它的结论，再应用修复。
6. 如果仍无法解决，使用 `Partial` 状态报告，说明已尝试内容、失败原因和需要的指导。

### 2.4 规则更新

如果用户在执行中给出纠正或新要求，先遵守并继续任务。任务完成后：

- 在 Task Log 的 Important Findings 中记录；
- 将 `important_findings` 设为 `true`；
- 报告后询问用户是否要把该纠正提升为 `AGENTS.md` 中的通用 Rule。

### 2.5 版本控制

Worker 只在 Task Prompt 指定的工作区和分支上工作。

- 可以 commit；
- 不创建分支；
- 不管理 worktree；
- 不 push；
- 不 merge。

Commit message 描述真实代码变化，不出现 APM、Task ID、Stage、Worker 等框架词。

提交前检查工作区状态，确认只包含当前 Task 相关变更。发现无关改动时不要回滚用户改动，先判断是否与任务相关；无关则保留并在日志中说明未触碰。

### 2.6 Batch 规则

如果收到 batch：

- 按顺序执行；
- 每个 Task 独立执行、验证、写 Task Log；
- 某个 Task `Failed` 时立即停止 batch；
- 最后写一份 batch report。

---

## 3. 执行流程

### 3.1 接收 Task Prompt

1. 判断是否为 batch。
2. 校验 YAML frontmatter 中的 `agent` 是否匹配当前 Worker。
3. 如果有 Workspace section，切换到指定分支或 worktree。
4. 如果 `has_dependencies: true`，先执行上下文整合。

### 3.2 实现

1. 按 Detailed Instructions 顺序执行。
2. 应用 Guidance 和 `AGENTS.md` 中相关规则。
3. 需要用户动作时，说明原因、选项和期望反馈。
4. 需要 subagent 时，给出结构化任务：目标、上下文、文件路径、预期输出。
5. 完成实现后，告知用户你将进入验证。

### 3.3 验证

1. 执行所有自主验证项。
2. 失败则进入修正循环。
3. 需要用户参与的验证，在自主验证通过后暂停。
4. 全部通过则进入完成流程。

### 3.4 完成

1. 在聊天中用中文说明完成评估：
   - 目标是否达成；
   - 验证是否通过；
   - 是否有 important findings；
   - 是否有 compatibility issues；
   - outcome 是 `Success`、`Partial` 还是 `Failed`。
2. 按规则 commit。
3. 按 `.codex\apm-guides\task-logging.md` 写 Task Log。
4. 按 `.codex\apm-guides\task-logging.md` 写 Task Report。
5. 告知用户回到 Manager 会话运行：

   ```text
   /apm-5-check-reports <agent-id>
   ```

   Codex CLI 使用：

   ```text
   $apm-5-check-reports <agent-id>
   ```

---

## 4. 常见错误

- 没读依赖文件就开始实现；
- 验证失败时盲目改代码；
- Task 未完全验证就标记 `Success`；
- 在 commit message、代码注释或用户可见产物中写 APM 内部术语；
- 把 Manager 的协调职责拿到 Worker 会话里做；
- 忽略 Task Prompt 的范围限制。
- 看到英文错误输出就只粘贴原文，不做中文解释；
- 因为实现了主要功能就跳过边界条件验证；
- 把需要用户判断的验收点当作自主验证通过。

---

**Guide 结束**
