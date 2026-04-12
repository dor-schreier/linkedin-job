---
phase: 05-watch-rules-notifications
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - app/services/watch_service.py
  - app/routes/watch.py
  - app/repository.py
  - app/scraper.py
  - app/main.py
  - app/templates/partials/nav.html
  - app/templates/watch_matches.html
  - app/routes/pages.py
  - app/routes/jobs.py
  - app/routes/scrape.py
  - app/routes/health.py
  - app/templates/watch_rules.html
  - app/templates/jobs.html
  - app/templates/profile.html
  - app/templates/search_config.html
  - app/templates/scrape.html
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-04-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The Phase 05 watch-rules and notifications feature is well-structured. The matching service, repository methods, and routes are clean and follow existing project conventions. The main correctness concerns are: a thread-safety bug in the scrape background-task lock release, an XSS vector in the watch-rule create endpoint, and a mark-all-read side-effect that fires unconditionally on every page load of `/watch-matches`. Three lower-severity issues round out the findings.

---

## Critical Issues

### CR-01: XSS — unescaped `rule_type` reflected directly into HTML response

**File:** `app/routes/watch.py:25`
**Issue:** When `rule_type` fails the allowlist check, the raw form value is interpolated into an HTML string with an f-string and returned as `HTMLResponse`. Although the allowlist blocks anything outside `{"company","keyword","sector"}`, the HTML response is constructed before any sanitization could have run and the value is user-controlled. If the allowlist logic is ever loosened, or if a future code path adds a second route that reuses this pattern without the check, arbitrary HTML/JS can be injected. Defense-in-depth requires escaping here regardless.

**Fix:**
```python
import html as html_lib

if rule_type not in ALLOWED_RULE_TYPES:
    return HTMLResponse(
        f'<div class="text-red-600">Invalid rule_type: {html_lib.escape(rule_type)}</div>',
        status_code=400,
    )
```

---

## Warnings

### WR-01: Lock is released in `finally` but acquired only on the happy path — double-release on error

**File:** `app/routes/scrape.py:24-40`
**Issue:** `_scrape_lock.acquire(blocking=False)` is called in the route handler (line 73). If acquisition succeeds, the background task `_run_scrape_task` releases the lock in its `finally` block (line 40). However, if `run_scrape` raises an exception that escapes the `try/except Exception` in `_run_scrape_task` (which it cannot given the bare `except Exception`, but see below), OR if `background_tasks.add_task` itself raises before the task runs, the lock is acquired but never released, permanently blocking all future scrapes. More practically: the `global _scrape_status` declaration on line 26 is unnecessary (dicts are mutated in-place, not rebound), and setting `_scrape_status["running"] = True` inside the background task creates a TOCTOU window where `_scrape_status["running"]` is still `False` between the lock acquisition in the route and the task starting — so a rapid second request could pass the lock check.

**Fix:** Set `_scrape_status["running"] = True` synchronously in the route handler immediately after a successful `acquire`, before returning, so the state is consistent:

```python
if not _scrape_lock.acquire(blocking=False):
    return HTMLResponse(...)

_scrape_status["running"] = True   # set synchronously here
_scrape_status["error"] = None
background_tasks.add_task(_run_scrape_task, keywords, location, experience_level or None)
```

And remove lines 27-28 from `_run_scrape_task`.

### WR-02: `/watch-matches` silently marks all notifications read on every GET

**File:** `app/routes/pages.py:117`
**Issue:** `repo.mark_notifications_read()` is called unconditionally every time the `/watch-matches` page is loaded. This includes browser tab refreshes, back-button navigation, and any future programmatic fetch. A user who opens the page and immediately refreshes will lose the "new" distinction for items they haven't actually seen yet, and the unread badge in the nav will drop to zero. The intent is clear from the comment on line 115, but the side-effect on a GET request is surprising and irreversible.

**Fix:** Drive mark-as-read via an explicit user action (e.g., a POST endpoint or an HTMX call triggered after the page renders), or at minimum guard it so it only fires when there are unread items and log a warning that this is a destructive GET.

