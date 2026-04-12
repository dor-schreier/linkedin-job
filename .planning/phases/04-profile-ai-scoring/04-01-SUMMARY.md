---
phase: 04-profile-ai-scoring
plan: 01
subsystem: backend
tags: [groq, ai-scoring, schema-migration, repository, sqlite]
dependency_graph:
  requires: []
  provides: [groq_service, profile_ai_recommendations_column, job_score_repository_methods]
  affects: [app/models.py, app/database.py, app/repository.py]
tech_stack:
  added: [groq==1.1.1]
  patterns: [sync-groq-client, idempotent-alter-table, json-fence-stripping, safe-fallback-on-parse-error]
key_files:
  created:
    - app/services/__init__.py
    - app/services/groq_service.py
    - tests/test_repository_phase4.py
    - tests/test_groq_service.py
  modified:
    - app/models.py
    - app/database.py
    - app/repository.py
decisions:
  - "Sync Groq client used to match existing sync SQLAlchemy + JobSpy pattern"
  - "ALTER TABLE migration wrapped in try/except for idempotence (SQLite has no IF NOT EXISTS for ADD COLUMN)"
  - "Description truncated to 1500 chars in prompt to limit accidental PII leakage from scraped HTML (T-04-01)"
  - "salary_estimated=None in update_job_scores leaves existing value untouched — caller controls overwrite"
metrics:
  duration: ~15 minutes
  completed: 2026-04-12
  tasks_completed: 2
  files_modified: 7
---

# Phase 4 Plan 01: Schema Migration + Groq Service Backend Summary

**One-liner:** SQLite profile schema migration with idempotent ALTER TABLE, Groq sync client wrappers for per-job fit scoring (llama-3.1-8b-instant) and profile recommendations (llama-3.3-70b-versatile), plus repository score persistence methods.

## What Was Built

### Task 1: Schema migration + repository extensions
- `app/models.py` — Added `ai_recommendations = Column(Text, nullable=True)` to `Profile` class after `years_experience`
- `app/database.py` — `init_db()` now executes `ALTER TABLE profile ADD COLUMN ai_recommendations TEXT` in a try/except block for idempotent startup migration
- `app/repository.py` — Added `update_job_scores(job_id, fit_score, fit_summary, salary_estimated=None)` and `get_job(job_id)` to `JobRepository`; `salary_estimated=None` sentinel preserves existing value

### Task 2: groq_service module
- `app/services/__init__.py` — Package marker
- `app/services/groq_service.py` — Full Groq wrapper module (130 lines):
  - `get_fit_score_and_salary(job, profile)` — calls `llama-3.1-8b-instant`, bundles salary estimation, never raises
  - `get_profile_recommendations(profile)` — calls `llama-3.3-70b-versatile`, returns 3-5 bullet strings, never raises
  - `_parse_json_response()` — strips markdown code fences, coerces field types, returns `FIT_SAFE_FALLBACK` on any parse failure
  - `_parse_recommendations_response()` — returns `[]` on failure
  - `_format_listed_salary()` — formats `salary_min`/`salary_max` into prompt-friendly string

## Schema Migration Approach

Raw ALTER TABLE in `init_db()` wrapped in `try/except Exception: pass`. SQLite does not support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` syntax, so the try/except is the standard idempotent approach. The column is hard-coded literal SQL (no user input concatenated) per threat T-04-05.

## Groq Service Module Surface

| Function | Model | Returns | Error behavior |
|----------|-------|---------|----------------|
| `get_fit_score_and_salary(job, profile)` | `llama-3.1-8b-instant` | `{"fit_score": int\|None, "fit_summary": str, "salary_estimated": str\|None}` | Returns `FIT_SAFE_FALLBACK`, logs error |
| `get_profile_recommendations(profile)` | `llama-3.3-70b-versatile` | `list[str]` (3-5 bullets) | Returns `[]`, logs error |

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/test_repository_phase4.py | 7 | PASS |
| tests/test_groq_service.py | 11 | PASS |
| Full suite | 30 | PASS |

Total Phase 4 backend test count: 18 (meets >= 18 requirement).

Tests pass with `GROQ_API_KEY=` (empty) — no real API calls in test suite (Groq client fully mocked via monkeypatch on `_get_client`).

## Commits

- `35fc126` — feat(04-01): add ai_recommendations column, migration, and repository score methods
- `10cde1b` — feat(04-01): add groq_service module with fit scoring and profile recommendations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] groq package not installed in active Python environment**
- **Found during:** Task 2 GREEN phase — `ModuleNotFoundError: No module named 'groq'`
- **Fix:** Ran `pip install groq -q`; package installed successfully
- **Impact:** No code changes, tests passed after install

No other deviations — plan executed as written.

## Threat Surface Scan

No new trust boundaries beyond those documented in the plan's `<threat_model>`. All mitigations applied:
- T-04-01: Description truncated to 1500 chars in prompt
- T-04-02: API key via `os.environ.get()`, never logged
- T-04-03: LLM output parsed through typed coercion with safe fallback
- T-04-05: ALTER TABLE uses hard-coded literal SQL

## Self-Check: PASSED

- `app/services/groq_service.py` — FOUND
- `app/services/__init__.py` — FOUND
- `tests/test_repository_phase4.py` — FOUND
- `tests/test_groq_service.py` — FOUND
- Commit `35fc126` — FOUND
- Commit `10cde1b` — FOUND
