---
phase: 02-scraper-dedup-pipeline
verified: 2026-04-12T00:00:00Z
status: human_needed
score: 9/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open http://127.0.0.1:8000/scrape in browser, submit form, verify HTMX polling updates without page reload"
    expected: "Form renders with pre-filled search config; after clicking Run Scrape the status area shows 'Scrape started...' then transitions to results; refreshing shows pre-filled fields"
    why_human: "HTMX polling behavior and live DOM swaps cannot be verified programmatically without a browser; user confirmed this in plan 02-02 Task 2 human-verify checkpoint"
---

# Phase 2: Scraper + Dedup Pipeline Verification Report

**Phase Goal:** Jobs flow from JobSpy through deduplication and into the database, validated without a UI
**Verified:** 2026-04-12
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can trigger a scrape run (via UI button or CLI) that fetches jobs from LinkedIn, Indeed, and Glassdoor | VERIFIED | `app/scraper.py:106` calls `scrape_jobs(site_name=["linkedin", "indeed", "glassdoor"])`. POST /scrape/run route confirmed in `app/routes/scrape.py`. `/scrape/run` route in registered routes. |
| 2 | Running the same scrape twice does not produce duplicate rows — jobs already in the DB are silently skipped | VERIFIED | `_compute_hash` produces SHA-256 of `title\|company\|location`. `run_scrape` calls `repo.get_job_by_hash()` before `repo.add_job()`, skipping on match. 12 unit tests confirm hash determinism. |
| 3 | Each stored job carries: title, company, location, description, source, apply URL, scraped date | VERIFIED | `_normalize_row` extracts all required fields. `Job` model has all columns. `scraped_at` is set by `server_default=func.now()` on insert. |
| 4 | Search configuration (keywords, location, experience level, work mode) is saved and pre-filled on next visit | VERIFIED | POST /scrape/run calls `repo.add_search_config(...)` with all four fields. GET /scrape loads `list_search_configs()` and passes `latest_config` to template. Template uses `{{ latest_config.keywords if latest_config }}` etc. |
| 5 | A scrape triggered from the browser returns immediately; progress is visible without blocking the page | VERIFIED (code) / NEEDS HUMAN (browser) | `background_tasks.add_task(_run_scrape_task, ...)` queues the scrape asynchronously. POST returns HTTP 200 immediately with HTMX polling div. Template polls `/scrape/status` every 2s. Browser confirmation noted in SUMMARY-02-02 as human-verify checkpoint approved by user. |

**Plan 01 must-haves:**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | run_scrape() calls JobSpy with linkedin, indeed, glassdoor sites | VERIFIED | `app/scraper.py:106` — confirmed exact list in `site_name` argument |
| 7 | Fully remote jobs are filtered out before insertion | VERIFIED | `_normalize_row` returns `None` when `row.get("is_remote") is True` (line 28–29). Test `test_normalize_row_filters_remote` passes. |
| 8 | Duplicate jobs (same title+company+location) are skipped via SHA-256 hash | VERIFIED | `_compute_hash` + `get_job_by_hash` guard before `add_job`. Unit tests confirm determinism, case-insensitivity, whitespace normalization. |
| 9 | NaN and missing DataFrame values never reach the database | VERIFIED | `_str()` helper coerces NaN strings to ""; `_numeric()` helper returns None for NaN floats. Tests cover NaN string fields, NaN salary fields, missing fields, None values — all 12 pass. |
| 10 | experience_level is embedded in search_term when provided | VERIFIED | `run_scrape:95-96` — `search_term = f"{experience_level} {keywords}"` when experience_level is truthy |

