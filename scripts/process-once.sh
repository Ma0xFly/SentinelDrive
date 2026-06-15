#!/bin/sh
set -eu

docker compose run --rm worker ./scripts/process-once.sh
docker compose run --rm backend ./scripts/evaluate-alerts.sh
