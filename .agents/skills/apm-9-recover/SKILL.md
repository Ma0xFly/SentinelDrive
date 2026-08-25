---
name: apm-9-recover
description: 恢复 APM agent 的工作上下文。
user-invocable: true
---

# APM 1.0.1 - Recover 命令

本命令用于在平台自动压缩、手动压缩、会话丢失或中断后重建工作上下文。仅适用于 Manager 和 Worker。如果你是 Planner 或非 APM agent，请简要拒绝并停止。

参数：可选 `[role]`，可以是 `manager` 或 Worker agent identifier，例如 `frontend-agent`。

当前参数：`（命令调用后用户提供的文本，如有）`。

**流程：**

1. 判断角色：
   - 如果提供参数，`manager` 表示 Manager，其他值按 Worker agent-id 处理。
   - 如果未提供参数，从当前会话上下文或压缩摘要判断。
   - 如果无法判断，询问用户。

2. 重新读取对应启动命令及其引用的所有文档：
   - Manager：`.agents/skills/apm-2-initiate-manager/SKILL.md`
   - Worker：`.agents/skills/apm-3-initiate-worker/SKILL.md`

   只读启动命令不够，必须读取它引用的指南、skill 和项目产物。跳过问候和身份注册中的重复说明。

3. 从项目产物和当前代码状态恢复工作进度。如果产物无法填补关键空白，向用户询问最小必要上下文。

4. 记录恢复事件：
   - 如果你是 Manager，在 `Tracker` 中添加 working note。
   - 如果你是 Worker，在下一份 Task Report 中说明恢复事件。

   Recover 不增加 instance number，仍然作为同一个实例继续工作。

5. 恢复职责并继续。

---

**命令结束**
