# 安全与密钥 Checklist

## 密钥

- [ ] `.env` 未提交。
- [ ] `APP_SECRET_KEY`、`POSTGRES_PASSWORD`、`DATABASE_URL`、`ADMIN_BOOTSTRAP_PASSWORD` 和 `NVD_API_KEY` 未出现在代码、文档示例或日志中。
- [ ] `make config-check` 在生产类环境下会拒绝占位密钥。
- [ ] Admin bootstrap 不打印明文密码，只保存密码哈希。

## 服务暴露

- [ ] 只有 `reverse-proxy` 发布公网端口。
- [ ] PostgreSQL 和 Redis 不发布宿主机端口。
- [ ] Worker 和 scheduler 不暴露公网入口。
- [ ] 前端只接收 `NEXT_PUBLIC_API_BASE_URL`。

## 数据处理

- [ ] API 响应不包含 raw payloads 或 collector secrets。
- [ ] Export outputs 省略未脱敏 credentials、tokens 和疑似密钥值。
- [ ] HTML/PDF 来源默认 metadata-only retention。
- [ ] 操作日志记录关键动作，但不记录明文密钥。

## 文档声明

- [ ] 文档命令不要求打印 `.env`。
- [ ] 分享日志前有密钥扫描步骤。
- [ ] 备份文件被视为内部敏感数据，不提交、不公开附件。
