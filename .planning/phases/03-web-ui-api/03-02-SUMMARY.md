---
plan: 03-02
phase: 3
subsystem: web-ui
tags: [routing, templates, navigation, fastapi]
dependency_graph:
  requires: [03-01]
  provides: [pages-router, nav-wiring]
  affects: [app/main.py, app/routes/pages.py, app/templates]
tech_stack:
  added: []
  patterns: [Jinja2 TemplateResponse, APIRouter, nav active-link pattern]
key_files:
  created:
    - app/routes/pages.py
    - app/templates/search_config.html
    - app/templates/profile.html
    - app/templates/watch_rules.html
  modified:
    - app/main.py
decisions:
  - "Used get_session (not get_db) to match existing codebase DB dependency pattern"
  - "pages_router appended last in main.py to avoid route shadowing"
metrics:
  duration: 8m
  completed: 2026-04-12
  tasks_completed: 2
  files_changed: 5
---

# Phase 3 Plan 02: Navigation Wiring — Pages Router, Placeholder Templates, main.py Summary

## One-liner

Pages router wires /profile, /watch-rules, /search-config with Jinja2 templates; all four nav links resolve HTTP 200.

## What Was Built

- `app/routes/pages.py`: APIRouter with three GET handlers; /search-config imports `_scrape_status` from scrape module and renders the full scrape form via `search_config.html`; /profile and /watch-rules render placeholder pages
- `app/templates/search_config.html`: Full scrape form migrated from scrape.html, nav bar added with Search Config active link
- `app/templates/profile.html`: Placeholder with Profile nav active, correct title
- `app/templates/watch_rules.html`: Placeholder with Watch Rules nav active, correct title
- `app/main.py`: pages_router imported and registered as 4th router (health, scrape, jobs, pages)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected DB dependency name**
- **Found during:** Task T01
- **Issue:** Plan code used `get_db` but codebase defines `get_session` in `app/database.py`
- **Fix:** Used `get_session` throughout `pages.py`
- **Files modified:** `app/routes/pages.py`
- **Commit:** b144e6f

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| app/templates/profile.html | "Profile editing coming in Phase 4." | Intentional placeholder; Phase 4 will wire profile data |
| app/templates/watch_rules.html | "Watch rule management coming in Phase 5." | Intentional placeholder; Phase 5 will wire watch rules |

These stubs do not block the plan goal (all nav links resolve HTTP 200). They are tracked for Phase 4/5 implementation.

## Self-Check: PASSED

- app/routes/pages.py: FOUND
- app/templates/search_config.html: FOUND
- app/templates/profile.html: FOUND
- app/templates/watch_rules.html: FOUND
- app/main.py includes pages_router: VERIFIED
- python -c "from app.main import app": exits 0
