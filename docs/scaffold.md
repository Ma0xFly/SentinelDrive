# SentinelDrive 运行时脚手架

SentinelDrive 以单台 Ubuntu 22.04 主机上的 Docker Compose 应用作为起点。初始运行时包含以下服务名：

- `reverse-proxy`：Caddy 入口，处理公共 HTTP 和 HTTPS 流量。
- `frontend`：Next.js/React 中文安全运营工作台外壳，包含客户端 session 处理。
- `backend`：FastAPI 应用，包含 `/health` 存活检查、`/ready` 依赖 readiness、MVP auth/user/intelligence/alert/manual-entry 端点、SQLAlchemy 模型和 Alembic 迁移。
- `worker`：执行 Source Connector 的 Celery worker。
- `scheduler`：派发数据源同步任务的 Celery Beat scheduler。
- `postgres`：带持久化卷的内部 PostgreSQL 数据库。
- `redis`：用于 cache、broker 和 task result 的内部 Redis。

## 本地启动

1. 将 `.env.example` 复制为 `.env`。
2. 共享环境或公网环境使用前，替换 `change-me-development-only` 值。
3. 运行 `make config-check`，验证当前环境的占位替换规则。
4. 运行 `make compose-config`，验证 Compose 渲染。
5. 运行 `make up`，构建并启动运行栈。

PostgreSQL 和 Redis 默认不发布宿主机端口。内部服务通过 Compose DNS 名称 `postgres` 和 `redis` 访问它们。

## 稳定命令

- `make compose-config`：渲染并校验 Docker Compose 配置。
- `make config-check`：校验面向部署的环境占位规则，不打印密钥。
- `make up`：构建并启动所有服务。
- `make down`：停止运行栈。
- `make backend-test`：运行后端测试。
- `make frontend-check`：运行前端生产构建检查。
- `make migrate`：应用后端 Alembic 迁移。
- `make admin-bootstrap`：使用配置的 bootstrap 凭证创建或更新初始管理员账号。
- `make sync-once`：通过 Connector runtime 触发一次 collection-only 数据源同步。
- `make process-once`：触发一次 worker collection、normalization、scoring 和 backend alert evaluation。
- `make worker`：运行 worker 命令。
- `make scheduler`：运行 scheduler 命令。

## 配置

配置来自环境变量，通常通过 `.env` 提供。模板包含数据库凭证、Redis URLs、可选 NVD API key、source feed 和 endpoint list、初始管理员 bootstrap 值、source enablement、sync interval、source timeout、readiness timeout、rate limit、retry count、raw retention、worker log/concurrency 设置和 reverse proxy 设置的安全示例。

`APP_ENV=development` 是本地默认值。生产类值（`production`、`prod` 或 `staging`）要求替换后端密钥、数据库凭证、管理员 bootstrap 值和部署 host 设置中的不安全占位。

`NVD_API_KEY` 是可选项，可以留空。未设置时，source config loader 会应用更严格的未认证 NVD 限速。

`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 设置时使用 JSON list。`SOURCE_VENDOR_ADVISORY_ENDPOINTS` 留空时使用内置代表性厂商 seed list。

后端将 `/health` 限定为进程存活检查。使用 `/ready` 验证 PostgreSQL 与 Redis 连通性，且不暴露配置凭证。受保护 API 路由使用 `POST /auth/login` 签发的 `Authorization: Bearer <token>`；签名 key 来自 `APP_SECRET_KEY`。情报路由暴露规范化搜索/详情数据，使用有界分页和安全 metadata 脱敏。告警路由评估确定性后端触发规则，并支持告警复核/状态更新。人工录入路由将分析人员提交的条目保存到既有 raw 和 normalized intelligence 表。

前端只接收 `NEXT_PUBLIC_API_BASE_URL`；浏览器可见配置不得包含密钥。MVP session 中，前端登录流程只把已签发 bearer token 存入 browser local storage，并在 logout 或 `401` 响应后清除。

## Connector 边界

源特定采集逻辑属于 worker connector package。运行时契约位于 `worker/sentineldrive_worker/connectors/`，并从 `worker/app/connectors/` 重新导出以保持兼容。Raw-to-normalized mapping 和 deduplication 位于 `worker/sentineldrive_worker/normalization/`。固定规则风险评分位于 `worker/sentineldrive_worker/scoring/`。Search 和 alert behavior 在后端保持跨数据源复用。

## 当前实现说明

Worker runtime 包含 contracts、NVD、CISA KEV、RSS、vendor advisory metadata、sample Connectors、raw-to-normalized intelligence deduplication、fixed-rule risk scoring 和 scheduled collect-normalize-score processing。Alerting 实现在后端 service layer，可在 worker processing 后通过 `make process-once` 执行。

Backend 当前提供 `/health`、`/ready`、MVP auth/user/intelligence/alert/manual-entry 端点、audit logging、intelligence search/detail、核心持久化 schema、migrations 和 admin/evaluate-alert scripts。

Frontend 当前提供受保护中文工作台路由 `/`、`/intelligence/[id]`、`/alerts`、`/sources`、`/manual-entry` 和 `/user`，并提供共享 API helpers 与可复用 loading/error/empty states。

这些元素稳定了服务名、build context、运维命令、API 集成和 operations-console layout，为后续更大规模领域实现提供边界。
