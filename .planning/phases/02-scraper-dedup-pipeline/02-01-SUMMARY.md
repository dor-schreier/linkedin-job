---
phase: 02-scraper-dedup-pipeline
plan: 01
subsystem: scraper
tags: [scraper, jobspy, deduplication, normalization, sha256, cli]
dependency_graph:
  requires: [app/database.py, app/repository.py, app/models.py]
  provides: [app/scraper.py, scripts/run_scrape.py, tests/test_scraper.py]
  affects: []
tech_stack:
  added: [jobspy]
  patterns: [sha256-dedup, dataframe-normalization, defensive-get-access]
key_files:
  created:
    - app/scraper.py
    - scripts/run_scrape.py
    - tests/test_scraper.py
decisions:
  - "import math inside _normalize_row to avoid top-level import order issue"
  - "SessionLocal used as context manager — consistent with how Phase 1 defined it"
metrics:
  duration: ~15 minutes
  completed: 2026-04-12
  tasks_completed: 2
  files_created: 3
---

# Phase 2 Plan 01: Scraper Service Summary

**One-liner:** SHA-256 dedup scraper pipeline using JobSpy with remote-job filter, NaN coercion, and defensive .get() DataFrame access throughout.

## What Was Built

- `app/scraper.py` — Core scraper service with three public-facing symbols:
  - `_compute_hash(title, company, location)`: deterministic SHA-256 hex of `title|company|location` (lowercased, stripped)
  - `_normalize_row(row)`: safely extracts fields from a JobSpy DataFrame row dict using `.get()`, coerces NaN strings to `""`, NaN numerics to `None`, filters remote jobs and empty titles
  - `run_scrape(keywords, location, ...)`: calls JobSpy across linkedin/indeed/glassdoor, creates its own `SessionLocal()`, deduplicates via hash lookup, persists new jobs, returns summary dict

- `tests/test_scraper.py` — 12 unit tests covering hash determinism, case/whitespace normalization, NaN field coercion, remote filtering, empty title filtering, and missing-field safety

- `scripts/run_scrape.py` — Standalone CLI validation script: initializes the DB and calls `run_scrape()` with optional keyword/location args

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create scraper service module (TDD) | a255719 | app/scraper.py, tests/test_scraper.py |
| 2 | Create CLI validation script | 797f120 | scripts/run_scrape.py |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Coverage

All mitigate-disposition threats addressed:

- **T-02-01 (Injection):** All DataFrame values go through `_str()` helper (str coercion + strip) before DB insert. SQLAlchemy parameterized queries prevent SQL injection downstream.
- **T-02-03 (DoS):** `RESULTS_WANTED = 50` constant caps scrape volume per call.

## Known Stubs

None — no placeholder values or hardcoded empty results flowing to UI.

## Self-Check: PASSED

- `app/scraper.py` — EXISTS
- `scripts/run_scrape.py` — EXISTS
- `tests/test_scraper.py` — EXISTS
- Commit a255719 — EXISTS
- Commit 797f120 — EXISTS
- All 12 tests pass
- `grep -c "row.get" app/scraper.py` returns 11 (> 5 required)
- `grep "is_remote" app/scraper.py` confirms remote filtering present
