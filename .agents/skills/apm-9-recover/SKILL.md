---
name: apm-9-recover
description: 恢复 APM agent 的工作上下文。
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
# APM 1.0.1 - Recover 命令

本命令用于在平台自动压缩、手动压缩、会话丢失或中断后重建工作上下文。仅适用于 Manager 和 Worker。如果你是 Planner 或非 APM agent，请简要拒绝并停止。

参数：可选 `[role]`，可以是 `manager` 或 Worker agent identifier，例如 `frontend-agent`。

当前参数：`(the text provided by the User after the command invocation, if any)`。

**中文恢复规则：**

- 恢复过程中面向用户的说明、问题、当前状态判断和下一步动作必须使用中文。
- 写入 `Tracker` 的 recovery working note 必须中文。
- Worker 在下一份 Task Report 中说明恢复事件时必须中文。
- 引用英文命令输出或错误消息时，可以保留原文，但必须补充中文解释。

**流程：**

1. 判断角色：
   - 如果提供参数，`manager` 表示 Manager，其他值按 Worker agent-id 处理。
   - 如果未提供参数，从当前会话上下文或压缩摘要判断。
   - 如果无法判断，询问用户。

2. 重新读取对应启动命令及其引用的所有文档：
   - Manager：`.agents\skills\apm-2-initiate-manager\SKILL.md`
   - Worker：`.agents\skills\apm-3-initiate-worker\SKILL.md`

   只读启动命令不够，必须读取它引用的指南、skill 和项目产物。跳过问候和身份注册中的重复说明。

3. 从项目产物和当前代码状态恢复工作进度。如果产物无法填补关键空白，向用户询问最小必要上下文。

4. 记录恢复事件：
   - 如果你是 Manager，在 `Tracker` 中添加 working note。
   - 如果你是 Worker，在下一份 Task Report 中说明恢复事件。

   Recover 不增加 instance number，仍然作为同一个实例继续工作。

5. 恢复职责并继续。

---

**命令结束**
