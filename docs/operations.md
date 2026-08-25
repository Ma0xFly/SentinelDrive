# 运维手册

本手册覆盖单台小型 Ubuntu 主机上的 Docker Compose 部署。PostgreSQL、Redis、`backend`、`frontend`、`worker` 和 `scheduler` 保持在 Compose 网络内部；只有 `reverse-proxy` 发布宿主机 HTTP/HTTPS 端口。

所有命令默认从仓库根目录运行。不要把真实 `.env` 值、bearer token、NVD key、数据库 URL 或管理员密码粘贴到 issue、聊天记录或公开日志中。

## 配置预检

```bash
make config-check
make compose-config
```

预期结果：配置校验通过，Docker Compose 成功渲染。生产类环境中，占位值会按变量名触发失败，但不会打印密钥值。

使用 `APP_ENV=production`、`APP_ENV=prod` 或 `APP_ENV=staging` 前，必须替换 `APP_SECRET_KEY`、`POSTGRES_PASSWORD`、`DATABASE_URL`、`ADMIN_BOOTSTRAP_EMAIL`、`ADMIN_BOOTSTRAP_PASSWORD` 和 `CADDY_HOST` 的占位值。

## 服务生命周期

前台启动完整运行栈：

```bash
make up
```

运维会话中后台启动或重建：

```bash
docker compose up -d --build
```

停止运行栈但不删除持久化卷：

```bash
make down
```

查看状态：

```bash
docker compose ps
```

重启一个或多个服务：

```bash
docker compose restart backend worker scheduler
```

重建已变更镜像并重新创建服务：

```bash
docker compose up -d --build backend frontend worker scheduler
```

正常运维中不要使用 `docker compose down -v`。该命令会删除 PostgreSQL、Redis 和 Caddy 的持久化卷。

## 日志

跟随近期日志：

```bash
make logs
```

查看指定服务日志：

```bash
docker compose logs --tail=200 backend
docker compose logs --tail=200 worker scheduler
docker compose logs --tail=200 postgres redis
docker compose logs --tail=200 reverse-proxy frontend
```

排查已知时间窗口内事件：

```bash
docker compose logs --since 30m backend worker scheduler postgres redis
```

分享日志前，先扫描可能泄露的密钥：

```bash
docker compose logs --tail=300 backend worker scheduler reverse-proxy \
  | grep -Ei 'password|secret|token|apikey|api_key|database_url|postgres_password|admin_bootstrap_password'
```

任何命中都先按敏感信息处理，确认后再决定是否脱敏分享。

## 健康检查与冒烟测试

公共健康路由通过 `reverse-proxy` 访问：

```bash
curl -sS http://127.0.0.1/api/health
curl -sS http://127.0.0.1/api/ready
curl -sS -I http://127.0.0.1/
```

预期结果：

- `/api/health` 返回 `{"status":"ok"}`。
- `/api/ready` 返回 ready 状态，PostgreSQL 和 Redis 标记为 `ok`。
- `/` 返回 HTTP 200，并提供 Next.js 工作台。

不发布端口的情况下检查内部依赖：

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select 1 as ok;"'
docker compose exec redis redis-cli ping
docker compose exec worker python -c "import socket; print(socket.getaddrinfo('services.nvd.nist.gov', 443)[0][4][0])"
```

PostgreSQL 和 Redis 命令在容器内运行，并使用容器环境变量。Worker DNS 检查用于确认 live source collection 所需的出站 egress。

## 测试命令

```bash
make backend-test
make frontend-check
```

预期结果：后端测试、worker 测试和前端生产构建通过。直接本地命令和完整测试矩阵见 `docs/testing.md`。

## 迁移与管理员初始化

初次启动后，以及拉取包含新 Alembic revisions 的代码后运行迁移：

```bash
make migrate
```

创建、重新激活或更新配置的管理员账号：

```bash
make admin-bootstrap
```

Bootstrap 命令读取 `ADMIN_BOOTSTRAP_EMAIL` 和 `ADMIN_BOOTSTRAP_PASSWORD`，只保存密码哈希，不打印明文密码。任何共享或公网部署前必须替换本地开发占位密码。

## PostgreSQL 备份

在宿主机侧 `backups/postgres/` 下创建备份。该目录有意放在 Docker volumes 外，便于复制到服务器外部。

```bash
backup_dir="backups/postgres"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/sentineldrive-postgres-$timestamp.dump"

