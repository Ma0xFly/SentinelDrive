---
stage: 9
task: 2
agent: backend-agent
log_path: ".apm/memory/stage-09/task-09-02.log.md"
has_dependencies: false
---

# Task 9.2 - 威胁统计聚合 API

## 背景

Stage 9 为前端 Pro v6 迁移与威胁态势仪表盘（用户确认：图表统计展示，非 OKR 管理）。本任务提供仪表盘数据源，由 Frontend Agent 的 Task 9.4 消费，与前端任务并行，互不阻塞。

## Workspace

- 从 `main` 创建功能分支：`feat/stats-overview-api`
- 只提交本任务自身产出（后端代码 + 测试）；`.apm/`、`web3开发/`、`frontend*` 等无关路径不得提交

## 目标

新增一个认证保护的轻量统计聚合端点，单次请求返回仪表盘所需的全部统计数据。

## 实现要求

1. **端点**：在 `backend/app/api/routes/` 新增 stats 路由（`prefix="/stats"`，与既有 router 风格一致），暴露 `GET /stats/overview`（经反代即 `/api/stats/overview`）。复用既有认证依赖，未认证返回 401。
2. **响应结构**（五个块，schema 定义在 `backend/app/api/schemas/`）：
   - `totals`：威胁情报总数、近 24 小时新增、近 7 天新增
   - `by_intelligence_type` / `by_severity` / `by_risk_level` / `by_processing_status`：分布计数
   - `trend`：近 30 天按天新增情报（日期 + 计数，缺失日期补零）
   - `alerts`：告警总数、按状态分布、近 30 天按天新增趋势
   - `sources`：启用数据源数、按关联情报数量排序的来源 Top 10
3. **实现约束**：SQLAlchemy 聚合查询（GROUP BY / 日期截断），不引入物化视图、不新增缓存基础设施、不做任意维度自由聚合参数；默认时间窗 30 天用模块常量（如需配置走既有 settings 模式）；适配 4 核/4 GB 单机。
4. **口径一致性**：计数与筛选语义必须与既有情报/告警列表 API 一致（同一状态过滤定义）；不暴露任何敏感字段或原始 payload。
5. **空库行为**：空库返回全零/空列表的合法结构，不报错。
6. **测试**：在 `backend/tests/` 按既有风格新增聚焦测试，覆盖：未认证 401、空库零值、多类型/严重度分布计数、趋势补零与边界日期、告警状态分布、来源 Top N 排序。注意既有约定：pytest 配置 `pythonpath = backend worker`（backend 在前）。

## 明确排除

- 不修改前端、worker、docker-compose、迁移（如无新表则不需要迁移；本任务只读聚合，不应建新表）
- 不做 AI 分析、自定义评分、导出变更等范围外能力
- 不提交真实密钥

## 验收清单

- [ ] 未认证 401；空库返回零值结构
- [ ] 五个数据块齐全且口径与列表 API 一致
- [ ] 新增测试通过；既有后端测试无回归
- [ ] 无敏感字段泄露；响应体大小可控（趋势/分布条目数有上界）

## 报告要求

完成后写入任务日志 `.apm/memory/stage-09/task-09-02.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/backend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。如测试环境无法运行（已知 `.venv` 缺 fastapi/httpx 且离线安装失败的历史问题），如实记录并在 Issues 中说明。
