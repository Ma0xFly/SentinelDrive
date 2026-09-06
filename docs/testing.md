# 测试与 QA 指南

本文定义 SentinelDrive 的测试策略和 QA 流程。

## CI-Ready 命令清单

除非命令显式切换目录，否则从仓库根目录运行：

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest worker/tests -q
cd frontend && npm run check
cd frontend && npm run e2e
cd frontend && npm audit --omit=dev
make config-check
make compose-config
git diff --check
```

通过标准：

- 后端测试全部通过；warning 需要审查，但除非 CI 配置为失败，否则不阻断。
- Worker 测试全部通过，且不依赖真实网络。
- 前端 `npm run check` 完成生产 `next build`。
- 前端 `npm run e2e` 启动本地 Next.js server，并用确定性的 mocked API 响应完成 Playwright 浏览器工作流。
- 前端 `npm audit --omit=dev` 不报告生产依赖漏洞。
- `make config-check` 校验当前环境且不打印密钥值。
- `make compose-config` 成功渲染 Compose 文件。
- `git diff --check` 不报告空白字符错误。

`make backend-test` 和 `make frontend-check` 保留为操作者使用的 Docker Compose 包装命令。在非 Docker CI 或本地验证中，优先使用上方直接命令，以便按服务面隔离失败。

## 测试策略

### 后端单元与 API 测试

当前后端测试面：

- FastAPI app：`backend/app/main.py`。
- 已实现路由：`GET /health`、`GET /ready`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`、`GET /users`、`POST /users`、`PATCH /users/{user_id}/status`、`GET /intelligence`、`GET /intelligence/{intelligence_id}`、`POST /intelligence/ingest`、`POST /alerts/evaluate`、`GET /alerts`、`GET /alerts/{alert_id}`、`PATCH /alerts/{alert_id}/status`、`GET /sources`、`GET /sources/{source_id}`、`GET /sources/jobs`、`GET /sources/pipeline/status`、`POST /sources/pipeline/trigger`、`PATCH /sources/{source_id}/status`、`GET /exports/intelligence.csv`、`GET /exports/intelligence/{intelligence_id}/markdown`、`GET /exports/alerts.csv`、`GET /exports/summary.pdf`、`POST /manual-entries`、`GET /manual-entries`、`GET /manual-entries/{entry_id}` 和 `PATCH /manual-entries/{entry_id}`。
- SQLAlchemy models：`backend/app/models/`。
- Alembic migrations：`backend/migrations/`。
- 命令：`make backend-test`。

后端测试当前验证：健康/就绪检查、settings 安全性、model 元数据、约束和索引、密码哈希、token 保护的认证流程、用户创建/列表/状态更新、情报搜索筛选/分页/排序/详情/敏感 metadata 脱敏、情报 ingest 的鉴权/字段校验/敏感文本拒绝/CVE 与外部编号去重合并/审计写入、告警触发评估、告警筛选、告警状态审计日志、数据源状态/任务日志筛选与脱敏、数据源状态审计日志、CSV/Markdown/PDF 导出的鉴权/筛选/脱敏、人工录入校验/持久化/去重/状态更新、审计事件创建、失败路径、管理员引导行为和迁移内容。真实迁移执行需要运行中的 PostgreSQL 服务。

后续后端测试应覆盖新增 API 的请求校验、错误响应、日期范围筛选、扩展导出格式/筛选，以及真实 API 工作流下的持久化行为。

### 流水线与连接器测试

除非明确要求真实联网验证，连接器测试必须 mock 外部网络数据源。

当前 worker 测试位于 `worker/tests/`，覆盖连接器运行时契约、NVD/CISA KEV 的 mocked HTTP 行为、RSS/Atom feed 解析、厂商公告 metadata 采集、内存态失败用例、SQLite 持久化、raw 到规范化的去重、固定规则评分，以及贯穿评分的完整 worker 处理流水线。

必须覆盖：

