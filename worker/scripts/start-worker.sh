#!/bin/sh
set -eu

exec celery -A app.celery_app.celery_app worker --loglevel="${CELERY_LOG_LEVEL:-INFO}" --concurrency="${CELERY_WORKER_CONCURRENCY:-2}"