**Score:** 9/10 truths programmatically verified (truth 5 needs browser confirmation, already approved by user in plan 02-02)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/scraper.py` | Scraper service with run_scrape(), _compute_hash(), _normalize_row() | VERIFIED | 161 lines; all three functions present and substantive; uses defensive .get() access (11 occurrences) |
| `scripts/run_scrape.py` | CLI validation entrypoint | VERIFIED | Exists; imports run_scrape, calls init_db(), main() guard present |
| `tests/test_scraper.py` | Unit tests for hash and normalization | VERIFIED | 12 tests, all passing |
| `app/routes/scrape.py` | POST /scrape/run, GET /scrape/status, GET /scrape | VERIFIED | All three routes implemented; background task, status dict, concurrent rejection all present |
| `app/templates/scrape.html` | Search config form + HTMX status polling | VERIFIED | Form with keywords, location, experience_level, work_mode fields; hx-post="/scrape/run", polling div present |
| `app/main.py` | Scrape router registered | VERIFIED | `from app.routes.scrape import router as scrape_router` + `app.include_router(scrape_router)` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/scraper.py` | `app/repository.py` | `repo.add_job()` and `repo.get_job_by_hash()` | VERIFIED | Lines 137-141: both calls present inside `run_scrape` |
| `app/scraper.py` | `app/database.py` | `SessionLocal()` context manager | VERIFIED | Line 121: `with SessionLocal() as session:` |
| `app/routes/scrape.py` | `app/scraper.py` | `background_tasks.add_task` calling `_run_scrape_task` | VERIFIED | Line 73: `background_tasks.add_task(_run_scrape_task, ...)`. `_run_scrape_task` calls `run_scrape()` on line 26 |
| `app/routes/scrape.py` | `app/repository.py` | SearchConfig persistence | VERIFIED | Lines 60-66: `repo.add_search_config(...)`. Line 41: `repo.list_search_configs(...)` |
| `app/main.py` | `app/routes/scrape.py` | `include_router` | VERIFIED | `app.include_router(scrape_router)` line 16 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/templates/scrape.html` | `latest_config` | `repo.list_search_configs()` -> SQLAlchemy query on `search_configs` table | Yes — DB query returns ORM objects | FLOWING |
| `app/templates/scrape.html` | `status` | `_scrape_status` module-level dict updated by `_run_scrape_task` | Yes — populated by actual `run_scrape()` return value | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 12 unit tests pass | `python -m pytest tests/test_scraper.py -v` | 12 passed in 0.39s | PASS |
| All three scrape routes registered | `python -c "from app.main import app; routes=[r.path for r in app.routes]; print(routes)"` | `[..., '/scrape', '/scrape/run', '/scrape/status']` | PASS |
| scrape.py imports cleanly | `from app.routes.scrape import router` | No error | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SRCH-01 | 02-01-PLAN | User can define search keywords | SATISFIED | `keywords` param in `run_scrape()`; form field in scrape.html |
| SRCH-02 | 02-01-PLAN | User can define target location | SATISFIED | `location` param in `run_scrape()`; form field in scrape.html |
| SRCH-03 | 02-01-PLAN | User can filter by experience level | SATISFIED | `experience_level` prepended to `search_term` in `run_scrape()`; select field in scrape.html |
| SRCH-04 | 02-01-PLAN | User can filter by work mode (exclude fully remote) | SATISFIED | `_normalize_row` returns None when `is_remote is True`; work_mode field in form (onsite/hybrid options only) |
| SRCH-05 | 02-02-PLAN | User can save search config and reuse across scrape runs | SATISFIED | `repo.add_search_config()` on every POST /scrape/run; `repo.list_search_configs()` + template pre-fill on GET /scrape |
| SRCH-06 | 02-02-PLAN | User can trigger a manual scrape run from the UI | SATISFIED | "Run Scrape" button in scrape.html posts to /scrape/run; background task queued |
| SCRP-01 | 02-01-PLAN | App scrapes from LinkedIn, Indeed, and Glassdoor | SATISFIED | `site_name=["linkedin", "indeed", "glassdoor"]` in `scrape_jobs()` call |
| SCRP-02 | 02-01-PLAN | Jobs deduplicated across sources via hash on title+company+location | SATISFIED | `_compute_hash` SHA-256 + `get_job_by_hash` guard before insert |

All 8 requirement IDs declared in plan frontmatter are accounted for. No orphaned requirements found for Phase 2.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Scanned `app/scraper.py`, `app/routes/scrape.py`, `app/templates/scrape.html` for TODO/FIXME, `return null/[]/{}`, hardcoded empty data, placeholder text. No blockers or warnings found. `return {}` in `_scrape_status` init is a state container, not a stub — gets populated by real scrape results.

### Human Verification Required

#### 1. HTMX Polling and Live Status Updates

**Test:** Start the server (`python -m uvicorn app.main:app --reload`), open http://127.0.0.1:8000/scrape, submit the form with valid keywords and location, watch the status div.
**Expected:** Status area shows "Scrape started..." immediately, then auto-updates without page reload to show results (Inserted N, skipped N). Refreshing the page pre-fills keywords/location from the last saved config.
**Why human:** DOM mutations from HTMX polling cannot be verified by grep or imports. The user already approved this in plan 02-02 Task 2 human-verify checkpoint (noted in SUMMARY), but a fresh browser confirmation is recommended before marking the phase fully passed.

### Gaps Summary

No programmatic gaps found. All artifacts exist, are substantive, are wired, and data flows through them. All 8 requirement IDs are satisfied. All 12 unit tests pass. All three scrape routes are registered and importable.

The only remaining item is browser-level confirmation of HTMX polling behavior (Truth 5). The SUMMARY documents this was approved by the user during the plan 02-02 human-verify checkpoint. If that approval stands, this phase can be considered fully passed.

---

_Verified: 2026-04-12_
_Verifier: Claude (gsd-verifier)_
