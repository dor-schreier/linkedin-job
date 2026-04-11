---
phase: 02
fixed_at: 2026-04-12T00:00:00Z
review_path: .planning/phases/02-scraper-dedup-pipeline/02-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-12T00:00:00Z
**Source review:** `.planning/phases/02-scraper-dedup-pipeline/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: XSS via Unsanitized Error Message in `/scrape/status` Route

**Files modified:** `app/routes/scrape.py`
**Commit:** 3f05c0d
**Applied fix:** Added `import html as html_lib` at the top of the module. In `scrape_status()`, the error string is now escaped with `html_lib.escape()` before interpolation into the `HTMLResponse` f-string, preventing raw HTML/script injection from attacker-influenced error messages.

### HR-01: Race Condition on `_scrape_status` Dict (Thread Safety)

**Files modified:** `app/routes/scrape.py`
**Commit:** 3f05c0d
**Applied fix:** Added `import threading` and a module-level `_scrape_lock = threading.Lock()`. In `scrape_run()`, replaced the `if _scrape_status["running"]` check with `if not _scrape_lock.acquire(blocking=False)` so the lock is atomically acquired before launching the background task. In `_run_scrape_task()`, added `_scrape_lock.release()` in the `finally` block to ensure the lock is always released when the task completes.

### HR-02: No Input Validation on `keywords` and `location` Before Passing to JobSpy

**Files modified:** `app/routes/scrape.py`
**Commit:** 3f05c0d
**Applied fix:** Added `Annotated` to imports and changed `keywords` and `location` parameters in `scrape_run()` from `str = Form(...)` to `Annotated[str, Form(min_length=1, max_length=200)]`. FastAPI/Pydantic now rejects requests with empty or overly long strings before they reach the scraper.

---

_Fixed: 2026-04-12T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
