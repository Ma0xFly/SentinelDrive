# 非 APM Agent 接入 Message Bus

非 APM agent 可以通过 `.apm/bus/` 参与任务交付和报告，但它们不参与 Memory、Handoff 和 Worker tracking。

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
