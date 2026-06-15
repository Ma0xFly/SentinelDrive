#!/bin/sh
set -eu

exec celery -A app.celery_app.celery_app beat --loglevel="${CELERY_LOG_LEVEL:-INFO}"