```python
unread = repo.list_unread_notifications_with_jobs()
if unread:
    repo.mark_notifications_read()
rows = repo.list_all_notifications_with_jobs(limit=200)
```

Alternatively, add a `POST /notifications/mark-read` button on the page itself (the endpoint already exists in `watch.py:40`).

### WR-03: `health.py` opens a raw `sqlite3` connection to the same file SQLAlchemy manages — risks WAL corruption under concurrent access

**File:** `app/routes/health.py:22-27`
**Issue:** A second, unmanaged `sqlite3.connect("data/jobs.db")` connection is opened alongside the live SQLAlchemy session pool. In WAL mode this is generally safe for reads, but the path `"data/jobs.db"` is a relative path that resolves relative to the process cwd, which may differ from the SQLAlchemy URL (`sqlite:///data/jobs.db` also resolves relative to cwd, so they should match — but this is fragile). More importantly, the `conn.close()` on line 27 is not inside a `try/finally`, so if either `execute` raises, the connection leaks.

**Fix:**
```python
try:
    conn = sqlite3.connect("data/jobs.db")
    tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    table_count = tables
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    wal_mode = mode == "wal"
finally:
    conn.close()
```

### WR-04: `match_new_jobs_to_watch_rules` commits notifications one-by-one inside a loop — N individual commits for N matches

**File:** `app/services/watch_service.py:46` and `app/repository.py:148-152`
**Issue:** `repo.add_notification(...)` calls `self.session.commit()` and `self.session.refresh(...)` on every iteration. For a scrape that inserts 50 jobs against 10 rules, this is up to 500 separate commits. Since the session is shared with the scraper (passed in from `scraper.py:147`), each intermediate commit also materialises partial notification state visible to concurrent reads.

**Fix:** Flush instead of committing inside `add_notification` when called in a batch context, and commit once after the loop:

```python
# In watch_service.py, after the loop:
session.commit()
```

This requires either a `flush`-only variant of `add_notification`, or moving the commit out of the repository method when called in batch. Simplest approach for a POC: add a `add_notification_no_commit` method and commit once in `match_new_jobs_to_watch_rules`.

---

## Info

### IN-01: Duplicate scrape form between `scrape.html` and `search_config.html`

**File:** `app/templates/scrape.html` and `app/templates/search_config.html`
**Issue:** Both templates contain an identical scrape form (keywords, location, experience_level, work_mode fields posting to `/scrape/run`). Any future change to the form needs to be made twice. There is also a duplicate `templates = Jinja2Templates(...)` instantiation across multiple route files — a minor redundancy but not a bug.

**Fix:** Extract the form into `app/templates/partials/scrape_form.html` and `{% include %}` it from both pages.

### IN-02: `import math` inside a hot inner function

**File:** `app/scraper.py:55`
**Issue:** `import math` is inside `_numeric`, which is a nested function called once per DataFrame row. Python caches module imports so this is not a correctness issue, but it is unconventional and slightly misleading. Move the import to the module top level.

**Fix:**
```python
import math  # at top of file

def _numeric(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None
```

### IN-03: `list_watch_rules(active_only=True)` called on `watch-rules` page but deleted rules are hard-deleted, so inactive rules never appear anywhere

**File:** `app/routes/pages.py:104` and `app/repository.py:138-144`
**Issue:** `delete_watch_rule` hard-deletes the row. `list_watch_rules` has an `active_only` flag that filters on `is_active`, but since deletion removes the row entirely, the flag only matters if rules are ever soft-deactivated (which currently they are not). The `active_only=True` default is dead code for the current usage pattern. This is a minor inconsistency that could confuse future maintainers who add a toggle-active feature.

**Fix:** Either implement soft-delete (set `is_active=False` instead of deleting) to make the flag meaningful, or remove the `active_only` parameter and always return all rules. Given the POC scope, documenting the intent in a comment is acceptable.

---

_Reviewed: 2026-04-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
