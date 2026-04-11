---
phase: 02
status: findings
critical: 1
high: 2
medium: 2
low: 3
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Seven files were reviewed covering the scraper pipeline, deduplication logic, background task state management, route layer, Jinja2 template, app entrypoint, and requirements. The core `_normalize_row` and `_compute_hash` functions are well-structured and defensively coded. Test coverage for the pure functions is solid. The main concerns are: an XSS vulnerability in the HTMX status route where unsanitized error text is interpolated directly into HTML; a race condition in the module-level `_scrape_status` dict shared between the FastAPI async event loop and a background thread; and missing input validation that can send arbitrary user-supplied strings directly to the JobSpy scraper.

---

## Critical Issues

### CR-01: XSS via Unsanitized Error Message in `/scrape/status` Route

**File:** `app/routes/scrape.py:88-91`

**Issue:** The `error` field of `_scrape_status` is populated directly from `str(e)` (line 33) — which may contain text originating from network responses, filenames, or other attacker-influenced input — and then interpolated raw into an HTML response using an f-string. Because this is returned as `HTMLResponse` (not a Jinja2 template), Jinja2's auto-escaping does NOT apply. Any `<script>` or HTML in the error message is rendered as live markup in the browser.

While the current attack surface is low (single-user local app), this pattern becomes dangerous if the app is ever exposed to a network, and it is an unambiguous coding defect regardless.

```python
# CURRENT — unsafe
error = _scrape_status["error"]
return HTMLResponse(
    f'<div id="scrape-result" class="text-red-600">Error: {error}</div>'
)
```

**Fix:** HTML-escape the error string before interpolation. Use the stdlib `html` module:

```python
import html as html_lib

error = html_lib.escape(_scrape_status["error"])
return HTMLResponse(
    f'<div id="scrape-result" class="text-red-600">Error: {error}</div>'
)
```

The same pattern applies to the `scrape.html` template at line 89 (`{{ status.error }}`), but Jinja2 auto-escapes that output by default, so it is safe there.

---

## High Issues

### HR-01: Race Condition on `_scrape_status` Dict (Thread Safety)

**File:** `app/routes/scrape.py:17-35`