- 公共数据源抓取的成功和失败。
- 超时与重试。
- 限速，包括 `NVD_API_KEY` 为空时 NVD 的未认证行为。
- 使用 mocked 响应的可配置 RSS feeds 和厂商端点。
- 合理体积下 API/RSS JSON 或 XML raw 持久化。
- HTML/PDF 默认 metadata-only 留存。
- 规范化到共享的威胁情报结构。
- 同一输入重复处理、多个来源报告同一 CVE 时的确定性去重。
- 无法规范化 raw 记录时的失败状态和错误更新。
- 固定评分边界、缺失 CVSS 回退、KEV、PoC、远程利用、身份认证、数据源可信度、多厂商/通用组件、车控关键组件信号，以及幂等 metadata 更新。
- 完整 worker 处理编排的成功、重复/幂等运行、部分数据源失败、无任务场景和可选注入的告警评估摘要。
- 告警触发行为保留在后端服务层；连接器和评分测试只验证告警评估所需的评分 metadata 确定性。
- 数据源归属字段。

聚焦 worker 流水线/评分检查：

```bash
.venv/bin/python -m pytest worker/tests/test_processing_pipeline.py -q
.venv/bin/python -m pytest worker/tests/test_scoring_service.py -q
```

### 前端检查

当前前端测试面：

- Next.js app：`frontend/`。
- 中文工作台页面：`frontend/app/`。
- 客户端 session provider 和共享 API helpers：`frontend/app/components/`、`frontend/lib/`。
- 构建命令：`make frontend-check` 或 `cd frontend && npm run check`。
- 浏览器工作流命令：`cd frontend && npm run e2e`。

新工作站或 CI 镜像上先安装 Playwright 浏览器：

```bash
cd frontend && npx playwright install chromium
```

`frontend/e2e/operator-workflows.spec.js` 中的 Playwright 套件会启动本地 Next.js app，并只在浏览器中 mock `/api/*` 响应。它不采集真实数据源，不需要后端凭证，也不需要 PostgreSQL/Redis/Celery。

当前浏览器工作流覆盖：

- 登录保护的工作台访问。
- 情报列表、详情导航、数据源归属和 CSV 下载处理。
- 外部/AI ingest 记录在情报列表与详情页的渲染：CVE、风险等级、`external_ingest` 标签、来源归属和去重键。
- 人工录入的校验失败和成功提交。
- 数据源流水线状态展示、`POST /sources/pipeline/trigger` 和独立的 `POST /alerts/evaluate` 控制行为。
- 告警详情复核、关联情报访问和状态更新。

剩余前端检查应覆盖登出/session 过期行为、API 失败渲染、响应式布局，以及 Docker 服务可用时经反向代理的真实栈冒烟验证。

### Compose 与部署验证

使用：

```bash
make compose-config
make config-check
make up
make logs
make down
```

验证：

- Compose 成功渲染。
- `reverse-proxy` 发布预期宿主机端口。
- `postgres`、`redis`、`worker` 和 `scheduler` 保持内部访问。
- `frontend`、`backend`、`worker` 和 `scheduler` 接收预期环境变量。
- 生产类占位密钥校验失败时不打印密钥值。
- PostgreSQL、Redis 和 Caddy 的持久化 volumes 存在。

`make compose-config` 只验证渲染配置。完整容器启动、反向代理路由、Docker 内 PostgreSQL/Redis 就绪和 worker/scheduler 运行时行为需要 Docker daemon，应在平台或部署验证阶段执行。

完整运行时部署冒烟测试见 `docs/qa/compose-deployment-verification.md`。

### 文档验证

验证：

- 文档链接指向存在的文件。
- 服务名匹配 `docker-compose.yml`。
- 命令名匹配 `Makefile`。
- 环境变量匹配 `.env.example` 和 `docker-compose.yml`。
- 未实现或延期行为标注清楚。
- 不包含真实 secrets、tokens、私有 URL 或凭证。

## 覆盖映射

