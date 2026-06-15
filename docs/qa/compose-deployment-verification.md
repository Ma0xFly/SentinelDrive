# Compose 部署验证

最后验证时间：2026-05-20，分支 `chore/compose-deployment-verification`，Docker Engine 28.3.2。

当 Compose wiring、container startup、source collection、reverse-proxy routing、migrations 或 deployment scripts 发生变化时，使用本 runtime check。

## 本地 HTTP 预览

本地 WSL 或浏览器预览时，在 `.env` 中设置：

```env
CADDY_HOST=:80
```

这只会为本地预览路径禁用 Caddy 自动 HTTPS。生产类部署应使用真实 `CADDY_HOST`、`CADDY_TLS_EMAIL`，并替换密钥占位值。

## 验证命令

```bash
make config-check
make compose-config
docker compose up -d --build
docker compose run --rm backend ./scripts/migrate.sh
docker compose run --rm backend ./scripts/admin-bootstrap.sh
curl -sS http://127.0.0.1/api/health
curl -sS http://127.0.0.1/api/ready
curl -sS -I http://127.0.0.1/
docker compose exec worker python -c "import socket; print(socket.getaddrinfo('services.nvd.nist.gov', 443)[0][4][0])"
docker compose run --rm worker ./scripts/sync-once.sh
docker compose ps
docker compose logs --tail=200 backend frontend reverse-proxy worker scheduler postgres redis
git diff --check
docker compose down
```

## 预期结果

- `make config-check` 在 development `.env` 下通过，且不打印密钥值。
- `make compose-config` 成功渲染 Compose 文件。
- 只有 `reverse-proxy` 发布宿主机端口。PostgreSQL、Redis、backend、frontend、worker 和 scheduler 均保持在 Compose 网络后方。
- PostgreSQL 和 Redis 在 backend、worker、scheduler 启动前变为 healthy。
- 后端迁移通过 `./scripts/migrate.sh` 运行。
- Admin bootstrap 创建或更新配置的管理员，且不打印密码。
- `/api/health` 通过 reverse proxy 返回 `{"status":"ok"}`。
- `/api/ready` 返回 ready 状态，PostgreSQL 和 Redis 标记为 `ok`。
- `/` 通过 reverse proxy 返回 HTTP 200，并提供 Next.js 工作台。
- Worker 日志显示 source sync、raw normalization 和 threat scoring task 已注册。
- Scheduler 日志显示 Celery Beat 使用 Redis 作为 broker。
- Worker one-shot sync 可在容器内解析公共 source hosts，并通过 PostgreSQL 持久化 source/job/raw records。
- 服务日志不包含真实 credentials、tokens、tracebacks 或 database enum cast errors。

## 2026-05-20 备注

- 本地预览使用 `CADDY_HOST=:80`，因此 Caddy 记录 HTTP-only local preview warnings；这是本地验证的预期行为。
- Worker 和 scheduler 需要 `egress` network 执行 live NVD/CISA/RSS/vendor source collection，同时仍使用 internal network 访问 PostgreSQL 和 Redis。
- NVD Connector 使用默认 120 天 `lastMod` window，因为更大窗口会被 NVD API 拒绝。单次运行分页仍有上限。
