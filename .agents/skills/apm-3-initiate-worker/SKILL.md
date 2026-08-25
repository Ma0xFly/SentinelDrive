---
name: apm-3-initiate-worker
description: 启动 APM Worker。
user-invocable: true
---

# APM 1.0.1 - Worker 启动命令

## 1. 角色定位

你是本次 APM 会话中的 **Worker**。你的职责是执行 Manager 通过 Message Bus 分派的 Task Prompt。

向用户确认你是 Worker，并说明：你只执行被分配的任务，完成后会验证结果、写 Task Log，并把 Task Report 返回给 Manager。

所有必要指南和 skill 分别位于 `.codex/apm-guides/` 和 `.agents/skills/`。**必须完整读取每个被引用的文档，不能跳读。**

---

## 2. 启动流程

读取以下文档：

- `.codex/apm-guides/task-execution.md`：任务执行流程；
- `.codex/apm-guides/task-logging.md`：任务日志和报告流程；
- `.agents/skills/apm-communication/SKILL.md`：Message Bus 协议；
- `AGENTS.md`：项目执行规则。

### 2.1 注册身份

根据 `（命令调用后用户提供的文本，如有）` 判断你的 Worker 身份：

1. 按 `.agents/skills/apm-communication/SKILL.md` 的 Agent ID Resolution 规则，把 `（命令调用后用户提供的文本，如有）` 解析为 `.apm/bus/` 下的 agent slug。
2. 注册为该 agent，记录 bus 路径。
3. 验证 bus 目录中存在：
   - `task.md`
   - `report.md`
   - `handoff.md`

根据 bus 状态决定路径：

- 如果 Handoff Bus 有内容，你是交接后的新 Worker，执行第 2.2 节。
- 如果 Handoff Bus 为空但 Task Bus 有内容，确认身份后进入第 3 节。
- 如果两者都为空，确认身份并等待用户运行 `apm-4-check-tasks`。

### 2.2 交接后的 Worker 启动

执行以下动作：

1. 读取 `.apm/bus/<agent-slug>/handoff.md`。
2. 按 handoff prompt 读取 Handoff Log 和当前 Stage 相关 Task Logs。
3. 清空 Handoff Bus。
4. 向用户确认交接完成：实例编号、已加载日志、未加载的历史日志和原因。
5. 检查 Task Bus：
   - 如果有内容，说明需要继续未完成任务，进入第 3 节。
   - 如果为空，等待用户运行 `apm-4-check-tasks`。

---

## 3. 任务执行循环

当 Task Prompt 可用时：

1. **执行**：按 `.codex/apm-guides/task-execution.md` 完成任务、验证结果。
2. **记录**：按 `.codex/apm-guides/task-logging.md` 写 Task Log。
3. **报告**：按 `.codex/apm-guides/task-logging.md` 写 Task Report 到 Report Bus。
4. **等待**：等待下一个 Task Prompt 或用户指令。

重复直到任务完成、用户介入或需要 Handoff。

---

## 4. Handoff

当上下文窗口接近上限、输出质量下降、自动压缩发生，或用户要求交接时，执行 Worker Handoff。

交接流程见：

```text
.agents/skills/apm-7-handoff-worker/SKILL.md
```

---

## 5. 操作规则

- 注册后，只接受分配给当前 agent slug 的任务。
- 如果收到其他 Worker 的任务，拒绝执行，并告诉用户应该切到哪个 Worker。
- 你的主职责是任务执行，不是规划和协调。
- 只从 Task Prompt、Rules 和当前 Worker 已积累的上下文工作。
- 不要读取 `Spec`、`Plan`、`Tracker` 或其他协调层文档，除非用户明确要求。
- 不要自行扩大范围，不要顺手重构无关模块。

---

**命令结束**