| 验收区域 | 当前自动化覆盖 | 主要文件 |
| --- | --- | --- |
| 认证/session/用户基础 | 登录成功/失败、受保护路由拒绝、登出审计、用户创建/列表/状态、仅管理员操作拒绝、重复/缺失用户失败路径、bootstrap 修复/创建 | `backend/tests/test_auth.py`, `backend/tests/test_admin_bootstrap.py` |
| 人工录入 | 鉴权要求、校验、创建、重复条目处理、列表/详情/状态更新、去重冲突 | `backend/tests/test_manual_entries.py` |
| 情报搜索/详情 | 鉴权要求、规范化字段筛选、数据源归属、分页、排序、安全 metadata/评分/告警引用、确定性 404 | `backend/tests/test_intelligence_api.py` |
| 数据源连接器与持久化 | 连接器契约、停用/未实现处理、游标/重试/超时/限速、数据源状态/任务日志、raw 持久化、metadata-only 的 HTML/PDF 留存、单数据源失败隔离 | `worker/tests/test_connector_contracts.py`, `worker/tests/test_collection_persistence.py` |
| 处理流水线 | 采集-规范化-评分编排、阶段摘要、重复运行幂等、数据源失败隔离、无任务输出、注入的告警摘要接缝 | `worker/tests/test_processing_pipeline.py` |
| 规范化/去重/数据源归属 | NVD/CISA 同一 CVE 合并、同一 raw 记录幂等、厂商 URL 去重、人工 raw 规范化、外部 ingest raw 规范化与去重键对齐、损坏 raw 失败、token 脱敏 | `worker/tests/test_normalization_pipeline.py` |
| 外部/AI ingest 写入路径 | 鉴权要求、字段校验、敏感文本拒绝、CVE 与外部编号去重合并、脱敏、审计写入 | `backend/tests/test_intelligence_ingest_api.py` |
| 风险评分 | 风险边界、缺失 CVSS 回退、KEV/PoC/远程/认证/车控关键信号、多厂商/通用组件评分、幂等 metadata 更新、评分错误脱敏 | `worker/tests/test_scoring_service.py` |
| 告警生成/状态更新 | 规则创建、重复预防、突发检测、定向评估、后端脚本调用、鉴权、列表/详情筛选/排序/脱敏、状态审计、备注保留/清除、确定性 404 | `backend/tests/test_alerts_api.py`, `backend/tests/test_alert_evaluation_script.py` |
| 数据源状态/任务日志 | 鉴权、安全的数据源状态/任务摘要、重试/跳过筛选、错误脱敏、状态审计、确定性 404、SQL 筛选 metadata 推导 | `backend/tests/test_sources_api.py` |
| 导出 | 鉴权要求、情报 CSV 筛选/URL 脱敏、Markdown 数据源/告警内容、告警 CSV 筛选/备注脱敏、无效告警筛选错误、PDF 脱敏、缺失 Markdown 404 | `backend/tests/test_exports_api.py` |
| 前端构建/工作台路由 | 生产构建覆盖当前路由 `/`、`/alerts`、`/intelligence/[id]`、`/manual-entry`、`/sources` 和 `/user` | `frontend/package.json`, `frontend/app/`, `frontend/lib/` |
| 前端浏览器工作流 | Playwright 覆盖登录保护、情报列表/详情/导出、外部/AI ingest 记录渲染、人工录入、数据源处理控制、告警评估和告警状态更新 | `frontend/e2e/operator-workflows.spec.js`, `frontend/playwright.config.js` |
| 配置/迁移 | Settings/env 校验、生产占位拒绝、迁移内容、model metadata/枚举/索引/约束 | `backend/tests/test_settings.py`, `backend/tests/test_migrations.py`, `backend/tests/test_models.py`, `scripts/config-check.sh` |

## 残余风险

- 前端浏览器覆盖使用 mocked `/api/*` 响应。它验证 UI 行为和端点接线，但不能证明真实 backend、反向代理、PostgreSQL、Redis、worker 或 scheduler 集成。
- 浏览器测试尚未覆盖登出/session 过期行为、mocked API 失败渲染、响应式布局或生成的 PDF 视觉渲染。
- Docker 运行时验证不由单元测试或 `make compose-config` 覆盖；完整启动与 reverse-proxy/backend/frontend/worker/scheduler 交互需要 Docker daemon。
- NVD、CISA KEV、RSS 和厂商公告端点的真实数据源验证有意排除在自动化测试外。连接器套件使用 mocked 响应，避免网络波动和凭证要求。
- 真实 PostgreSQL 迁移执行不属于后端单元套件；当前测试检查迁移内容和 model 元数据。部署验证期间应在隔离的 PostgreSQL 实例上运行迁移。

## QA 清单

- [自动化测试覆盖总结](qa/coverage-pass-summary.md)
- [连接器行为清单](qa/connector-checklist.md)
- [API 集成清单](qa/api-integration-checklist.md)
- [前端页面清单](qa/frontend-page-checklist.md)
- [Docker Compose 清单](qa/compose-checklist.md)
- [安全与密钥清单](qa/security-secrets-checklist.md)
