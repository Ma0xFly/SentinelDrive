# Ubuntu Docker Compose 部署指南

本文档记录当前项目在单台 Ubuntu 主机上的 Docker Compose 部署路径。

## 目标形态

- 一台 Ubuntu 22.04 或更新版本服务器。
- 小型服务器目标资源：4 核 CPU、4 GB 内存、40 GB SSD。
- Docker Compose 运行栈包含 `reverse-proxy`、`frontend`、`backend`、`worker`、`scheduler`、`postgres` 和 `redis`。
- 只有 `reverse-proxy` 发布宿主机端口。

## 部署前检查

1. 安装 Docker Engine 和 Docker Compose v2。
2. 将仓库 clone 或复制到服务器。
3. 从 `.env.example` 创建 `.env`。
4. 设置 `APP_ENV=production`。
5. 将所有 `change-me-development-only` 替换为部署环境专用密钥。
6. 确定 `CADDY_HOST`、`CADDY_TLS_EMAIL`、`REVERSE_PROXY_HTTP_PORT` 和 `REVERSE_PROXY_HTTPS_PORT`。
7. 启用真实采集前，先审查数据源配置。

不要提交生成后的 `.env` 文件。

## 配置

```bash
cp .env.example .env
sed -i 's/^APP_ENV=.*/APP_ENV=production/' .env
make config-check
make compose-config
```

本地开发时，`.env.example` 保持 `APP_ENV=development`，允许安全占位值。使用 `APP_ENV=production`、`APP_ENV=prod` 或 `APP_ENV=staging` 前，至少替换 `APP_SECRET_KEY`、`POSTGRES_PASSWORD`、`DATABASE_URL`、`ADMIN_BOOTSTRAP_EMAIL`、`ADMIN_BOOTSTRAP_PASSWORD` 和 `CADDY_HOST`。`make config-check` 会在这些值仍像占位符时清晰失败，且不会打印密钥值。

启动前审查渲染后的配置。确认只有 `reverse-proxy` 发布宿主机端口；`postgres`、`redis`、`backend`、`frontend`、`worker` 和 `scheduler` 不应直接发布宿主机端口。`NVD_API_KEY` 可以留空；未设置时 NVD Connector 使用更严格的未认证限速。`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 设置时必须是 JSON list。

## 启动与初始化

```bash
docker compose up -d --build
make migrate
make admin-bootstrap
```

使用 `make logs` 查看启动输出。`make migrate` 通过 backend 容器应用 Alembic 迁移。`make admin-bootstrap` 根据 `ADMIN_BOOTSTRAP_EMAIL` 和 `ADMIN_BOOTSTRAP_PASSWORD` 创建或更新管理员，只保存密码哈希，并记录审计事件。

## 停止

```bash
make down
```

Compose volumes `postgres_data`、`redis_data`、`caddy_data` 和 `caddy_config` 是持久化卷，不会被 `make down` 删除。

## 公共访问面

- `/` 通过 `reverse-proxy` 路由到 `frontend`。
- `/api/*` 通过 `reverse-proxy` 路由到 `backend`。

后端暴露 `GET /health`、`GET /ready` 和 `docs/testing.md` 中记录的认证 API。通过反向代理访问时，使用 `/api/health` 检查进程存活，使用 `/api/ready` 检查 PostgreSQL 和 Redis readiness。

启动后检查健康状态：

```bash
curl -fsS "http://127.0.0.1/api/health"
curl -fsS "http://127.0.0.1/api/ready"
curl -fsS -I "http://127.0.0.1/"
```

## 内部访问面

- `backend` 通过 `DATABASE_URL` 访问 PostgreSQL。
- `backend`、`worker` 和 `scheduler` 通过 `REDIS_URL`、`CELERY_BROKER_URL` 和 `CELERY_RESULT_BACKEND` 访问 Redis。
- `postgres` 和 `redis` 位于内部 Compose 网络。
- `worker` 和 `scheduler` 同时连接内部网络和 egress 网络：内部网络用于 PostgreSQL/Redis，egress 网络用于出站数据源采集。
- `worker` 和 `scheduler` 使用 `CELERY_LOG_LEVEL`；`worker` 还使用 `CELERY_WORKER_CONCURRENCY`，小型服务器默认值为 `2`。

## 公共配置

`frontend` 服务是 nginx 静态托管，API base path 固定为 `/api`，由 `reverse-proxy` 转发到 `backend`。部署时不需要浏览器可见环境变量；不要把凭证、Token 或私有内部 URL 写入前端配置。

## 反向代理主机与 TLS

本地 HTTP 预览：

```env
CADDY_HOST=:80
CADDY_TLS_EMAIL=
```

生产域名：

```env
CADDY_HOST=sentineldrive.example.com
CADDY_TLS_EMAIL=security@example.com
REVERSE_PROXY_HTTP_PORT=80
REVERSE_PROXY_HTTPS_PORT=443
```

不要把 backend、PostgreSQL、Redis、worker 或 scheduler 地址放入浏览器可见变量。

## 数据源设置

运行采集前先审查配置：

```env
NVD_API_KEY=
SOURCE_ENABLED_NVD=true
SOURCE_ENABLED_CISA_KEV=true
SOURCE_ENABLED_RSS=true
SOURCE_RSS_FEEDS=[]
SOURCE_ENABLED_VENDOR_ADVISORIES=false
SOURCE_VENDOR_ADVISORY_ENDPOINTS=
```

`NVD_API_KEY` 是可选项，不得提交。`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 是 JSON list。审查端点前，建议保持厂商公告采集关闭。

触发一次采集：

```bash
make sync-once
```

采集会写入 source/job/raw 数据。Normalization、scoring 和 backend alert generation 是独立的 worker/API 动作。

## 运维命令

```bash
make migrate
make admin-bootstrap
make logs
make down
```

## 部署冒烟测试

启动后执行 `docs/qa/compose-deployment-verification.md` 中的命令化验证。至少确认迁移和管理员初始化能从 backend 容器运行，`/api/health` 与 `/api/ready` 能通过 `reverse-proxy` 成功返回，前端通过 `reverse-proxy` 返回 HTTP 200，worker 日志显示任务注册，服务日志不打印凭证值。

PostgreSQL 备份/恢复、例行维护、留存和故障排查流程见 `docs/operations.md`。