mkdir -p "$backup_dir"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c --no-owner --no-acl' > "$backup_file"
chmod 600 "$backup_file"
ls -lh "$backup_file"
```

验证备份可列出：

```bash
docker compose exec -T postgres pg_restore --list < "$backup_file" | head
```

运维注意事项：

- 迁移、批量导入、恢复测试或高风险维护前先备份。
- 尽量将备份文件复制到服务器外部存储。
- 不要提交 `backups/`，也不要把备份文件附到公开 issue。Dump 可能包含用户账号、审计记录、source metadata 和已采集情报。

## PostgreSQL 恢复

恢复会替换当前应用数据库。继续前，确认备份文件正确，并先对当前数据库做一份新备份。

设置备份文件：

```bash
backup_file="backups/postgres/sentineldrive-postgres-YYYYMMDDTHHMMSSZ.dump"
test -f "$backup_file"
docker compose exec -T postgres pg_restore --list < "$backup_file" | head
```

停止应用写入服务，保留 PostgreSQL 和 Redis 可用：

```bash
docker compose stop backend worker scheduler frontend reverse-proxy
docker compose up -d postgres redis
```

删除并重建配置的数据库，然后恢复 dump：

```bash
docker compose exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" "$POSTGRES_DB"'

docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl' < "$backup_file"
```

将数据库迁移到当前 schema，并重启服务：

```bash
make migrate
docker compose up -d backend worker scheduler frontend reverse-proxy
curl -sS http://127.0.0.1/api/ready
```

恢复后，在触发新同步前审查 `worker` 和 `scheduler` 日志。如果旧 Celery broker/result 数据导致 stale jobs 反复执行，确认影响后，只清理 Celery Redis 数据库：

```bash
docker compose stop worker scheduler
docker compose exec redis redis-cli -n 1 FLUSHDB
docker compose exec redis redis-cli -n 2 FLUSHDB
docker compose up -d worker scheduler
```

这只删除 queued Celery tasks 和 task results，不删除 PostgreSQL 数据。

## 数据源操作

运行一次不包含 normalization、scoring 或 alert evaluation 的手动 source sync：

```bash
make sync-once
```

该命令会入队 `sentineldrive.sync_sources`。查看执行：

```bash
docker compose logs --since 5m worker scheduler
```

运行完整一次性处理路径：

```bash
make process-once
```

该命令先运行 worker processing pipeline，采集已启用数据源、持久化 raw records、规范化 pending raw rows，并为 normalized intelligence 评分。随后在 backend 容器中运行 alert evaluation script，由后端 service layer 创建持久化告警记录。

Worker task 边界：

- `sentineldrive.sync_sources`：采集已启用 sources，并持久化 source status、sync state、job logs 和 raw intelligence。
- `sentineldrive.normalize_raw_intelligence`：将 pending 或 collected raw rows 规范化为共享 threat intelligence records。
- `sentineldrive.score_threat_intelligence`：对 normalized rows 应用确定性评分。
- `sentineldrive.process_pipeline`：按顺序运行 collection、normalization 和 scoring，并返回每阶段计数和失败总结。
- Backend alert evaluation 创建持久化告警复核记录；worker 不导入 backend ORM models，也不直接创建 alert records。

Celery Beat 使用 `SOURCE_SYNC_INTERVAL_SECONDS` 调度 `sentineldrive.process_pipeline`。只有在排查或 replay 时才通过 Celery 调用单独阶段：

```bash
docker compose run --rm worker celery -A app.celery_app.celery_app call sentineldrive.normalize_raw_intelligence --kwargs='{"limit":100}'
docker compose run --rm worker celery -A app.celery_app.celery_app call sentineldrive.score_threat_intelligence --kwargs='{"limit":100}'
```

通过后端脚本或认证 API 评估告警：

```bash
docker compose run --rm backend ./scripts/evaluate-alerts.sh --limit 100
```

```bash
BACKEND_URL="http://127.0.0.1/api"
TOKEN="<bearer-token-from-login>"

