#!/bin/sh
set -eu

python -m app.scripts.evaluate_alerts "$@"
