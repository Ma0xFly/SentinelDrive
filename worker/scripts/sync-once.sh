#!/bin/sh
set -eu

celery -A app.celery_app.celery_app call sentineldrive.sync_sources
