# SentinelDrive

SentinelDrive 是一个车联网威胁情报工作台。本仓库提供面向 Linux 服务器部署的 Docker Compose 运行栈，包含中文前端工作台、FastAPI 后端、PostgreSQL 存储、Redis broker/cache、Celery worker、scheduler 和 Caddy 反向代理。

## 部署目标

推荐部署环境：

- Ubuntu 22.04 或更新版本。
- 4 核 CPU、4 GB 内存、40 GB SSD 起步。
- Docker Engine 与 Docker Compose v2。
- 一个域名，或仅用于内网/临时访问的服务器 IP。

运行栈服务：

- `reverse-proxy`：Caddy 公共入口，负责前端流量和 `/api/*` 反向代理。
- `frontend`：Next.js 中文运营工作台，覆盖情报、告警、数据源、人工录入和基础用户能力。
- `backend`：FastAPI API，包含 health/readiness、认证、用户、情报、告警、数据源、人工录入和导出。
- `worker`：Celery worker，负责执行 Source Connector 和处理任务。
- `scheduler`：Celery Beat 调度器，负责派发数据源同步任务。
- `postgres`：内部 PostgreSQL 服务。
- `redis`：内部 Redis 服务。

PostgreSQL、Redis、`worker` 和 `scheduler` 都是内部 Compose 服务。生产部署时不要把它们暴露到公网。

## 服务器部署

在 Linux 服务器上安装 Docker 后，拉取代码：

```bash
cd /opt
git clone https://github.com/Ma0xFly/SentinelDrive.git sentineldrive
cd sentineldrive
```

创建并编辑环境文件：

```bash
cp .env.example .env
nano .env
```

至少替换这些值：

```env
APP_ENV=production
APP_SECRET_KEY=replace-with-a-strong-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-database-password
DATABASE_URL=postgresql+psycopg://sentineldrive:replace-with-a-strong-database-password@postgres:5432/sentineldrive
ADMIN_BOOTSTRAP_EMAIL=admin@example.com
ADMIN_BOOTSTRAP_PASSWORD=replace-with-a-strong-admin-password
CADDY_HOST=sentineldrive.example.com
CADDY_TLS_EMAIL=security@example.com
```

如果只是临时用服务器 IP 做 HTTP 预览，可使用：

```env
CADDY_HOST=:80
CADDY_TLS_EMAIL=
```

启动前校验配置：

```bash
make config-check
make compose-config
```

构建并启动：

```bash
docker compose up -d --build
make migrate
make admin-bootstrap
```

检查运行状态：

```bash
curl http://127.0.0.1/api/health
curl http://127.0.0.1/api/ready
docker compose ps
```

浏览器访问：

```text
http://你的服务器IP
https://你的域名
```

## 首次登录

管理员账号来自 `.env`：

```text
Email: ADMIN_BOOTSTRAP_EMAIL
Password: ADMIN_BOOTSTRAP_PASSWORD
```

`ADMIN_BOOTSTRAP_PASSWORD` 只用于初始化或更新管理员账号，系统保存的是密码哈希。不要把 `.env` 提交到 Git，也不要把真实密码写入文档或 issue。

## 数据源与处理

Worker 需要出站网络访问，以便连接 NVD、CISA KEV、RSS feed 和厂商公告页面。PostgreSQL 和 Redis 仍保持内部服务，不发布宿主机端口。

执行一次采集：

```bash
make sync-once
```

执行一次完整处理路径：

```bash
make process-once
```

`make sync-once` 只采集并持久化 source/job/raw 数据。`make process-once` 会执行采集、规范化、评分，并运行后端告警评估。

## 常用命令

- `make config-check`：校验面向部署的环境占位规则。
- `make compose-config`：渲染并校验 `docker-compose.yml`。
- `docker compose up -d --build`：后台构建并启动运行栈。
- `make logs`：跟随查看近期 Compose 日志。
- `make migrate`：运行后端 Alembic 迁移。
- `make admin-bootstrap`：创建或更新已配置的初始管理员。
- `make sync-once`：调用一次 worker 数据源同步任务。
- `make process-once`：运行一次采集、规范化、评分和告警评估。
- `make down`：停止运行栈，不删除持久化卷。

## 更新部署

服务器上更新代码：

```bash
cd /opt/sentineldrive
git pull
make config-check
make compose-config
docker compose up -d --build
make migrate
```

如果更新涉及管理员账号配置，再运行：

```bash
make admin-bootstrap
```

## 备份

PostgreSQL 是核心持久化数据。执行迁移、升级、批量导入或恢复演练前先备份：

```bash
backup_dir="backups/postgres"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/sentineldrive-postgres-$timestamp.dump"

mkdir -p "$backup_dir"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c --no-owner --no-acl' > "$backup_file"
chmod 600 "$backup_file"
ls -lh "$backup_file"
```

更完整的恢复流程见 [运维手册](docs/operations.md)。

## 文档

- [Ubuntu Docker Compose 部署指南](docs/deployment.md)
- [运维手册](docs/operations.md)
- [环境变量参考](docs/environment.md)
- [本地开发指南](docs/development.md)
- [Connector 开发指南](docs/connectors.md)
- [数据源配置示例](docs/source-configuration.md)
- [测试与 QA 指南](docs/testing.md)
- [Compose 部署验证](docs/qa/compose-deployment-verification.md)
- [运行时脚手架说明](docs/scaffold.md)

## 实现状态

MVP 运行栈已包含主要工作台页面、认证 API、迁移、Source Connector 运行时、原始数据持久化、规范化、去重、评分、告警、导出和聚焦测试。数据库在 bootstrap 后默认为空；可通过人工录入页面或已配置的数据源同步添加数据。
