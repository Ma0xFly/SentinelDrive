---
stage: 7
task: 2
title: Operations Control Surface Backend Slice
agent: backend-agent
status: Success
important_findings: false
compatibility_issues: false
---

# Task 7.2 - Operations Control Surface Backend Slice

## Summary
Implemented authenticated backend operations APIs for viewing processing pipeline status and safely enqueueing the approved processing pipeline task. Added fakeable Celery integration, focused tests, configuration wiring, and operator documentation.

## Details
- Added `GET /sources/pipeline/status` with compact operational counts for pending raw rows, failed raw rows, scoring-pending intelligence rows, open alerts, latest pipeline trigger/job, latest source job, and recent failures.
- Added `POST /sources/pipeline/trigger` accepting only bounded `normalization_limit`, `scoring_limit`, and `alert_limit` values, and enqueueing only `sentineldrive.process_pipeline`.
- Recorded pipeline trigger attempts as source-less `JobLog` rows and audit events using the existing audit pattern without adding migrations or enum values.
- Isolated Celery client behavior behind `PipelineTaskClient` so tests can fake enqueue/status behavior without Redis or a live worker.
- Kept the backend/worker boundary intact: backend enqueues the stable worker task and does not import worker pipeline internals.
- Applied existing safe response patterns and additional internal URL/key filtering so status responses do not expose Redis, database, credential, or raw payload details.

## Output
- Modified `backend/app/api/routes/sources.py`
- Modified `backend/app/api/schemas/sources.py`
- Modified `backend/app/api/deps.py`
- Added `backend/app/services/pipeline.py`
- Modified `backend/app/core/settings.py`
- Modified `backend/requirements.txt`
- Modified `backend/tests/test_sources_api.py`
- Modified `backend/tests/test_settings.py`
- Modified `docker-compose.yml`
- Modified `docs/development.md`
- Modified `docs/environment.md`
- Modified `docs/operations.md`
- Modified `docs/testing.md`
- Commit: `98fe3c7 feat: add operations pipeline api`

## Validation
- Installed backend requirements in the local validation environment with `/home/myx/SentinelDrive/.venv/bin/python -m pip install -r backend/requirements.txt`.
- `PYTHONPATH=backend /home/myx/SentinelDrive/.venv/bin/python -m pytest backend/tests/test_sources_api.py backend/tests/test_settings.py -q` passed: 14 tests.
- `PYTHONPATH=backend /home/myx/SentinelDrive/.venv/bin/python -m compileall backend/app` passed.
- `cd backend && PYTHONPATH=. /home/myx/SentinelDrive/.venv/bin/python -m pytest tests -q` passed: 73 tests, 1 existing multipart deprecation warning.
- `make config-check` passed.
- `make compose-config` passed.
- `git diff --check` passed.

## Issues
None.
