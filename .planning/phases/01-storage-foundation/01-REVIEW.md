---
phase: 01-storage-foundation
reviewed: 2026-04-11T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - app/__init__.py
  - app/database.py
  - app/main.py
  - app/models.py
  - app/repository.py
  - app/routes/__init__.py
  - app/routes/health.py
  - app/templates/health.html
  - .env.example
  - .gitignore
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This is a clean, well-structured storage foundation. The ORM models are sensibly designed, the repository pattern is correctly applied, and the FastAPI lifespan setup is correct. The main concerns are: a raw sqlite3 connection in the health route that is never closed on error (resource leak), missing foreign key enforcement for the Notification table (referential integrity gap), and the `get_session` generator not committing or rolling back — which means callers that mutate outside the repository have no implicit transaction guard.

---

## Critical Issues

### CR-01: Raw sqlite3 connection in health route not closed on exception

**File:** `app/routes/health.py:17`
**Issue:** `sqlite3.connect("data/jobs.db")` is called directly. If any line between `connect()` and `conn.close()` raises an exception, the connection is never closed. Over repeated requests this leaks file descriptors and can lock the WAL files, blocking the main SQLAlchemy engine.
**Fix:**
```python
if db_exists:
    with sqlite3.connect("data/jobs.db") as conn:
        tables = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        table_count = tables
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        wal_mode = mode == "wal"
```
`sqlite3.connect` used as a context manager closes the connection when the block exits (even on exception).

---

## Warnings

### WR-01: Notification table has no foreign key constraints

**File:** `app/models.py:87-88`
**Issue:** `job_id` and `watch_rule_id` on `Notification` are plain `Integer` columns with no `ForeignKey` reference. SQLite does not enforce referential integrity by default, and SQLAlchemy will not create FK constraints unless declared. Deleting a `Job` or `WatchRule` row leaves orphaned `Notification` rows that will silently return stale data in later phases when notifications are rendered.
**Fix:**
```python
from sqlalchemy import ForeignKey

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    watch_rule_id = Column(Integer, ForeignKey("watch_rules.id", ondelete="CASCADE"), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
```
Also enable FK enforcement in the connect event:
```python
cursor.execute("PRAGMA foreign_keys=ON")
```

### WR-02: `get_session` generator does not rollback on exception

**File:** `app/database.py:32-38`
**Issue:** The `get_session` generator only calls `session.close()` in the `finally` block. If a caller raises an exception mid-transaction (e.g., a constraint violation), the session is closed without an explicit rollback. SQLAlchemy will roll back on close, but the intent is unclear and any code that catches the exception and continues with the same session will see a broken transaction state.
**Fix:**
```python
def get_session():
    """Generator that yields a database session and closes it after use."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### WR-03: `add_job` accepts arbitrary `**kwargs` with no validation

**File:** `app/repository.py:16-21`
**Issue:** `add_job(**kwargs)` passes all keyword arguments directly to `Job(...)`. There is no check that the required field `job_hash` is present, nor that unknown keys are rejected. Passing an unexpected key will raise a `TypeError` from SQLAlchemy with no descriptive message, and omitting `job_hash` will fail with a NOT NULL constraint violation at the DB level rather than a clear application error.
**Fix:** Add an explicit guard for the required field, or accept typed parameters rather than `**kwargs`:
```python
def add_job(self, **kwargs) -> Job:
    if "job_hash" not in kwargs:
        raise ValueError("job_hash is required for deduplication")
    job = Job(**kwargs)
    self.session.add(job)
    self.session.commit()
    self.session.refresh(job)
    return job
```

---

## Info

### IN-01: `DATABASE_URL` in `.env.example` is unused

**File:** `.env.example:2`
**Issue:** `DATABASE_URL=sqlite:///data/jobs.db` is defined in `.env.example` but `app/database.py` hardcodes `DATABASE_PATH = "data/jobs.db"` and never reads this environment variable. The example file implies configuration that does not actually work, which is misleading.
**Fix:** Either remove `DATABASE_URL` from `.env.example` and add a comment that the DB path is fixed, or update `database.py` to read it:
```python
import os
DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///data/jobs.db").replace("sqlite:///", "")
```

### IN-02: Health route uses hardcoded paths inconsistent with `database.py`

**File:** `app/routes/health.py:13,17`
**Issue:** `os.path.exists("data/jobs.db")` and `sqlite3.connect("data/jobs.db")` duplicate the path string `"data/jobs.db"` that is already defined as `DATABASE_PATH` in `app/database.py`. If the path ever changes, these will silently check/open the wrong file.
**Fix:**
```python
from app.database import DATABASE_PATH

db_exists = os.path.exists(DATABASE_PATH)
if db_exists:
    with sqlite3.connect(DATABASE_PATH) as conn:
        ...
```

### IN-03: `scraped_at` and `created_at` on `Job` are both `server_default=func.now()` with no distinction

**File:** `app/models.py:45-46`
**Issue:** Both `scraped_at` and `created_at` use the same `server_default` and have no `onupdate` hook. The two columns are currently identical in behavior. If the intent is to distinguish when a job was first scraped from a generic record-creation timestamp, the columns should be documented or one should be removed to avoid confusion in later phases.
**Fix:** Add a comment clarifying intent, or remove `created_at` if it serves no separate purpose from `scraped_at`:
```python
scraped_at = Column(DateTime, server_default=func.now(), nullable=False)  # when job was scraped
# created_at intentionally mirrors scraped_at in Phase 1; update onupdate in Phase 2 if needed
```

---

_Reviewed: 2026-04-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
