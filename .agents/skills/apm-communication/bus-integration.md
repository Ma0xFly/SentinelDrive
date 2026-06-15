# 非 APM Agent 接入 Message Bus

非 APM agent 可以通过 `.apm/bus/` 参与任务交付和报告，但它们不参与 Memory、Handoff 和 Worker tracking。

## 0. 纯中文本土化执行规范

本文件是 APM 中文本土化版本。执行时必须遵守以下规则：

- 本文件的中文说明就是实际执行口径，不需要再参考英文原文。
- 面向用户的解释、提问、分析、总结、风险说明、审查意见和下一步指令必须使用中文。
- APM 项目产物正文必须使用中文，包括 `.apm/spec.md`、`.apm/plan.md`、`AGENTS.md` 中的 APM 规则、Task Prompt、Task Log、Task Report、Handoff Log、Recovery Summary、Stage Summary、Memory Notes 和 Working Notes。
- 可以保留英文的内容仅限命令、路径、代码标识、YAML 字段、Markdown 结构标题、状态值、Agent 名称、Task ID、mermaid 语法、协议字段、库名、框架名和行业通用缩写。
- 不得为了节省上下文而删除流程约束。必须保留审批门槛、上下文边界、依赖判定、验证标准、日志格式、Message Bus、Handoff、Recovery、Tracker 和 Memory 相关规则。
- 如果发现规则缺口，用中文补足；不要回退到英文说明。

---
## 接入步骤

1. 为 agent 创建目录：

   ```text
   .apm/bus/<agent-slug>/
   ```

2. 创建文件：

   ```text
   .apm/bus/<agent-slug>/task.md
   .apm/bus/<agent-slug>/report.md
   .apm/bus/<agent-slug>/handoff.md
   ```

3. Manager 可以把 Task Prompt 写入该 agent 的 `task.md`。

4. 该 agent 完成后，把 Task Report 写入 `report.md`。

## 限制

- 非 APM agent 不写 Task Log；
- 不执行 Handoff；
- 不出现在 Worker tracking 中；
- Manager 只把它当作可通信执行者处理。
