---
plan: 03-01
phase: 3
subsystem: web-ui
tags: [jobs-list, htmx, jinja2, repository, fastapi]
dependency_graph:
  requires: []
  provides: [GET /jobs, POST /jobs/{id}/status, job list page, filter bar, status update]
  affects: [app/main.py, app/repository.py, app/routes/jobs.py, app/templates/jobs.html, app/templates/partials/job_list.html]
tech_stack:
  added: []
  patterns: [HTMX partial swap via HX-Request header, Jinja2 include for partial reuse, FastAPI Form dependency for POST body]
key_files:
  created:
    - app/routes/jobs.py
    - app/templates/jobs.html
    - app/templates/partials/job_list.html
  modified:
    - app/repository.py
    - app/main.py
decisions:
  - use get_session (not get_db) matching existing scrape.py pattern
  - partial template reused via Jinja2 include on full load and swapped on HTMX request
metrics:
  duration: ~15min
  completed: 2026-04-12
  tasks_completed: 3
  files_changed: 5
---

# Phase 3 Plan 01: Jobs List Page — Repository, Route, Template Summary

**One-liner:** Filterable, paginated jobs list with HTMX partial updates, per-card status dropdowns, and salary-conditional rendering via FastAPI + Jinja2.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 03-01-T01 | Extend list_jobs with company/salary_min filters + count_jobs_filtered | f180b41 |
| 03-01-T02 | Create GET /jobs and POST /jobs/{id}/status routes | a736780 |
| 03-01-T03 | Create jobs.html, partials/job_list.html, register router in main.py | e8c9e79 |

## Verification Results

- GET /jobs returns HTTP 200 with `id="job-list"` in HTML
- HTMX partial (HX-Request: true) returns partial template without wrapper div (job-list count: 0)
- POST /jobs/1/status with invalid value returns HTTP 422
- Server imports cleanly: `from app.routes.jobs import router` exits 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed missing get_db import**
- **Found during:** Task 2
- **Issue:** Plan referenced `from app.database import get_db` but the actual function is named `get_session` (visible in app/routes/scrape.py)
- **Fix:** Replaced `get_db` with `get_session` in both route handlers
- **Files modified:** app/routes/jobs.py
- **Commit:** a736780

**2. [Rule 2 - Missing] Register jobs router in main.py**
- **Found during:** Task 3
- **Issue:** Plan specified creating the router but did not include a task to register it in app/main.py — without this the routes would be unreachable
- **Fix:** Added `from app.routes.jobs import router as jobs_router` and `app.include_router(jobs_router)` to main.py
- **Files modified:** app/main.py
- **Commit:** e8c9e79

## Known Stubs

None — all data is sourced from the database via JobRepository. Empty state renders correctly when no jobs exist.

## Threat Surface Scan

No new network endpoints beyond those declared in the plan's threat model. T-03-01, T-03-02, T-03-03 all mitigated:
- Status validated against JobStatus enum (422 on invalid)
- Company passed as SQLAlchemy bound parameter via ilike()
- salary_min cast to float with try/except (422 on non-numeric)

## Self-Check: PASSED

- app/routes/jobs.py: FOUND
- app/templates/jobs.html: FOUND
- app/templates/partials/job_list.html: FOUND
- app/repository.py count_jobs_filtered: FOUND
- Commits f180b41, a736780, e8c9e79: FOUND
