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

- Backend tests 全部通过；warning 需要审查，但除非 CI 配置为失败，否则不阻断。
- Worker tests 全部通过，且不依赖 live network。
- Frontend `npm run check` 完成生产 `next build`。
- Frontend `npm run e2e` 启动本地 Next.js server，并用确定性的 mocked API responses 完成 Playwright 浏览器工作流。
- Frontend `npm audit --omit=dev` 不报告生产依赖漏洞。
- `make config-check` 校验当前环境且不打印密钥值。
- `make compose-config` 成功渲染 Compose 文件。
- `git diff --check` 不报告 whitespace errors。

`make backend-test` 和 `make frontend-check` 保留为操作者使用的 Docker Compose wrappers。在非 Docker CI 或本地验证中，优先使用上方直接命令，以便按 surface 隔离失败。

## 测试策略

### Backend Unit and API Tests

当前后端 surface：

- FastAPI app：`backend/app/main.py`。
- 已实现路由：`GET /health`、`GET /ready`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`、`GET /users`、`POST /users`、`PATCH /users/{user_id}/status`、`GET /intelligence`、`GET /intelligence/{intelligence_id}`、`POST /alerts/evaluate`、`GET /alerts`、`GET /alerts/{alert_id}`、`PATCH /alerts/{alert_id}/status`、`GET /sources`、`GET /sources/{source_id}`、`GET /sources/jobs`、`GET /sources/pipeline/status`、`POST /sources/pipeline/trigger`、`PATCH /sources/{source_id}/status`、`GET /exports/intelligence.csv`、`GET /exports/intelligence/{intelligence_id}/markdown`、`GET /exports/alerts.csv`、`GET /exports/summary.pdf`、`POST /manual-entries`、`GET /manual-entries`、`GET /manual-entries/{entry_id}` 和 `PATCH /manual-entries/{entry_id}`。
- SQLAlchemy models：`backend/app/models/`。
- Alembic migrations：`backend/migrations/`。
- 命令：`make backend-test`。

后端测试当前验证 health/readiness、settings safety、model metadata、约束和索引、password hashing、token-protected auth flows、user create/list/status updates、intelligence search filters/pagination/sorting/detail/sensitive metadata redaction、alert trigger evaluation、alert filters、alert status audit logging、source status/job filters and redaction、source status audit logging、CSV/Markdown/PDF export auth/filtering/redaction、manual entry validation/persistence/dedup/status updates、audit event creation、failure paths、admin bootstrap behavior 和 migration contents。Live migration execution 需要运行中的 PostgreSQL 服务。

后续后端测试应覆盖新增 API 的 request validation、error responses、date range filters、扩展导出格式/筛选，以及真实 API workflow 下的持久化行为。

### Pipeline and Connector Tests

除非明确要求 live validation，Connector tests 必须 mock 外部网络来源。

当前 worker tests 位于 `worker/tests/`，覆盖 connector runtime contract、NVD/CISA KEV mocked HTTP behavior、RSS/Atom feed parsing、vendor advisory metadata collection、in-memory failure cases、SQLite-backed persistence、raw-to-normalized deduplication、fixed-rule scoring 和完整 worker processing pipeline through scoring。

必须覆盖：

- 公共来源 fetch 成功和失败。
- Timeout 与 retry。
- Rate limiting，包括 `NVD_API_KEY` 为空时的未认证 NVD 行为。
- 使用 mocked source responses 的可配置 RSS feeds 和 vendor endpoints。
- 合理体积下 API/RSS JSON 或 XML raw persistence。
- HTML/PDF 默认 metadata-only retention。
- Normalization 到共享 threat intelligence structures。
- 同一输入重复处理、多个来源报告同一 CVE 时的确定性 deduplication。
- 无法规范化 raw rows 的 failure status 和 error updates。
- Fixed scoring boundaries、missing-CVSS fallback、KEV、PoC、remote、authentication、source confidence、multi-vendor/common component、vehicle-critical component 和幂等 metadata update。
- Full worker processing orchestration 的成功、重复/幂等运行、部分 source failure、no-work cases 和可选 injected alert evaluator summaries。
- Alert trigger behavior 保留在 backend service layer；connector 和 scoring tests 只验证 alert evaluation 需要的 scoring metadata 确定。
- Source attribution fields。

聚焦 worker pipeline/scoring 检查：

```bash
.venv/bin/python -m pytest worker/tests/test_processing_pipeline.py -q
.venv/bin/python -m pytest worker/tests/test_scoring_service.py -q
```

### Frontend Checks

当前前端 surface：

- Next.js app：`frontend/`。
- 中文工作台页面：`frontend/app/`。
- Client-side session provider 和共享 API helpers：`frontend/app/components/`、`frontend/lib/`。
- Build 命令：`make frontend-check` 或 `cd frontend && npm run check`。
- Browser workflow 命令：`cd frontend && npm run e2e`。

新工作站或 CI image 上先安装 Playwright 浏览器：

```bash
cd frontend && npx playwright install chromium
```

`frontend/e2e/operator-workflows.spec.js` 中的 Playwright suite 会启动本地 Next.js app，并只在浏览器中 mock `/api/*` responses。它不采集 live sources，不需要后端凭证，也不需要 PostgreSQL/Redis/Celery。

当前浏览器工作流覆盖：

- 登录保护工作台访问。
- Intelligence list、detail navigation、source attribution 和 CSV download handling。
- Manual-entry validation failure 和 successful submission。
- Source pipeline status display、`POST /sources/pipeline/trigger` 和独立 `POST /alerts/evaluate` control behavior。
- Alert detail review、linked intelligence access 和 status update。

剩余前端检查应覆盖 logout/session-expired behavior、API failure rendering、responsive layout，以及 Docker services 可用时通过 reverse proxy 的 live-stack smoke validation。

### Compose and Deployment Validation

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

`make compose-config` 只验证渲染配置。完整容器启动、reverse-proxy routing、Docker 内 PostgreSQL/Redis readiness 和 worker/scheduler runtime behavior 需要 Docker daemon，应在平台或部署验证阶段执行。

完整 runtime deployment smoke test 见 `docs/qa/compose-deployment-verification.md`。

### Documentation Validation

验证：

- 文档链接指向存在的文件。
- 服务名匹配 `docker-compose.yml`。
- 命令名匹配 `Makefile`。
- 环境变量匹配 `.env.example` 和 `docker-compose.yml`。
- 未实现或延期行为标注清楚。
- 不包含真实 secrets、tokens、private URLs 或 credentials。

## 覆盖映射

| 验收区域 | 当前自动化覆盖 | 主要文件 |
| --- | --- | --- |
| Authentication/session/user basics | 登录成功/失败、受保护路由拒绝、logout audit、用户创建/列表/状态、admin-only rejection、重复/缺失用户失败路径、bootstrap 修复/创建 | `backend/tests/test_auth.py`, `backend/tests/test_admin_bootstrap.py` |
| Manual entry | Auth requirement、validation、create、duplicate handling、list/detail/status update、dedup collision | `backend/tests/test_manual_entries.py` |
| Intelligence search/detail | Auth requirement、normalized-field filters、source attribution、pagination、sorting、safe metadata/scoring/alert references、deterministic 404 | `backend/tests/test_intelligence_api.py` |
| Source connectors and persistence | Connector contract、disabled/unimplemented handling、cursor/retry/timeout/rate-limit、source status/job logs、raw persistence、metadata-only HTML/PDF retention、one-source failure isolation | `worker/tests/test_connector_contracts.py`, `worker/tests/test_collection_persistence.py` |
| Processing pipeline | Collect-normalize-score orchestration、stage summaries、repeated-run idempotency、source failure isolation、no-work output、injected alert summary seam | `worker/tests/test_processing_pipeline.py` |
| Normalization/dedup/source attribution | NVD/CISA same-CVE merge、same raw row idempotency、vendor URL dedup、manual raw normalization、malformed raw failure、token redaction | `worker/tests/test_normalization_pipeline.py` |
| Risk scoring | Risk boundaries、missing-CVSS fallback、KEV/PoC/remote/auth/vehicle-critical signals、multi-vendor/common-component scoring、idempotent metadata update、scoring error redaction | `worker/tests/test_scoring_service.py` |
| Alert generation/status updates | Rule creation、duplicate prevention、burst detection、targeted evaluation、backend script invocation、auth、list/detail filters/sorting/redaction、status audit、note preservation/clearing、deterministic 404 | `backend/tests/test_alerts_api.py`, `backend/tests/test_alert_evaluation_script.py` |
| Source status/job logs | Auth、safe source state/job summary、retry/skipped filters、error redaction、status audit、deterministic 404、SQL filter metadata derivation | `backend/tests/test_sources_api.py` |
| Exports | Auth requirement、intelligence CSV filters/redacted URLs、Markdown source/alert content、alert CSV filters/redacted notes、invalid alert filter error、PDF redaction、missing Markdown 404 | `backend/tests/test_exports_api.py` |
| Frontend build/workbench routes | 生产构建覆盖当前 routes `/`、`/alerts`、`/intelligence/[id]`、`/manual-entry`、`/sources` 和 `/user` | `frontend/package.json`, `frontend/app/`, `frontend/lib/` |
| Frontend browser workflows | Playwright 覆盖登录保护、intelligence list/detail/export、manual-entry、source processing controls、alert evaluation 和 alert status update | `frontend/e2e/operator-workflows.spec.js`, `frontend/playwright.config.js` |
| Configuration/migrations | Settings/env validation、placeholder production rejection、migration contents、model metadata/enums/indexes/constraints | `backend/tests/test_settings.py`, `backend/tests/test_migrations.py`, `backend/tests/test_models.py`, `scripts/config-check.sh` |

## 残余风险

- Frontend browser coverage 使用 mocked `/api/*` responses。它验证 UI behavior 和 endpoint wiring，但不能证明 live backend、reverse-proxy、PostgreSQL、Redis、worker 或 scheduler integration。
- Browser tests 尚未覆盖 logout/session-expired behavior、mocked API failure rendering、responsive layout 或 generated PDF visual rendering。
- Docker runtime validation 不由 unit tests 或 `make compose-config` 覆盖；完整 startup 与 reverse-proxy/backend/frontend/worker/scheduler 交互需要 Docker daemon。
- NVD、CISA KEV、RSS 和厂商公告端点的 live source validation 有意排除在自动化测试外。Connector suites 使用 mocked responses，避免网络波动和凭证要求。
- Live PostgreSQL migration execution 不属于 backend unit suite；当前测试检查 migration contents 和 model metadata。部署验证期间应在隔离 PostgreSQL 实例上运行迁移。

## QA Checklists

- [自动化测试覆盖总结](qa/coverage-pass-summary.md)
- [Connector 行为 Checklist](qa/connector-checklist.md)
- [API 集成 Checklist](qa/api-integration-checklist.md)
- [前端页面 Checklist](qa/frontend-page-checklist.md)
- [Docker Compose Checklist](qa/compose-checklist.md)
- [安全与密钥 Checklist](qa/security-secrets-checklist.md)
