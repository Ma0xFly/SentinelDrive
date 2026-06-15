#!/bin/sh
set -eu

docker compose run --rm worker ./scripts/sync-once.sh
