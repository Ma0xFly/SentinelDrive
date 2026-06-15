# Docker Compose Checklist

## 配置

- [ ] `make config-check` 通过。
- [ ] `make compose-config` 通过。
- [ ] `.env` 不包含未替换的生产类占位密钥。
- [ ] `APP_ENV=production`、`prod` 或 `staging` 时，占位密钥校验会失败。

## 服务暴露

- [ ] 只有 `reverse-proxy` 发布宿主机 HTTP/HTTPS 端口。
- [ ] `frontend` 和 `backend` 只通过 Compose `expose` 暴露给内部网络。
- [ ] `postgres`、`redis`、`worker` 和 `scheduler` 没有宿主机端口映射。
- [ ] `worker` 和 `scheduler` 有出站 egress，但没有公网入口。

## 启动

- [ ] PostgreSQL 和 Redis 健康后，backend/worker/scheduler 再启动。
- [ ] `make migrate` 可运行。
- [ ] `make admin-bootstrap` 可运行，且不打印管理员密码。
- [ ] `/api/health` 和 `/api/ready` 可通过 reverse proxy 访问。
- [ ] `/` 返回前端工作台。

## 命令

- [ ] `make logs` 可查看运行栈日志。
- [ ] `make sync-once` 可触发 collection-only 运行。
- [ ] `make process-once` 可触发 collection、normalization、scoring 和 backend alert evaluation。
- [ ] `make down` 不删除持久化 volumes。