curl -sS -X POST "$BACKEND_URL/alerts/evaluate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit":100}'
```

通过认证 API 查看 source health 和 job history：

```bash
curl -sS "$BACKEND_URL/sources?status=error" \
  -H "Authorization: Bearer $TOKEN"

curl -sS "$BACKEND_URL/sources/jobs?status=failed&limit=25" \
  -H "Authorization: Bearer $TOKEN"

curl -sS "$BACKEND_URL/sources/pipeline/status" \
  -H "Authorization: Bearer $TOKEN"
```

无需 shell 访问 worker，即可通过后端触发已批准 processing pipeline：

```bash
curl -sS -X POST "$BACKEND_URL/sources/pipeline/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"normalization_limit":100,"scoring_limit":100,"alert_limit":100}'
```

使用 `PATCH /sources/{source_id}/status` 与 `enabled`、`disabled` 或 `error` 记录有意的数据源状态变更。Status endpoints 只报告持久化 worker state，不直接运行 Connectors。Pipeline trigger endpoint 只能入队 `sentineldrive.process_pipeline`；它不接受 task names、queues、broker URLs、shell commands 或 Celery control operations。

## 导出

从后端 API 生成认证导出：

```bash
curl -sS -o intelligence.csv "$BACKEND_URL/exports/intelligence.csv?risk_level=critical" \
  -H "Authorization: Bearer $TOKEN"

curl -sS -o alerts.csv "$BACKEND_URL/exports/alerts.csv?status=open" \
  -H "Authorization: Bearer $TOKEN"

curl -sS -o summary.pdf "$BACKEND_URL/exports/summary.pdf" \
  -H "Authorization: Bearer $TOKEN"
