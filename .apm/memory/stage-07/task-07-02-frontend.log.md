---
stage: 7
task: 2
title: Operations Control Surface - Frontend Slice
agent: frontend-agent
status: Success
important_findings: false
compatibility_issues: false
---

# Task 7.2 - Operations Control Surface - Frontend Slice

## Summary
Added a Chinese operations control surface to the existing `/sources` workbench so authenticated operators can inspect processing status, trigger the approved pipeline flow, refresh source/status data, and run backend alert evaluation as a separate action.

## Details
Implemented the new API helpers through the existing `apiClient` path, preserving token handling and normalized API error behavior. Integrated the operations surface directly into `frontend/app/sources/SourcesWorkbench.js` rather than adding a separate marketing-style route.

The panel shows dense summaries for pending raw rows, failed raw rows, scoring-pending intelligence, open alerts, latest processing/source runs, and recent failures. Rendering is defensive against optional or refined backend field names, while also matching the backend companion schema observed in the parallel worktree: `pending_raw_rows`, `failed_raw_rows`, `scoring_pending_intelligence_rows`, `open_alerts`, `latest_pipeline_job`, `latest_source_job`, and `recent_failures`.

Manual trigger actions disable while in flight to prevent duplicate clicks. Pipeline processing and alert evaluation are labeled separately so the UI does not imply worker processing always creates alerts. Failure text is rendered from sanitized summary fields only and hides obvious credential/token strings.

## Output
Modified files:

- `frontend/lib/endpoints.js`
- `frontend/app/sources/SourcesWorkbench.js`
- `frontend/app/globals.css`

Commit:

- `94a5c07 feat: add operations control surface`

## Validation
Passed:

- `cd frontend && npm ci` - installed locked frontend dependencies; audit reported 0 vulnerabilities.
- `cd frontend && npm run check` - Next.js production build passed for `/`, `/_not-found`, `/alerts`, `/intelligence/[id]`, `/manual-entry`, `/sources`, and `/user`.
- `git diff --check` - passed.

## Issues
None.
