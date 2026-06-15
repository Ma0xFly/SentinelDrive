---
name: apm-6-handoff-manager
description: 执行 APM Manager Handoff。
user-invocable: true
---

## 0. 纯中文本土化执行规范

本文件是 APM 中文本土化版本。执行时必须遵守以下规则：

- 本文件的中文说明就是实际执行口径，不需要再参考英文原文。
- 面向用户的解释、提问、分析、总结、风险说明、审查意见和下一步指令必须使用中文。
- APM 项目产物正文必须使用中文，包括 `.apm/spec.md`、`.apm/plan.md`、`AGENTS.md` 中的 APM 规则、Task Prompt、Task Log、Task Report、Handoff Log、Recovery Summary、Stage Summary、Memory Notes 和 Working Notes。
- 可以保留英文的内容仅限命令、路径、代码标识、YAML 字段、Markdown 结构标题、状态值、Agent 名称、Task ID、mermaid 语法、协议字段、库名、框架名和行业通用缩写。
- 不得为了节省上下文而删除流程约束。必须保留审批门槛、上下文边界、依赖判定、验证标准、日志格式、Message Bus、Handoff、Recovery、Tracker 和 Memory 相关规则。
- 如果发现规则缺口，用中文补足；不要回退到英文说明。

---
# APM 1.0.1 - Manager Handoff 命令

## 1. 目标

当 Manager 的上下文窗口接近上限、发生自动压缩、输出质量下降，或用户要求交接时，执行本命令。

你需要创建两类产物：

- **Handoff Log**：记录当前 Manager 实例已经完成、决定和观察到的内容，保存到 `.apm/memory/handoffs/manager/`。
- **Handoff Prompt**：写入 `.apm/bus/manager/handoff.md`，指导下一个 Manager 如何重建上下文。

新的 Manager 不是只读 Handoff Log，而是结合规划文档、指南、skill、Task Logs 和 Handoff Log 重建上下文。

---

## 0. 中文交接产物强制规则

Manager Handoff 产物必须使用中文正文。

- Handoff Log 中的已完成事项、历史判断、用户偏好、协调经验、风险和版本控制状态说明必须中文。
- Handoff Prompt 中的当前状态、下一步动作、待读文件、未决报告和 active Workers 说明必须中文。
- YAML 字段、路径、命令、Task ID、Agent 名称、分支名、状态值可以保留英文。
- 如果引用英文命令输出、错误消息或代码片段，必须补充中文解释。

---

## 2. 执行流程

### 2.1 创建 Handoff Log

执行以下动作：

1. 判断当前 Manager instance number 和下一个 Manager instance number。
2. 创建 Handoff Log，记录过去发生的事情。内容使用过去时，不写当前待办状态。
3. 必须覆盖：
   - 已协调的 Stages；
   - 已审查的 Tasks；
   - 已完成的派发循环；
   - 已发生的 Worker Handoffs；
   - 当前实例发生过的自动压缩或恢复事件；
   - 从 Tracker 提取的版本控制状态；
   - 用户偏好和沟通模式；
   - 重要协调判断、尝试过的方法和经验。

### 2.2 创建 Handoff Prompt

执行以下动作：

1. 创建 Handoff Prompt，记录当前状态和下一步动作。内容必须可执行、使用现在时。
2. 必须覆盖：
   - 当前 Stage 和进度；
   - outstanding Tasks 的完整信息；
   - 正在审查的报告和未决结论；
   - active Workers 和派发状态；
   - 新 Manager 必须读取的 Task Logs 和文件；
   - 立即下一步应该做什么。

### 2.3 用户审查和完成

1. 写入 Handoff Prompt：

   ```text
   .apm/bus/manager/handoff.md
   ```

2. 向用户展示 Handoff Log 路径和 Handoff Bus 路径，请用户审查。
3. 指导用户新开 Manager 会话并运行：

   ```text
   /apm-2-initiate-manager
   ```

   Codex CLI 使用：

   ```text
   $apm-2-initiate-manager
   ```

4. 如果用户要求修改，更新产物后再结束。完成后，当前 Manager 不再继续协调。

---

## 3. Handoff Log 结构

位置：

```text
.apm/memory/handoffs/manager/handoff-<NN>.log.md
```

YAML frontmatter：

```yaml
---
agent: manager
outgoing: <N>
incoming: <N+1>
handoff: <N>
stage: <N>
---
```

正文结构：

```markdown
# Manager Handoff <N> (Manager <N> -> Manager <N+1>)

## Summary

## Working Context

## Worker Handoffs

## Version Control State

## Working Notes
```

---

## 4. Handoff Prompt 结构

写入：

```text
.apm/bus/manager/handoff.md
```

必须包含：

- outgoing 和 incoming instance number；
- 需要读取的 Handoff Log；
- 需要读取的当前 Stage Task Logs；
- previous-stage dependency context 的处理方式；
- 当前 Stage、进度、阻塞点、working notes；
- 立即下一步；
- 要求新 Manager 先用中文输出简洁理解摘要，然后继续协调。

---

**命令结束**
