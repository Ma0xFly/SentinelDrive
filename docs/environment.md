# 环境变量参考

所有服务配置都应来自环境变量或已记录的配置文件。使用 `.env.example` 作为安全模板，绝不要提交真实密钥。

部署前运行 `make config-check`。本地开发可在 `APP_ENV=development` 下使用安全占位值；当 `APP_ENV` 为生产类值（`production`、`prod` 或 `staging`）时，必须替换占位密钥和部署主机设置。检查只报告变量名，不打印密钥值。

## Application

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | `backend`, `worker`, `scheduler` | `development` | 应用环境标识。生产类值会启用占位密钥校验。 |
| `APP_SECRET_KEY` | `backend` | `change-me-development-only` | 后端必需，用于签名 API bearer tokens。生产类环境前必须替换。 |
| `READINESS_TIMEOUT_SECONDS` | `backend` | `2` | `/ready` PostgreSQL 和 Redis 依赖探测超时。 |
| `NODE_ENV` | `frontend` | `production` | 传给 Next.js 服务。 |
| `NEXT_PUBLIC_API_BASE_URL` | `frontend` | `/api` | 浏览器可见 API base path。不要在 `NEXT_PUBLIC_` 变量中放密钥。 |

## PostgreSQL

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `POSTGRES_DB` | `postgres` | `sentineldrive` | 数据库名。 |
| `POSTGRES_USER` | `postgres` | `sentineldrive` | 数据库用户。 |
| `POSTGRES_PASSWORD` | `postgres` | `change-me-development-only` | 本地开发外必须替换。 |
| `DATABASE_URL` | `backend`, `worker`, `scheduler` | `postgresql+psycopg://sentineldrive:change-me-development-only@postgres:5432/sentineldrive` | 内部 Compose 数据库 URL。生产类部署前替换占位凭证。 |

PostgreSQL 必须保持 Compose 内部服务。

## Redis and Celery

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `REDIS_URL` | `backend`, `worker`, `scheduler` | `redis://redis:6379/0` | 通用 Redis 连接 URL。 |
| `CELERY_BROKER_URL` | `backend`, `worker`, `scheduler` | `redis://redis:6379/1` | Celery broker URL。Backend 只用它入队已批准的 processing pipeline task。 |
| `CELERY_RESULT_BACKEND` | `backend`, `worker`, `scheduler` | `redis://redis:6379/2` | Celery result backend URL。Backend 只用它读取运维面板所需的安全 task state。 |
| `CELERY_LOG_LEVEL` | `worker`, `scheduler` scripts | `INFO` | 可选脚本级日志等级默认值。 |
| `CELERY_WORKER_CONCURRENCY` | `worker` script | `2` | 可选 worker 并发默认值。目标单机部署应保持较小。 |
| `REDIS_MAXMEMORY` | `redis` | `256mb` | Redis 内存限制。 |

Redis 必须保持 Compose 内部服务。

`worker` 和 `scheduler` 同时连接内部网络和 `egress` 网络。内部网络用于 PostgreSQL 和 Redis；egress 用于从 NVD、CISA KEV、RSS feeds 和厂商公告页面进行真实 HTTPS 采集。这不会发布 worker 或 scheduler 端口。

## Admin Bootstrap

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `ADMIN_BOOTSTRAP_EMAIL` | `backend` | `admin@example.test` | `make admin-bootstrap` 用于初始管理员账号的邮箱。生产类部署前替换。 |
| `ADMIN_BOOTSTRAP_PASSWORD` | `backend` | `change-me-development-only` | `make admin-bootstrap` 使用的密码；只保存为密码哈希。共享、公网或生产类环境前替换。 |

管理员 bootstrap 命令从环境读取这些值，不打印或存储明文密码。它保存 bcrypt 密码哈希，并在配置的管理员账号创建或重新激活时写入审计事件。

