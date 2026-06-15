---
name: apm-5-check-reports
description: 将 Task Report 交付给 APM Manager。
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
# APM 1.0.1 - Manager 检查报告命令

检查 Report Bus 中是否有 Worker 提交的 Task Report。如果你是 Planner、Worker 或非 APM agent，请简要拒绝并停止。

参数：可选 `[agent-id ...]`。如果提供参数，只检查指定 Workers 的 Report Bus；如果不提供参数，扫描所有 Report Bus。

**流程：**

1. 判断扫描范围：
   - 如果 `(the text provided by the User after the command invocation, if any)` 有内容，按 `.agents\skills\apm-communication\SKILL.md` 解析每个 agent-id，并批量读取对应 Report Bus。
   - 如果没有参数，进入第 2 步。

2. 扫描所有 Report Bus。使用一次终端命令读取所有非空文件，例如：

   ```bash
   for f in .apm/bus/*/report.md; do [ -s "$f" ] && echo "=== $f ===" && cat "$f"; done
   ```

   在 Windows PowerShell 中使用等价命令。如果没有待处理报告，告知用户并等待下一次调用。

3. 对每个有内容的 Report Bus，按 `.codex\apm-guides\task-review.md` 执行 Task Review。

---

**命令结束**
