---
phase: 04-profile-ai-scoring
reviewed: 2026-04-12T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - app/database.py
  - app/models.py
  - app/repository.py
  - app/services/__init__.py
  - app/services/groq_service.py
  - app/routes/pages.py
  - app/routes/jobs.py
  - app/main.py
  - tests/test_groq_service.py
  - tests/test_repository_phase4.py
  - tests/test_routes_phase4.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-12
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 4 adds Groq-powered fit scoring and profile recommendations on top of the existing scraper/repository stack. The overall structure is clean: the `groq_service` module is well-isolated, error handling returns safe fallbacks rather than raising, and the route layer correctly separates validation from persistence. Tests cover the main paths including exception swallowing and label thresholds.

Three warnings are worth fixing before relying on the feature in production use: a logic error in salary formatting that silently drops a `$0` minimum (unlikely but latent), a broad `except Exception: pass` in the migration path that can mask serious database errors, and a missing `None`-check on the `profile` object after a fire-and-forget `upsert_profile` call in the analyze route. The info items are low-priority cleanup.

---

## Warnings

### WR-01: Falsy-zero bug in salary formatting silently drops valid salary_min=0

**File:** `app/services/groq_service.py:89-91`

**Issue:** `_format_listed_salary` checks `if smin and smax:` and `if smin:`. Python treats `0` as falsy, so a job with `salary_min=0` (or any zero value) will never produce a listed salary string, causing the prompt to say "not listed" and the model to generate an estimate when one already exists. While `salary_min=0` is rare in practice, the same bug also fires for `salary_min=0.0` coming from JobSpy's pandas conversion.

**Fix:**
```python
# Replace truthiness checks with explicit None checks
if smin is not None and smax is not None:
    return f"{cur}{int(smin):,} - {cur}{int(smax):,}"
if smin is not None:
    return f"{cur}{int(smin):,}+"
return None
```

---

### WR-02: Broad `except Exception: pass` in migration swallows real errors

**File:** `app/database.py:49-53`

**Issue:** The `ALTER TABLE` migration catches all exceptions with a silent `pass`. SQLite's only expected failure here is `OperationalError: duplicate column name`. All other exceptions — disk full, permissions failure, corrupted database, wrong table name — are silently ignored, leaving the app running with a broken schema and no log entry to diagnose the problem.

**Fix:**
```python
from sqlalchemy.exc import OperationalError

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
        conn.commit()
    except OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise  # unexpected error — let it surface
```

---

### WR-03: Unguarded `profile` access after conditional upsert in analyze route

**File:** `app/routes/pages.py:85-89`

**Issue:** When Groq returns an empty bullet list (`bullets` is falsy), the route falls through to line 89 and accesses `profile.ai_recommendations`. At this point `profile` was fetched on line 71 and is known to be non-None (because the guard on line 72 confirmed it). However, the `repo.get_profile()` call on line 85 returns `Optional[Profile]` and reassigns `profile`. If that second fetch returns `None` for any reason (e.g., a concurrency edge case), line 89 will raise `AttributeError` and return a 500 instead of a graceful response.

**Fix:**
```python
if bullets:
    repo.upsert_profile(ai_recommendations="\n".join(bullets))
    profile = repo.get_profile()
# Use the original profile reference as fallback
existing_bullets = _split_bullets(profile.ai_recommendations) if profile else []
return templates.TemplateResponse(
    request,
    "partials/ai_insights.html",
    {"bullets": bullets or existing_bullets},
)
```

---

## Info

### IN-01: `_get_client()` creates a new HTTP client on every Groq call

**File:** `app/services/groq_service.py:47-49`

**Issue:** A new `Groq(...)` instance (and underlying HTTP connection pool) is instantiated for every `get_fit_score_and_salary` and `get_profile_recommendations` call. For a personal-use app this is harmless, but if batch scoring many jobs the overhead accumulates.

**Fix:** Move the client to a module-level singleton, or pass it in for easier testing:
```python
_client: Groq | None = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client
```

---

### IN-02: Missing GROQ_API_KEY produces an unhelpful error at call time, not startup

**File:** `app/services/groq_service.py:49`

**Issue:** `os.environ.get("GROQ_API_KEY")` returns `None` when the key is absent. The `Groq` SDK will accept `None` at construction and only fail at the first API call with an authentication error. For a local app that depends on this key, a startup check would make configuration errors obvious immediately.

**Fix:** Add an early check in `app/main.py` lifespan or log a warning at module load:
```python
# In groq_service.py at module level
if not os.environ.get("GROQ_API_KEY"):
    logger.warning("GROQ_API_KEY is not set — Groq calls will fail")
```

---

### IN-03: In-function import couples `search_config` route to scrape module internals

**File:** `app/routes/pages.py:23`

**Issue:** `from app.routes.scrape import _scrape_status` imports a private (underscore-prefixed) name from a sibling module, inside a function body. This is a hidden coupling: if `_scrape_status` is renamed or moved, the failure is a runtime `ImportError` rather than a static analysis error.

**Fix:** Either expose `_scrape_status` as a public module attribute, or pass the status value through a shared state object (e.g., a small `state.py` module).

---

### IN-04: `database.py` uses relative path for SQLite file resolved at import time

**File:** `app/database.py:5-7`

**Issue:** `DATABASE_PATH = "data/jobs.db"` and the corresponding `os.makedirs("data", exist_ok=True)` resolve relative to the current working directory when the module is first imported. If the app is started from a directory other than the project root (e.g., `python -m app.main` from a subdirectory), the database will be created in the wrong location.

**Fix:** Pin the path to the project root using `__file__`:
```python
import pathlib
_ROOT = pathlib.Path(__file__).parent.parent  # project root
DATABASE_PATH = str(_ROOT / "data" / "jobs.db")
os.makedirs(_ROOT / "data", exist_ok=True)
```

---

_Reviewed: 2026-04-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