## Source Collection

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `NVD_API_KEY` | `backend`, `worker`, `scheduler` | empty | 可选。配置后，NVD Connector 会作为 `apiKey` 请求头发送。 |
| `SOURCE_ENABLED_NVD` | `backend`, `worker`, `scheduler` | `true` | 启用 NVD CVE Connector。 |
| `SOURCE_ENABLED_CISA_KEV` | `backend`, `worker`, `scheduler` | `true` | 启用 CISA KEV Connector。 |
| `SOURCE_ENABLED_VENDOR_ADVISORIES` | `backend`, `worker`, `scheduler` | `false` | 启用端点驱动的厂商公告 metadata 采集。 |
| `SOURCE_ENABLED_RSS` | `backend`, `worker`, `scheduler` | `true` | 启用可配置 RSS/Atom feed 采集。 |
| `SOURCE_RSS_FEEDS` | `backend`, `worker`, `scheduler` | `[]` | RSS/Atom feed 对象 JSON list。每个对象应包含 `url`，可选 `name` 和 `source` 会作为 metadata 保留。 |
| `SOURCE_VENDOR_ADVISORY_ENDPOINTS` | `backend`, `worker`, `scheduler` | empty | 厂商端点对象 JSON list。为空时使用内置代表性 seed list。 |
| `SOURCE_ENABLED_SAMPLE` | `worker`, `scheduler` | `true` | 启用 sample no-op Connector，用于验证 worker runtime path。 |
| `SOURCE_SYNC_INTERVAL_SECONDS` | `backend`, `worker`, `scheduler` | `3600` | Scheduler 间隔。 |
| `SOURCE_TIMEOUT_SECONDS` | `backend`, `worker`, `scheduler` | `20` | Connector 超时。 |
| `SOURCE_RATE_LIMIT_PER_MINUTE` | `backend`, `worker`, `scheduler` | `20` | 默认 Connector 限速。 |
| `SOURCE_RETRY_ATTEMPTS` | `backend`, `worker`, `scheduler` | `3` | Connector 重试次数。 |

`SOURCE_SYNC_INTERVAL_SECONDS` 驱动 `sentineldrive.process_pipeline` 的 Celery Beat 调度。`SOURCE_TIMEOUT_SECONDS`、`SOURCE_RATE_LIMIT_PER_MINUTE` 和 `SOURCE_RETRY_ATTEMPTS` 由 worker Connector runtime 消费。数据源 URL 和端点示例见 `docs/source-configuration.md`。

当 `NVD_API_KEY` 为空时，配置加载器将其视为 unset，并应用更严格的未认证 NVD 限速。`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 设置时必须是合法 JSON list；格式错误应导致配置或 Connector 校验失败，而不是静默忽略。

## Retention

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `RAW_RETENTION_DAYS` | `backend`, `worker`, `scheduler` | `90` | 计划中的轻量 raw 留存周期。 |
| `HTML_RETENTION_MODE` | `backend` | `metadata_only` | 默认保存 URL/title/summary/hash/fetch metadata/parsing status，而不是完整 HTML 快照。 |
| `PDF_RETENTION_MODE` | `backend` | `metadata_only` | 默认保存 metadata 和链接，而不是下载 PDF 附件。 |

## Reverse Proxy

| Variable | Used by | Safe example | Notes |
| --- | --- | --- | --- |
| `CADDY_HOST` | `reverse-proxy` | `localhost` | Caddy 匹配的 host。 |
| `CADDY_TLS_EMAIL` | `reverse-proxy` | empty | 配置 TLS 自动化时使用的邮箱。 |
| `REVERSE_PROXY_HTTP_PORT` | `reverse-proxy` | `80` | 宿主机 HTTP 端口。 |
| `REVERSE_PROXY_HTTPS_PORT` | `reverse-proxy` | `443` | 宿主机 HTTPS 端口。 |
| `FRONTEND_UPSTREAM` | `reverse-proxy` | `frontend:3000` | 内部 frontend upstream。 |
| `BACKEND_UPSTREAM` | `reverse-proxy` | `backend:8000` | 内部 backend upstream。 |

## Service Exposure

- 公共宿主机端口只由 `reverse-proxy` 发布。
- `frontend` 和 `backend` 使用 Compose `expose`，通过 `reverse-proxy` 访问。
- `postgres`、`redis`、`worker` 和 `scheduler` 没有宿主机端口映射。
- `worker` 和 `scheduler` 需要出站 egress 进行真实数据源采集，但仍是非公开服务。

## Validation Behavior

- 当 `APP_ENV` 为 `production`、`prod` 或 `staging` 时，后端 settings 会拒绝占位生产配置。
- `make config-check` 对 `.env` 或 `ENV_FILE=/path/to/file` 执行同样面向部署的占位检查。
- `NVD_API_KEY` 是可选项。空值被视为 unset。
- `SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 设置时必须是 JSON list。
- 后端 settings 当前会校验已消费的数值型 timeout、interval、rate-limit、retry 和 retention 配置。
- 前端配置限定为 `NEXT_PUBLIC_API_BASE_URL`；它有意暴露给浏览器，绝不能包含密钥。
