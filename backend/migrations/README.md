# 后端数据库迁移

通过既有的项目命令执行迁移：

```bash
make migrate
```

该命令在 backend 服务内运行 `alembic upgrade head`，并从环境变量读取 `DATABASE_URL`。
