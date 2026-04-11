---
phase: 03-web-ui-api
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - app/routes/jobs.py
  - app/templates/jobs.html
  - app/templates/partials/job_list.html
  - app/repository.py
  - app/main.py
  - app/routes/pages.py
  - app/templates/profile.html
  - app/templates/search_config.html
  - app/templates/watch_rules.html
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Nine files reviewed covering the jobs list page, partial templates, repository layer, main app wiring, and stub pages. The overall structure is sound: HTMX partial detection is correct, filter validation is properly typed, and the repository pattern is clean. Three correctness issues were found: posting an empty status value produces a server-side 422 error visible to the user, filter values in the "Load more" URL are not URL-encoded and will break on special characters, and the "latest search config" selection has undefined ordering. Two info-level issues were also found.

## Warnings

### WR-01: Posting Empty Status ("— Set Status —") Returns 422

**File:** `app/templates/partials/job_list.html:24-36`

**Issue:** The status `<select>` for each job card has an option with `value=""` labelled "— Set Status —". When the user changes the select to this option, HTMX fires `hx-post="/jobs/{job_id}/status"` with `status=` (empty string). In `app/routes/jobs.py:91`, `JobStatus("")` raises `ValueError` and the handler returns HTTP 422. The user sees no visible feedback because `hx-swap="none"`, but the POST still fails. In practice, re-selecting the placeholder after having set a real status is a natural action (e.g., "undo").

**Fix:** Either exclude the empty option from triggering a POST (add `hx-trigger="change[this.value != '']"`), or handle the empty string in the route by treating it as a no-op (return 204 immediately):

```html
<!-- Option A: suppress POST when value is empty -->
<select
  hx-post="/jobs/{{ job.id }}/status"
  hx-trigger="change[this.value != '']"
  hx-swap="none"
  name="status"
  ...
>
```

```python
# Option B: in routes/jobs.py, treat empty string as no-op
if not status:
    return Response(status_code=204)
try:
    status_enum = JobStatus(status)
...
```

---

### WR-02: Unencoded Filter Values in "Load More" URL

**File:** `app/templates/partials/job_list.html:48`

**Issue:** The "Load more" button constructs its HTMX URL via direct Jinja2 interpolation:

```
hx-get="/jobs?page={{ page + 1 }}&status={{ filters.status }}&company={{ filters.company }}&salary_min={{ filters.salary_min }}"
```

If `filters.company` contains `&`, `+`, `#`, `%`, or a space, the URL is malformed and either breaks the request or sends incorrect filter values. For example, company name "A&B Corp" would produce `company=A&B Corp`, which the server parses as `company=A` with `B Corp` as an unknown extra parameter.

**Fix:** Use Jinja2's `urlencode` filter (available via `urllib.parse.quote`) or build the URL as a query string. The simplest fix without a custom filter is to add `filters` as a hidden form and use HTMX's `hx-include`, or use the built-in `urlencode` dict filter:

```html
hx-get="/jobs?page={{ page + 1 }}&{{ {'status': filters.status, 'company': filters.company, 'salary_min': filters.salary_min} | urlencode }}"
```

Note: Jinja2's `urlencode` filter is available in Jinja2 >= 2.7 and is enabled by default in FastAPI's `Jinja2Templates`. Verify it is available in the project's Jinja2 version; if not, register a custom filter using `urllib.parse.urlencode`.

---

### WR-03: Undefined Ordering for "Latest" Search Config

**File:** `app/routes/pages.py:17`

**Issue:** `latest_config = configs[-1] if configs else None` assumes the last element of the list returned by `list_search_configs` is the most recently created config. However, `list_search_configs` in `repository.py` has no `ORDER BY` clause, so the order returned by SQLAlchemy depends on the database engine's internal row ordering, which is not guaranteed to be insertion order.

```python
# repository.py:96-100
def list_search_configs(self, active_only: bool = True) -> list[SearchConfig]:
    q = self.session.query(SearchConfig)
    if active_only:
        q = q.filter(SearchConfig.is_active == True)
    return q.all()  # no ORDER BY
```

If a user adds multiple search configs over time, the "latest" shown in the form prefill may be incorrect.

**Fix (Option A):** Add ordering to `list_search_configs`:
```python
return q.order_by(SearchConfig.id.desc()).all()
```
Then use `configs[0]` in `pages.py`.

**Fix (Option B):** Add a dedicated `get_latest_search_config()` repository method:
```python
def get_latest_search_config(self) -> Optional[SearchConfig]:
    return self.session.query(SearchConfig).order_by(SearchConfig.id.desc()).first()
```

---

## Info

### IN-01: Inline Import Inside Route Handler

**File:** `app/routes/pages.py:18`

**Issue:** `from app.routes.scrape import _scrape_status` is placed inside the `search_config` handler function body rather than at module top-level. This is an unusual pattern — Python re-executes the import statement on every request (though Python's import system caches it, so the cost is minimal). The leading underscore on `_scrape_status` signals it is a private implementation detail of the scrape module, yet it is imported across module boundaries. This is a tight coupling between the pages and scrape routers.

**Fix:** Move the import to the top of `pages.py` alongside the other imports, or expose `_scrape_status` via a public accessor function in `scrape.py`:
```python
# In scrape.py
def get_scrape_status() -> dict:
    return _scrape_status

# In pages.py (top-level import)
from app.routes.scrape import get_scrape_status
```

---

### IN-02: LIKE Wildcards Not Escaped in Company Filter

**File:** `app/repository.py:39`

**Issue:** The company filter uses `ilike(f"%{company}%")` with the user-supplied `company` string inserted directly. SQLAlchemy parameterizes the value so there is no SQL injection risk, but SQL `LIKE` wildcards (`%`, `_`) within the `company` string itself are treated as pattern characters. A search for "50%" as a company name would match any company containing "50" followed by any characters, rather than literally "50%".

**Fix:** Escape `%` and `_` in the user input before building the pattern:
```python
escaped = company.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
q = q.filter(Job.company.ilike(f"%{escaped}%", escape="\\"))
```

---

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
