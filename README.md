# SentinelDrive

SentinelDrive 是一个车联网威胁情报工作台。本仓库提供一套 Docker Compose 运行栈，包含中文前端工作台、FastAPI 后端、PostgreSQL 存储、Redis broker/cache、Celery worker、scheduler 和 Caddy 反向代理。

## 当前实现

已实现的服务面：

- `reverse-proxy`：Caddy 公共入口，负责前端流量和 `/api/*` 反向代理。
- `frontend`：Next.js 中文运营工作台，覆盖情报、告警、数据源、人工录入和基础用户能力。
- `backend`：FastAPI API，包含 health/readiness、认证、用户、情报、告警、数据源、人工录入和导出。
- `worker`：Celery worker，负责执行 Source Connector 和处理任务。
- `scheduler`：Celery Beat 调度器，负责派发数据源同步任务。
- `postgres`：内部 PostgreSQL 服务。
- `redis`：内部 Redis 服务。

PostgreSQL、Redis、`worker` 和 `scheduler` 都是内部 Compose 服务。部署修改时不要把它们暴露到公网。

## 快速开始

如果需要从 Windows 浏览器预览 WSL 内的本地服务，先启动 Docker：

```bash
sudo service docker start
docker info --format '{{.ServerVersion}}'
```

创建本地环境文件。普通 HTTP 浏览器预览建议设置 `CADDY_HOST=:80`；否则 Caddy 会把 `localhost` 当作本地 HTTPS 站点，浏览器可能出现证书提示。

```bash
cp .env.example .env
sed -i 's/^CADDY_HOST=.*/CADDY_HOST=:80/' .env
make config-check
make compose-config
docker compose up -d --build
make migrate
make admin-bootstrap
```

从 Windows 打开工作台：

```text
http://localhost
```

本地开发 bootstrap 凭证：

```text
Email: admin@example.test
Password: change-me-development-only
```

验证运行栈：

```bash
curl http://127.0.0.1/api/health
curl http://127.0.0.1/api/ready
docker compose ps
docker compose exec worker python -c "import socket; print(socket.getaddrinfo('services.nvd.nist.gov', 443)[0][4][0])"
```

确认数据源配置后，可选择执行一次真实数据源采集：

```bash
make sync-once
```

该命令会运行已启用的 Source Connectors，并持久化 source/job/raw 数据。它不会自动执行规范化、评分或后端告警生成，除非当前版本已在后续任务中接入自动处理管道。

Worker 需要出站网络访问，以便连接 NVD、CISA KEV 等真实数据源。它同时连接内部 Compose 网络用于访问 PostgreSQL 和 Redis，并连接具备出站 HTTPS 能力的 Compose 网络。PostgreSQL 和 Redis 仍保持内部服务，不发布宿主机端口。

停止运行栈：

```bash
docker compose down
```

默认 bootstrap 密码仅用于本地开发。共享环境或公网环境使用前，必须替换所有 `change-me-development-only` 值。部署前运行 `make config-check`；当 `APP_ENV` 为生产类值且关键配置仍为占位符时，检查应失败。

## 稳定命令

- `make compose-config`：渲染并校验 `docker-compose.yml`。
- `make config-check`：校验面向部署的环境占位规则。
- `make up`：构建并以前台方式启动运行栈。
- `make down`：停止运行栈。
- `make logs`：跟随查看近期 Compose 日志。
- `make backend-test`：运行后端测试。
- `make frontend-check`：运行前端检查。
- `make migrate`：运行后端 Alembic 迁移。
- `make admin-bootstrap`：创建或更新已配置的初始管理员。
- `make sync-once`：调用一次 worker 数据源同步任务。
- `make worker`：运行 worker 命令。
- `make scheduler`：运行 scheduler 命令。

## 文档

- [本地开发指南](docs/development.md)
- [Ubuntu Docker Compose 部署指南](docs/deployment.md)
- [环境变量参考](docs/environment.md)
- [Connector 开发指南](docs/connectors.md)
- [数据源配置示例](docs/source-configuration.md)
- [运维手册](docs/operations.md)
- [测试与 QA 指南](docs/testing.md)
- [Compose 部署验证](docs/qa/compose-deployment-verification.md)
- [运行时脚手架说明](docs/scaffold.md)

## 实现状态

MVP 运行栈已包含主要工作台页面、认证 API、迁移、Source Connector 运行时、原始数据持久化、规范化、去重、评分、告警、导出和聚焦测试。数据库在 bootstrap 后默认为空；可通过人工录入页面或已配置的数据源同步添加本地预览数据。