**Issue:** `_scrape_status` is a plain module-level `dict` mutated by `_run_scrape_task`, which runs in a background thread (FastAPI's `BackgroundTasks` dispatches to a threadpool executor). The FastAPI request handlers on the async event loop read this dict concurrently with no locking. In CPython, individual dict key assignments are GIL-protected, but a check-then-act sequence is not atomic:

```python
# lines 68-69 — read
if _scrape_status["running"]:
    ...

# lines 22-23 — write (background thread, concurrently)
_scrape_status["running"] = True
_scrape_status["error"] = None
```

Two rapid POST requests can both pass the `running` check before the background thread sets `running = True`, launching two concurrent scrape tasks that will interleave writes to `_scrape_status` and the database.

**Fix:** Guard concurrent launches with a `threading.Lock`:

```python
import threading
_scrape_lock = threading.Lock()
_scrape_status: dict = {"running": False, "last_result": None, "error": None}

# In scrape_run():
if not _scrape_lock.acquire(blocking=False):
    return HTMLResponse('<div id="scrape-result" class="text-yellow-600">A scrape is already running.</div>')
background_tasks.add_task(_run_scrape_task, keywords, location, experience_level or None)

# In _run_scrape_task():
try:
    _scrape_status["running"] = True
    ...
finally:
    _scrape_status["running"] = False
    _scrape_lock.release()
```

### HR-02: No Input Validation on `keywords` and `location` Before Passing to JobSpy

**File:** `app/routes/scrape.py:51-73`

**Issue:** `keywords` and `location` are accepted as raw form strings with no length limit, character filtering, or sanitization before being passed to `run_scrape` → `scrape_jobs`. JobSpy constructs HTTP requests from these values. Extremely long strings (e.g., 10,000 characters) or special characters could cause unexpected scraper behavior, large log entries, or errors whose messages then surface in the UI.

There is no separate injection risk into the database (SQLAlchemy parameterizes values), but the unvalidated strings go directly into network requests to third-party sites.

**Fix:** Add Pydantic validation at the route level using FastAPI's Form field constraints:

```python
from pydantic import Field
from fastapi import Form
from typing import Annotated

keywords: Annotated[str, Form(min_length=1, max_length=200)]
location: Annotated[str, Form(min_length=1, max_length=200)]
```

---

## Medium Issues

### MD-01: `import math` Inside a Hot Inner Loop

**File:** `app/scraper.py:55`

**Issue:** `import math` is placed inside `_numeric`, which is called once per salary field per scraped row (potentially hundreds of times per scrape run). While CPython caches module imports after the first load and this does not affect correctness, it is an unusual and misleading pattern — any reader unfamiliar with CPython's import cache would assume it is a performance problem.

**Fix:** Move `import math` to the top of the module alongside the other stdlib imports (line 2-3 region).

```python
import hashlib
import logging
import math
from typing import Optional
```

### MD-02: `_scrape_status` State Is Reset Only on New Scrape Start, Not on Server Restart

**File:** `app/routes/scrape.py:17`

**Issue:** The `_scrape_status` dict is module-level and initialized at import time. If the server crashes mid-scrape (while `running=True`), the state is reset on restart because the module is re-imported. This is fine. However, there is no mechanism to recover or surface a partial scrape result if `_run_scrape_task` raises an unhandled exception that escapes the `except Exception` block — for example, a `BaseException` subclass like `KeyboardInterrupt` or `SystemExit`. In that case `running` stays `True` permanently (the `finally` block does set it to `False`, so this is actually safe for most cases). The deeper issue is that `_scrape_status["error"]` is cleared to `None` at the start of every new run (line 24) before the previous result is preserved anywhere. If the UI polls after the new run starts, the previous result is silently lost.

**Fix:** This is acceptable for a single-user POC but worth noting. Consider not clearing `error` until a new result or error is written:

```python
_scrape_status["running"] = True
# Do not clear error/last_result here — clear them only when new data arrives
```

---

## Low Issues

### LW-01: `jobspy` Not Listed in `requirements.txt`

**File:** `requirements.txt`

**Issue:** `jobspy` (from `speedyapply`) is the core scraping dependency and is imported in `app/scraper.py` at line 92. It is not present in `requirements.txt`. A fresh `pip install -r requirements.txt` will succeed but the app will fail at runtime when a scrape is triggered.

**Fix:** Add the pinned package to `requirements.txt`:

```
jobspy>=1.1.79
```

### LW-02: `experience_level` Prepended to `search_term` Without Normalization

**File:** `app/scraper.py:94-97`

**Issue:** When `experience_level` is provided, it is prepended to the keywords string: `f"{experience_level} {keywords}"`. The values come from a `<select>` with options `entry`, `mid`, `senior`, `director`. These abbreviated strings are sent directly to JobSpy/LinkedIn's search. "mid software engineer" or "entry data analyst" are not standard job search phrases and may return poor results compared to "mid-level" or "entry-level". This is a logic quality issue, not a crash.

**Fix:** Map abbreviated levels to search-friendly phrases:

```python
LEVEL_LABELS = {
    "entry": "entry-level",
    "mid": "mid-level",
    "senior": "senior",
    "director": "director",
}
label = LEVEL_LABELS.get(experience_level, experience_level)
search_term = f"{label} {keywords}"
```

### LW-03: Commented-out / Debug Potential — `verbose=0` Silences All JobSpy Output

**File:** `app/scraper.py:112`

**Issue:** `verbose=0` suppresses all JobSpy console output, which is correct for production use. However, there is no fallback diagnostic logging if `df` is empty after scraping (total_scraped == 0 but no error raised). A user triggering a scrape that returns zero results would see "Done! Inserted 0, skipped 0 (from 0 scraped)" with no indication of whether scraping actually reached the sites.

**Fix:** Add a warning log when the result DataFrame is empty:

```python
if total_scraped == 0:
    logger.warning("Scrape returned 0 results for search_term=%r location=%r", search_term, location)
```

---

## Files Reviewed

- `app/scraper.py`
- `scripts/run_scrape.py`
- `tests/test_scraper.py`
- `app/routes/scrape.py`
- `app/templates/scrape.html`
- `app/main.py`
- `requirements.txt`

---

_Reviewed: 2026-04-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
