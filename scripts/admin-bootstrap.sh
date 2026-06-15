#!/bin/sh
set -eu

docker compose run --rm backend ./scripts/admin-bootstrap.sh
