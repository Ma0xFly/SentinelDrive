# Backend Migrations

Run migrations through the existing project command:

```bash
make migrate
```

The command runs `alembic upgrade head` inside the backend service and reads `DATABASE_URL` from the environment.
