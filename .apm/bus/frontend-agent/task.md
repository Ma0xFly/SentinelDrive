---
stage: 9
task: 4
agent: frontend-agent
log_path: ".apm/memory/stage-09/task-09-04.log.md"
has_dependencies: true
---

# Task 9.4 - 威胁态势仪表盘

## 背景

9.2 的 `GET /stats/overview` 已合并（main @ `bfbbc81`），9.3 四个核心页面已合并。本任务实现「态势总览」仪表盘首页，替换占位页——这是本期前端迁移的最后一个新功能页面。后续 9.5（E2E 移植与部署切换）不在本任务范围。

## Workspace

- worktree 隔离（沿用 9.3 模式）：`git worktree add .apm/worktrees/frontend-pro-dashboard -b feat/frontend-pro-dashboard main`，在 worktree 内重新 `pnpm install` 后开发与提交
- `.apm/` 日志与报告写主检出绝对路径 `/home/myx/Projects/SentinelDrive/.apm/...`
- 提交信息 `type: description`；只提交 `frontend-pro/` 下自身产出

## 依赖上下文

- **`/stats/overview` 响应结构**（`backend/app/api/schemas/stats.py`）：
  - `totals`：`total_intelligence` / `new_last_24_hours` / `new_last_7_days`
  - `by_intelligence_type` / `by_severity` / `by_risk_level` / `by_processing_status`：`dict[str, int]`，**枚举键全量补零**
  - `trend`：**固定 30 条** `{date, count}`，最旧→最新，`date` 序列化为字符串
  - `alerts`：`total` / `by_status`（枚举补零）/ `trend`（30 条）
  - `sources`：`enabled` / `top`（≤10 项 `{id, name, intelligence_count}`，**含禁用来源**，按去重关联情报数排序）
- 枚举键为原始值，中文标签与徽章色用 `src/constants/labels.ts` 映射
- `src/services/` 尚无 stats 域（9.1 手写契约层早于 9.2 端点）：需新增 `src/services/stats/`（typings + 请求函数，结构对齐既有域，字段对齐后端 schema），不改动其他域
- **真实联调环境可复用**（9.3 遗留）：postgres/redis/backend 容器运行中、`backend/.venv` 已重建（主检出）、管理员 `admin@example.test`（密码为 compose 默认开发占位值）。**只复用：不得 down/restart 容器、不得修改 `docker-compose.yml`**。库内已有少量情报与真实告警；图表需要更多数据可用 `/intelligence/ingest` 注入本地模拟数据（注明仅本地开发库）

## 实现要求

1. 替换 `src/pages/dashboard/index.tsx` 占位为真实仪表盘；路由「态势总览」已存在（`config/routes.ts`）。
2. 统计卡片行：情报总数、近 7 天新增、告警总数、启用来源——antd Statistic 卡片，信息密度优先、视觉克制。
3. 图表（消费上方五块数据）：近 30 天情报新增趋势（折线或面积）、严重度分布、情报类型占比、告警状态分布、来源情报覆盖 Top 10（横向条形或紧凑列表）。
4. 图表库：`@ant-design/charts`（Plot 系）或等价轻量方案；保持构建产物体积可控，仪表盘图表用动态 import；不做地图、3D、营销大屏化效果与装饰动画。
5. 加载/错误/空状态全中文；空库（全零数据）渲染正常不报错；提供手动刷新。
6. 除导航必要微调外，不改动 9.3 已交付页面；`src/services/` 既有域结构不动。

## 明确排除

- 不做 AI 对话、OKR 实体、地图/3D；不删旧 `frontend/`；不改 `docker-compose.yml`、`backend/`、旧 `frontend/`
- 发现后端契约缺口记录到报告 Issues，不顺手改后端
- 不提交真实密钥

## 验收清单

- [ ] `pnpm build`、`pnpm lint`、`pnpm test` 全绿
- [ ] 真实后端走查：仪表盘渲染真实统计（截图确认），数值与 `curl /stats/overview` 口径一致
- [ ] 枚举键中文映射与 `labels.ts` 一致；空态/错误态/加载态齐全
- [ ] 主检出 `docker-compose.yml`、`backend/`、旧 `frontend/` 零改动；容器栈保持运行
- [ ] 任务日志与报告按 APM 规范写入

## 报告要求

完成后写入 `/home/myx/Projects/SentinelDrive/.apm/memory/stage-09/task-09-04.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `/home/myx/Projects/SentinelDrive/.apm/bus/frontend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。合并与 worktree 清理由 Manager 负责。
