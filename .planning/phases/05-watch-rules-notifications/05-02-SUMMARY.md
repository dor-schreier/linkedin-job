---
phase: 5
plan: 02
subsystem: frontend/templates
tags: [watch-rules, watch-matches, nav, htmx, jinja2]
dependency_graph:
  requires: [05-01-PLAN.md]
  provides: [watch-rules-ui, watch-matches-ui, shared-nav-partial]
  affects: [all-page-templates]
tech_stack:
  added: []
  patterns: [shared-nav-partial, _ctx-helper, include-partial]
key_files:
  created:
    - app/templates/partials/nav.html
    - app/templates/watch_matches.html
  modified:
    - app/routes/pages.py
    - app/routes/jobs.py
    - app/routes/scrape.py
    - app/routes/health.py
    - app/templates/watch_rules.html
    - app/templates/jobs.html
    - app/templates/profile.html
    - app/templates/search_config.html
    - app/templates/scrape.html
    - app/templates/health.html
decisions:
  - Replaced inline nav blocks in search_config.html, scrape.html, health.html with shared partial (nav block was absent from scrape.html and health.html — added partial directly after body open)
metrics:
  duration: ~15m
  completed: 2026-04-12
  tasks_completed: 2
  files_changed: 10
---

# Phase 5 Plan 02: Watch Rules + Matches UI Summary

Shared nav partial with unread-count badge wired into every full-page route; watch_rules.html rewritten with CRUD form; watch_matches.html created; all existing templates updated to use the shared partial.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Shared nav partial + _ctx helper | a32807a |
| 2 | Rewrite watch templates + swap nav partial | cb10555 |

## What Was Built

- `app/templates/partials/nav.html`: shared nav with Matches link and red unread-count badge driven by `{{ unread_count }}`
- `app/routes/pages.py`: `_ctx()` helper, `watch_rules_page` (GET /watch-rules), `watch_matches_page` (GET /watch-matches) — marks notifications read on view so badge resets
- All four full-page route files (`pages.py`, `jobs.py`, `scrape.py`, `health.py`) use `_ctx()` to inject `active` and `unread_count` into every full-page TemplateResponse
- HTMX partial branches remain untouched
- `watch_rules.html`: working CRUD UI (create form + delete per rule)
- `watch_matches.html`: list of matched notifications joined with jobs and rules
- All five existing page templates (`jobs`, `profile`, `search_config`, `scrape`, `health`) replaced inline nav or added nav partial

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing feature] scrape.html and health.html had no nav at all**
- **Found during:** Task 2
- **Issue:** `scrape.html` had no `<nav>` block (page opened directly into content), `health.html` was a bare unstyled page with no nav
- **Fix:** Added `{% include "partials/nav.html" %}` after `<body>` open in both files; upgraded `health.html` to Tailwind-styled layout matching the rest of the app
- **Files modified:** `app/templates/scrape.html`, `app/templates/health.html`
- **Commit:** cb10555

## Self-Check: PASSED

- app/templates/partials/nav.html: FOUND
- app/templates/watch_matches.html: FOUND
- app/templates/watch_rules.html contains /watch-rules/create: FOUND
- All pages return 200 with "Matches" in response: VERIFIED (all pages ok)
- Commits a32807a and cb10555: FOUND
