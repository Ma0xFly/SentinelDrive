#!/bin/sh
set -eu

docker compose run --rm backend ./scripts/migrate.sh
