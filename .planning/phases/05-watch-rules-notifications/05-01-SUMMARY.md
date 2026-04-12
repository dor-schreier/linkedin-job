---
phase: 5
plan: 01
subsystem: watch-rules-notifications
tags: [watch-rules, notifications, backend, scraper]
dependency_graph:
  requires: []
  provides: [watch-service, watch-routes, notification-count-endpoint]
  affects: [app/scraper.py, app/main.py]
tech_stack:
  added: []
  patterns: [repository-pattern, fastapi-router, post-scrape-hook]
key_files:
  created:
    - app/services/watch_service.py
    - app/routes/watch.py
  modified:
    - app/repository.py
    - app/scraper.py
    - app/main.py
decisions:
  - "Import match_new_jobs_to_watch_rules inside run_scrape function body (deferred import) to avoid circular imports"
metrics:
  duration: ~10min
  completed: 2026-04-12
  tasks_completed: 2
  files_changed: 5
---

# Phase 5 Plan 01: Watch Rules Backend Summary

Watch rules CRUD + post-scrape notification matching backend using existing WatchRule/Notification models with repository pattern extension.

## What Was Built

- `app/services/watch_service.py`: `_matches()` helper (company exact, keyword title-substring, sector description-substring, all case-insensitive) and `match_new_jobs_to_watch_rules(session, new_job_ids)` that creates Notification rows for every matching (rule, job) pair, skipping duplicates.
- `app/repository.py`: Four new methods — `get_jobs_by_ids`, `list_unread_notifications_with_jobs`, `list_all_notifications_with_jobs`, `notification_exists` — needed by the service and by Plan 02's UI layer.
- `app/routes/watch.py`: Four endpoints — `POST /watch-rules/create`, `POST /watch-rules/{id}/delete`, `POST /notifications/mark-read`, `GET /api/notifications/unread-count` — with input validation on rule_type.
- `app/scraper.py`: `run_scrape` now collects inserted job ids, calls `match_new_jobs_to_watch_rules` after the insert loop, and includes `notifications_created` in the returned summary dict.
- `app/main.py`: `watch_router` registered immediately after `pages_router`.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check

### Files exist
- app/services/watch_service.py: FOUND
- app/routes/watch.py: FOUND
- app/repository.py (modified): FOUND
- app/scraper.py (modified): FOUND
- app/main.py (modified): FOUND

### Commits exist
- c99cba2: feat(05-01): extend repository + add watch matching service
- 10a7c64: feat(05-01): wire watch matching into scraper + create watch/notifications routes

## Self-Check: PASSED
