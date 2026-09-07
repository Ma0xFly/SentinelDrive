# 本地开发指南

本文档说明当前 backend、frontend、Connector runtime、source Connectors 和 scheduler 的本地开发方式。

## 前置条件

- Docker Engine 与 Docker Compose v2。
- GNU Make。
- 能访问仓库根目录。

## 环境准备

```bash
cp .env.example .env
make config-check
```

`APP_ENV=development` 允许使用 `.env.example` 中的安全本地占位值。进入共享环境或公网环境前，必须替换 `APP_SECRET_KEY`、`POSTGRES_PASSWORD`、`DATABASE_URL`、`ADMIN_BOOTSTRAP_EMAIL` 和 `ADMIN_BOOTSTRAP_PASSWORD` 等占位值。真实密钥不得进入 Git。

`NVD_API_KEY` 是可选项。留空时使用未认证 NVD 访问，配置加载器会自动使用更严格限速。

`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 使用 JSON list。示例必须公开且安全；当 `SOURCE_ENABLED_VENDOR_ADVISORIES=true` 且 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 为空时，会使用内置代表性厂商 seed list。

前端静态托管，API base path 固定为 `/api`，由反向代理转发到后端。不要创建任何浏览器可见的密钥环境变量。

## 脚手架验证

```bash
make config-check
make compose-config
```

`make config-check` 校验面向部署的占位规则，不打印密钥值。`make compose-config` 使用 `.env` 渲染 `docker-compose.yml` 并校验 Compose 语法。

## 启动与停止

```bash
make up
make logs
make down
```

公共入口是 `reverse-proxy`，宿主机端口来自 `REVERSE_PROXY_HTTP_PORT` 和 `REVERSE_PROXY_HTTPS_PORT`。内部服务通过 Compose DNS 名称互相访问。

## 服务地图

| Service | 当前职责 | 公网暴露 |
| --- | --- | --- |
| `reverse-proxy` | Caddy 入口，处理 `/` 和 `/api/*` | 宿主机 HTTP/HTTPS 端口 |
| `frontend` | Next.js 中文运营工作台，包含客户端 session 和共享 API helper | 仅内部 `expose: 3000` |
| `backend` | FastAPI API，包含健康检查、认证/用户、情报搜索/详情、告警、数据源状态、任务日志、导出和 Alembic schema | 仅内部 `expose: 8000` |
| `worker` | Celery worker，执行 Source Connector 和处理管道 | 内部 |
| `scheduler` | Celery Beat，派发数据源同步/处理任务 | 内部 |
| `postgres` | PostgreSQL 存储 | 内部 |
| `redis` | Redis cache/broker/result backend | 内部 |

## 常用命令

```bash
make backend-test
make frontend-check
make migrate
make admin-bootstrap
make sync-once
make process-once
make worker
make scheduler
```

`make migrate` 通过 backend 容器应用 Alembic 迁移。`make admin-bootstrap` 创建或更新初始管理员，只保存密码哈希，并在创建或激活管理员时写入用户变更审计事件。`make sync-once` 只执行采集。`make process-once` 执行 worker 采集、规范化、评分，然后运行后端告警评估。

Worker Celery 入口包括 `sentineldrive.sync_sources`、`sentineldrive.normalize_raw_intelligence`、`sentineldrive.score_threat_intelligence` 和 `sentineldrive.process_pipeline`。

## 直接运行测试与构建

只验证某个局部面时，可绕过 Compose wrapper：

```bash
cd backend
../.venv/bin/python -m pytest tests -q
```

```bash
.venv/bin/python -m pytest worker/tests -q
```

```bash
cd frontend
pnpm build
pnpm audit --omit=dev
```

文档或配置变更后，从仓库根目录运行：

```bash
make config-check
make compose-config
git diff --check
```

`pnpm build` 通过 `max build` 产出静态文件。`make frontend-check` 等价于 `cd frontend && pnpm build`。Worker 测试会 mock 外部来源，不需要真实 NVD、CISA、RSS 或厂商网络访问。

## 数据库迁移

后端持久化层使用 `backend/app/models/` 下的 SQLAlchemy 模型和 `backend/migrations/` 下的 Alembic 迁移。

```bash
make migrate
```

该命令从 backend 环境读取 `DATABASE_URL`。PostgreSQL 保持 Compose 内部服务，不发布到宿主机。

## 认证与 API 表面

后端提供 MVP 认证和运营 API。受保护路由使用：

```text
Authorization: Bearer <token>
```

主要路由包括：

- `POST /auth/login`：登录并返回 bearer token，记录成功或失败审计事件。
- `POST /auth/logout`：要求 bearer 认证，记录 logout 审计事件。Token 是无状态的，按时间过期；logout 不撤销 token。
- `GET /auth/me`：返回当前用户，不包含密码哈希或密钥。
- `GET /users`、`POST /users`、`PATCH /users/{user_id}/status`：管理员用户管理。
- `GET /intelligence`、`GET /intelligence/{intelligence_id}`：规范化情报搜索和详情。
- `POST /alerts/evaluate`、`GET /alerts`、`GET /alerts/{alert_id}`、`PATCH /alerts/{alert_id}/status`：告警评估、列表、详情和状态更新。
- `GET /sources`、`GET /sources/{source_id}`、`GET /sources/jobs`：数据源状态和任务日志。
- `GET /sources/pipeline/status`、`POST /sources/pipeline/trigger`：受限的运维处理管道状态与触发。
- `PATCH /sources/{source_id}/status`：数据源状态更新并记录审计。
- `GET /exports/intelligence.csv`、`GET /exports/intelligence/{intelligence_id}/markdown`、`GET /exports/alerts.csv`、`GET /exports/summary.pdf`：认证导出。
- `POST /manual-entries`、`GET /manual-entries`、`GET /manual-entries/{entry_id}`、`PATCH /manual-entries/{entry_id}`：人工录入。

前端登录页调用 `POST /auth/login`，将 bearer token 存入浏览器 local storage 作为 MVP session，随后调用 `GET /auth/me` 填充当前用户。当受保护 API 返回 `401` 时，前端会清除 token。工作台页面只在当前用户加载完成后渲染。非管理员用户的 admin-only 前端控件会禁用；后端管理员路由仍负责最终授权。

人工录入通过既有 raw 和 normalized intelligence 表保存。Research lead 会映射为 `advisory` intelligence type，并默认带 `research_lead` tag 和 `under_review` 状态。重复提交使用确定性 dedup key，不创建重复 normalized intelligence 记录。

情报搜索和详情响应基于 normalized `ThreatIntelligence`。响应包含来源名称、来源 URL、来源归因行、规范化漏洞字段、标签、状态、风险字段和安全 metadata。Raw payload、collector headers、Token、API key、cookie、密码等敏感值不会出现在 API 响应中。

告警评估位于后端 service layer，可在 worker scoring 后或通过认证 API 触发。MVP 规则覆盖 Critical 情报、CISA KEV 或 known exploited 信号、高风险车辆关键组件、同一 CVE 多来源观察，以及短时间内同厂商/组件集中爆发。重复告警通过每条情报的确定性 `triggering_rule` 避免。告警 API 不发送外部通知，也不创建工单。

数据源状态 API 只报告持久化的 worker 状态。它可以暴露安全的数据源配置、同步状态、失败原因、retry/skipped metadata 和任务计数，但不实现源特定采集行为，也不暴露凭证。Pipeline trigger API 只能入队已批准的 Celery processing task，不接受任意 task name、queue、shell 命令或 broker 细节。

导出端点直接流式生成文件，只使用安全公开字段。CSV 导出有边界且支持筛选；Markdown 包含单条 normalized intelligence 和来源归因；PDF 是轻量摘要报告。导出会省略 raw payload、不安全 metadata 和未脱敏的疑似密钥值。

## 实现边界

- Backend 当前包含 health/readiness、MVP auth、管理员用户管理、情报搜索/详情、人工录入、告警评估/复核、数据源状态/任务检查、基础导出、审计日志、持久化模型和迁移。
- Frontend 当前包含中文工作台外壳、登录/session、受保护运营页面、共享 loading/error/empty/session-expired 状态，以及 auth、intelligence、alerts、sources、manual entries、users 和 exports 的可复用 API helpers。
- Worker 当前包含 Connector runtime contracts、NVD、CISA KEV、RSS、厂商公告 metadata、sample Connectors、raw-to-normalized deduplication、固定规则风险评分，以及定时 collect-normalize-score processing。
- 告警生成不属于 Connector 或 scoring worker task；评分后使用后端 service 或 `POST /alerts/evaluate` 创建持久化告警记录。
