---
name: apm-communication
description: Agent 通信标准和基于文件的 Message Bus 协议，用于结构化多 Agent 协作。
---

# APM 1.0.1 - Communication Skill

## 1. 目标

本 skill 定义 APM 中 Agent 的通信标准和基于文件的 Message Bus 协议。Planner、Manager 和 Worker 都必须读取并遵守本文件。

非 APM agent 也可以参与 Message Bus 通信，方法见同目录下的 `bus-integration.md`。

---

## 2. Agent 与用户通信

### 2.1 直接沟通

和用户沟通时，使用自然语言。说明发生了什么、做出了什么判断、下一步要做什么。

当需要用户操作时，必须明确说明：

- 在哪个 Agent 会话中操作；
- 运行什么命令；
- 是否需要附加 agent-id；
- 预期结果是什么。

命令使用代码块，路径、字段和值使用行内代码。

### 2.2 可见推理

在关键决策点，先向用户展示你的分析，再执行动作。用户需要能审查你的判断、权衡和风险。

可见推理不等于暴露内部隐藏推理，而是用可审查的方式说明：

- 你正在评估什么；
- 关键证据是什么；
- 有哪些取舍；
- 你得出的结论是什么。

### 2.3 术语边界

APM 正式术语可以直接使用，例如 Task、Stage、Worker、Manager、Planner、Handoff、Message Bus。

不要在用户输出中暴露内部章节编号、流程步骤名或决策分支编号。应当用自然语言说明当前动作，而不是说“我正在执行第 3.2 节”。

---

## 3. Agent 与系统通信

写入 APM artifacts 时，遵守对应指南定义的结构，包括：

- `Spec`
- `Plan`
- `Tracker`
- Task Log
- Task Report
- Handoff Log
- Bus 文件

结构化字段、YAML frontmatter、路径和状态值保持英文原值，便于工具链和后续流程识别。自由文本内容使用自然语言。

---

## 4. Message Bus 协议

Message Bus 位于：

```text
.apm/bus/
```

Bus 文件要么为空，表示没有待处理消息；要么包含一条等待交付的消息。

写入 outgoing bus 前，先清空 incoming bus。写入前总是先读取目标 bus 文件，避免跨平台文件工具无法识别空文件。

### 4.1 Bus 身份

Agent 身份来自目录名：

```text
.apm/bus/<agent-slug>/
```

Worker 必须确认任务中的 `agent` 字段与当前目录匹配。如果不匹配，拒绝执行并提示用户切换到正确 Worker。

### 4.2 Agent ID 解析

`apm-4-check-tasks` 和 `apm-5-check-reports` 可接受 `[agent-id]` 参数。解析顺序：

1. 精确匹配 `.apm/bus/` 目录名；
2. 前缀匹配；
3. 最合理的模糊匹配。

如果只有一个合理候选，直接使用。如果有多个候选，列出并询问用户。如果没有 bus 目录，说明 Message Bus 尚未初始化。

### 4.3 Agent Slug 格式

Agent slug 从 `Plan` 的 Workers 字段派生：

- 转小写；
- 空格替换为连字符；
- 保持 kebab-case。

示例：

```text
Frontend Agent -> frontend-agent
Backend Agent -> backend-agent
```

Manager 固定使用：

```text
manager
```

---

**Skill 结束**