```

单条情报记录使用 `GET /exports/intelligence/{intelligence_id}/markdown`。导出文件会省略 raw source payloads 和疑似密钥值，但仍可能包含运营情报，应按内部数据处理。

## 留存与磁盘使用

目标主机只有 40 GB SSD。Live source sync、镜像重建、备份和导出前后都应监控磁盘。

检查 Docker 和备份磁盘使用：

```bash
df -h .
docker system df
du -sh backups/postgres 2>/dev/null || true
docker compose exec postgres du -sh /var/lib/postgresql/data
docker compose exec redis du -sh /data
```

持久化 Compose volumes：

- `postgres_data`：应用数据库和 source/job/intelligence records。
- `redis_data`：cache、broker 和 task results 的 Redis append-only 数据。
- `caddy_data`：Caddy 证书和状态。
- `caddy_config`：Caddy runtime configuration state。

留存默认值：

- `RAW_RETENTION_DAYS=90` 表示预期轻量 raw retention window。
- `HTML_RETENTION_MODE=metadata_only` 和 `PDF_RETENTION_MODE=metadata_only` 避免保存完整 HTML/PDF 快照或下载附件。
- Redis 通过 `REDIS_MAXMEMORY=256mb` 控制内存，但 append-only 数据仍需监控。

当前没有自动 PostgreSQL pruning 命令。优先使用有界 source configuration、metadata-only retention、backup rotation 和人工审查，避免直接手动删除应用记录。

查看旧备份：

```bash
find backups/postgres -type f -name 'sentineldrive-postgres-*.dump' -mtime +14 -print
```

确认已有服务器外部副本后再删除旧备份：

```bash
find backups/postgres -type f -name 'sentineldrive-postgres-*.dump' -mtime +14 -delete
```

磁盘压力来自旧镜像或 build cache 时，清理未使用 Docker 构建产物：

```bash
docker system df
docker image prune
docker builder prune
```

部署主机上避免使用 `docker volume prune`，除非已确认不会删除 SentinelDrive volumes。

## 例行维护

每日或交接前：

- 检查 `docker compose ps`。
- 检查 `/api/ready`。
- 查看 `docker compose logs --tail=200 backend worker scheduler postgres redis`。
- 通过 `GET /sources?status=error` 查看失败数据源。

每周：

- 创建并验证 PostgreSQL 备份。
- 检查备份目录大小并轮转旧备份。
- 检查 `docker system df`，需要时清理未使用 images/build cache。
- 审查 source sync job history 中反复失败的来源。

升级前：

- 创建 PostgreSQL 备份。
- 运行 `make config-check` 和 `make compose-config`。
- 使用 `docker compose up -d --build` 重建并启动。
- 运行 `make migrate`。
- 执行 `docs/qa/compose-deployment-verification.md` 中的 smoke checks。

## 故障排查

| 现象 | 检查 | 处理 |
| --- | --- | --- |
| WSL 中 Docker 不可用 | `docker info --format '{{.ServerVersion}}'` 失败 | 使用 `sudo service docker start` 启动 Docker，再重新运行 `docker info`。 |
| 本地浏览器出现证书提示或 HTTPS 混乱 | 本地 `.env` 中 `CADDY_HOST=localhost` | 仅本地 HTTP 预览时设置 `CADDY_HOST=:80` 并重建 `reverse-proxy`。生产类部署使用真实 host。 |
| `/api/ready` 报 PostgreSQL 或 Redis 失败 | `docker compose ps`；`docker compose logs --tail=100 postgres redis backend` | 确认 `postgres` 和 `redis` 健康，再重启 `backend`。不要为调试 readiness 发布内部端口。 |
| Worker 无法解析 NVD/CISA/RSS hosts | `docker compose exec worker python -c "import socket; print(socket.getaddrinfo('services.nvd.nist.gov', 443)[0][4][0])"` | 确认 `worker` 和 `scheduler` 连接 `egress`；用 `docker compose up -d --build worker scheduler` 重建镜像并重新创建容器。 |
| NVD 返回请求错误 | `docker compose logs --tail=200 worker \| grep -Ei nvd` | 保持默认 120 天 `lastMod` window。只有在安全配置时添加 `NVD_API_KEY`；它是可选项。 |
| Admin bootstrap 出现 Passlib/bcrypt 兼容 warning | `docker compose run --rm backend ./scripts/admin-bootstrap.sh` | 从当前 requirements 重建 backend image，当前版本 pin 了 `bcrypt==4.0.1`：`docker compose build backend`。 |
| Worker 日志出现 PostgreSQL enum cast 错误，例如 `source_type is of type source_type` | `docker compose logs --tail=200 worker postgres` | 使用当前代码重建并重新创建 `worker` 和 `scheduler`；worker metadata 会渲染 PostgreSQL enum bind casts。 |
| `make config-check` 在生产类配置下失败 | 错误只列变量名 | 替换 `.env` 中占位值；不要削弱校验，也不要提交密钥。 |
| 磁盘使用增长过快 | `docker system df`；`du -sh backups/postgres`；`docker compose exec postgres du -sh /var/lib/postgresql/data` | 轮转备份、清理未使用 Docker images/build cache，并审查 source sync 规模。没有已验证备份前不要删除 Compose volumes。 |

## 事件记录

排查问题时：

- 避免打印 `.env` 中的密钥。
- 除非已脱敏，否则不要在公开 ticket 或报告中粘贴完整 `docker compose config` 输出。
- 避免导出未脱敏凭证、Token、私有个人数据或批量 VIN 数据。
- 手动数据修正记录必须保留 source attribution。
- 记录故障发生在哪一层：collection、parsing、normalization、deduplication、scoring、alerts、exports、API、frontend 或 deployment。
