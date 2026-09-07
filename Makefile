COMPOSE ?= docker compose

.PHONY: compose-config config-check up down logs backend-test frontend-check migrate admin-bootstrap sync-once process-once worker scheduler

compose-config:
	$(COMPOSE) config

config-check:
	./scripts/config-check.sh

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

backend-test:
	$(COMPOSE) run --rm backend python -m pytest

frontend-check:
	cd frontend && pnpm build

migrate:
	$(COMPOSE) run --rm backend ./scripts/migrate.sh

admin-bootstrap:
	$(COMPOSE) run --rm backend ./scripts/admin-bootstrap.sh

sync-once:
	$(COMPOSE) run --rm worker ./scripts/sync-once.sh

process-once:
	$(COMPOSE) run --rm worker ./scripts/process-once.sh
	$(COMPOSE) run --rm backend ./scripts/evaluate-alerts.sh

worker:
	$(COMPOSE) run --rm worker ./scripts/start-worker.sh

scheduler:
	$(COMPOSE) run --rm scheduler ./scripts/start-scheduler.sh
