---
phase: 05-watch-rules-notifications
fixed_at: 2026-04-12T00:00:00Z
review_path: .planning/phases/05-watch-rules-notifications/05-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-04-12T00:00:00Z
**Source review:** .planning/phases/05-watch-rules-notifications/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: XSS — unescaped `rule_type` reflected directly into HTML response

**Files modified:** `app/routes/watch.py`
**Commit:** fbacec9
**Applied fix:** Added `import html as html_lib` at the top of the module and wrapped `rule_type` with `html_lib.escape()` in the error `HTMLResponse` f-string, ensuring the raw user input cannot inject HTML/JS regardless of future allowlist changes.

### WR-01: Lock is released in `finally` but acquired only on the happy path — double-release on error

**Files modified:** `app/routes/scrape.py`
**Commit:** 5200f19
**Applied fix:** Moved `_scrape_status["running"] = True` and `_scrape_status["error"] = None` from inside `_run_scrape_task` to the route handler immediately after a successful `_scrape_lock.acquire()`. Removed the now-redundant `global _scrape_status` declaration and the two status assignments from the background task. This closes the TOCTOU window where a rapid second request could slip through while `running` was still `False`.

### WR-02: `/watch-matches` silently marks all notifications read on every GET

**Files modified:** `app/routes/pages.py`
**Commit:** 5f3fcc4
**Applied fix:** Added a guard so `mark_notifications_read()` only fires when `list_unread_notifications_with_jobs()` returns at least one row. Fetches the full list for display afterward. This prevents the badge from dropping to zero on a browser refresh when nothing new was actually viewed.

### WR-03: `health.py` opens a raw `sqlite3` connection without guarding `conn.close()`

**Files modified:** `app/routes/health.py`
**Commit:** 9ee9859
**Applied fix:** Wrapped the sqlite3 connection block in a `try/finally` so `conn.close()` is guaranteed to run even if either `execute` call raises, preventing connection leaks.

### WR-04: `match_new_jobs_to_watch_rules` commits notifications one-by-one inside a loop

**Files modified:** `app/repository.py`, `app/services/watch_service.py`
**Commit:** b9770ae
**Applied fix:** Added `add_notification_no_commit()` to `JobRepository` — a flush-only variant that stages the `Notification` row without committing. Updated `match_new_jobs_to_watch_rules` in `watch_service.py` to call this method in the inner loop and issue a single `session.commit()` after the loop completes (only when at least one notification was created). The original `add_notification()` method is preserved for single-item call sites.

---

_Fixed: 2026-04-12T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
