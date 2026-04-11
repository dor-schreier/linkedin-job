# Phase 2: Scraper + Dedup Pipeline - Research

**Researched:** 2026-04-11
**Domain:** JobSpy scraping, pandas DataFrame normalization, SHA-256 deduplication, FastAPI BackgroundTasks
**Confidence:** HIGH

---

## Summary

Phase 2 wires together four distinct concerns: calling JobSpy's `scrape_jobs()` function, normalizing the returned pandas DataFrame into ORM-ready dicts, hashing each job for deduplication, and persisting into the SQLite schema Phase 1 established. A fifth concern — not blocking the HTTP request — is handled by FastAPI's `BackgroundTasks` mechanism, which runs the sync scraper in a threadpool after the response has already been returned to the browser.

The schema is already fully designed in Phase 1 (`job_hash` SHA-256 column exists with a UNIQUE constraint, `JobRepository.add_job()` and `get_job_by_hash()` are implemented). Phase 2 must not modify these; it must work within the existing contract. The dedup strategy is straightforward: hash `title + company + location`, check existence via `get_job_by_hash()`, skip if found. No SQLite `INSERT OR IGNORE` is needed because the repository layer already handles sessions explicitly — just skip the insert when the hash is found.

Search configuration persistence (SRCH-05) requires saving to `search_configs` table (also already modeled) and reading back the latest active config to pre-fill the scrape parameters.

**Primary recommendation:** Add a `scraper.py` service module under `app/` that owns the JobSpy call and normalization. Wire it into a new `app/routes/scrape.py` that accepts a POST, enqueues a `BackgroundTask`, and returns immediately. A separate `/scrape/status` endpoint (backed by a simple in-memory dict or the jobs table count) provides progress feedback for HTMX polling.

---

## Project Constraints (from CLAUDE.md)

- Use sync SQLAlchemy (not asyncio variant) — JobSpy is sync; mixing async DB adds complexity.
- Use `BackgroundTasks` — scrape runs must never block the request path.
- Use `groq` SDK only — no OpenAI (Groq scoring is Phase 4, not this phase).
- Use JobSpy pinned to `>=1.1.79`; all DataFrame access uses `.get()` / `fillna()` guards.
- No auth, no multi-tenancy, personal POC scope.
- Fully remote jobs are OUT OF SCOPE — filter `is_remote=True` jobs out before storing.
- Part-time / contract / internship are OUT OF SCOPE — set `job_type="fulltime"` in JobSpy call.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

No Phase 2 CONTEXT.md exists — no prior discussion was held. All decisions are Claude's discretion
guided by CLAUDE.md, ROADMAP.md decisions, and Phase 1 established patterns.

### Locked Decisions (from ROADMAP.md / STATE.md accumulated context)
- Scrape runs as FastAPI BackgroundTask — never blocks the request path.
- JobSpy pinned to specific version; all DataFrame access uses `.get()`/`fillna()` guards.
- Groq scoring is on-demand only — never auto-score all results (Phase 4 concern, out of scope here).
- WAL mode + busy_timeout already set in Phase 1 DB init — do not re-configure.

### Claude's Discretion
- How to surface scrape progress to the browser (HTMX polling vs SSE vs WebSocket).
- Whether to use a global in-memory state dict or DB query for progress tracking.
- How to structure the `scraper.py` module internally.
- Which JobSpy parameters map to which SearchConfig fields.
- Whether to scrape all three sites concurrently (JobSpy does this by default) or sequentially.
- CLI validation approach (a `scripts/` entry point or pytest fixture).

### Deferred Ideas (OUT OF SCOPE for Phase 2)
- Automated scheduled scraping (APScheduler) — V2 requirement.
- Proxy rotation — V2 requirement.
- AI scoring — Phase 4.
- Watch rule matching — Phase 5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-01 | User can define search keywords | JobSpy `search_term` param; save to `search_configs.keywords` |
| SRCH-02 | User can define target location | JobSpy `location` + `country_indeed` params; save to `search_configs.location` |
| SRCH-03 | User can filter by experience level | JobSpy does not have a direct `experience_level` param — must filter post-scrape OR use `search_term` embedding; save to `search_configs.experience_level` |
| SRCH-04 | User can filter by work mode (onsite/hybrid, exclude fully remote) | Post-scrape filter on `jobs_df['is_remote'] == True` rows — drop them; save to `search_configs.work_mode` |
| SRCH-05 | User can save search configuration and reuse it | `SearchConfig` model + `JobRepository.add_search_config()` + `list_search_configs()` already implemented in Phase 1 |
| SRCH-06 | User can trigger a manual scrape run from the UI | POST endpoint at `/scrape/run` that enqueues a `BackgroundTask`; returns 202 immediately |
| SCRP-01 | App scrapes from LinkedIn, Indeed, Glassdoor via JobSpy | `site_name=["linkedin", "indeed", "glassdoor"]` in `scrape_jobs()` call |
| SCRP-02 | Jobs deduplicated across sources (hash on title+company+location) | SHA-256 of `f"{title}|{company}|{location}".lower().strip()` → `job_hash`; skip insert if hash found |
</phase_requirements>

---

## Standard Stack

### Core (all already in requirements.txt)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| jobspy (speedyapply) | `>=1.1.79` [VERIFIED: requirements.txt] | Multi-site job scraping | Project requirement; returns pandas DataFrame |
| pandas | `>=2.2` [VERIFIED: requirements.txt] | DataFrame normalization | Required by JobSpy; use for column extraction and filtering |
| hashlib | stdlib | SHA-256 job hashing | No install needed; deterministic dedup key |
| FastAPI BackgroundTasks | ships with fastapi [VERIFIED: requirements.txt] | Non-blocking scrape trigger | Runs sync tasks in threadpool after response sent |
| SQLAlchemy (sync) | `>=2.0,<3.0` [VERIFIED: requirements.txt] | Persist normalized jobs | Phase 1 established pattern |

### No New Dependencies Needed
Phase 2 requires zero new `pip install` entries. All necessary libraries are already in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure Addition
```
app/
├── scraper.py          # NEW: JobSpy call + DataFrame normalization + dedup logic
├── routes/
│   ├── health.py       # existing
│   └── scrape.py       # NEW: POST /scrape/run, GET /scrape/status
├── templates/
│   └── scrape.html     # NEW: minimal trigger form + HTMX status polling
├── main.py             # add scrape router
├── database.py         # unchanged
├── models.py           # unchanged
└── repository.py       # add upsert_search_config if needed; otherwise unchanged
scripts/
└── run_scrape.py       # NEW: CLI validation entrypoint (calls scraper directly)
```

### Pattern 1: Scraper Service Module

**What:** A standalone `app/scraper.py` module with a single public function `run_scrape(search_config)` that calls JobSpy, normalizes the DataFrame, hashes, deduplicates, and returns a summary dict `{scraped: N, inserted: N, skipped: N}`.

**When to use:** Called by both the BackgroundTask route handler and the CLI validation script.

**Example:**
```python
# Source: [VERIFIED: JobSpy GitHub README + existing Phase 1 repository.py patterns]
import hashlib
from jobspy import scrape_jobs
from app.database import SessionLocal
from app.repository import JobRepository

def _compute_hash(title: str, company: str, location: str) -> str:
    raw = f"{title}|{company}|{location}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()

def run_scrape(keywords: str, location: str, country_indeed: str = "USA") -> dict:
    df = scrape_jobs(
        site_name=["linkedin", "indeed", "glassdoor"],
        search_term=keywords,
        location=location,
        country_indeed=country_indeed,
        job_type="fulltime",   # exclude part-time/contract/internship
        results_wanted=50,
        verbose=0,
        linkedin_fetch_description=True,
    )
    inserted, skipped = 0, 0
    with SessionLocal() as session:
        repo = JobRepository(session)
        for _, row in df.iterrows():
            title    = str(row.get("title") or "").strip()
            company  = str(row.get("company") or "").strip()
            location_val = str(row.get("location") or "").strip()

            # SRCH-04: exclude fully remote
            if row.get("is_remote") is True:
                skipped += 1
                continue

            job_hash = _compute_hash(title, company, location_val)
            if repo.get_job_by_hash(job_hash):
                skipped += 1
                continue

            repo.add_job(
                title=title,
                company=company,
                location=location_val,
                description=str(row.get("description") or ""),
                source=str(row.get("site") or ""),
                apply_url=str(row.get("job_url") or ""),
                salary_min=row.get("min_amount") if row.get("min_amount") else None,
                salary_max=row.get("max_amount") if row.get("max_amount") else None,
                salary_currency=str(row.get("currency") or "") or None,
                job_hash=job_hash,
            )
            inserted += 1
    return {"inserted": inserted, "skipped": skipped}
```

### Pattern 2: Non-Blocking Scrape Trigger (SRCH-06)

**What:** FastAPI `BackgroundTasks` enqueues `run_scrape()` after the response is sent. A simple module-level dict tracks status for HTMX polling.

**When to use:** Browser-initiated scrape (SRCH-06 / success criterion 5).

**Example:**
```python
# Source: [CITED: https://fastapi.tiangolo.com/tutorial/background-tasks/]
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/scrape")

_status: dict = {"running": False, "last_result": None}

def _scrape_task(keywords: str, location: str):
    _status["running"] = True
    try:
        result = run_scrape(keywords, location)
        _status["last_result"] = result
    finally:
        _status["running"] = False

@router.post("/run", status_code=202)
def trigger_scrape(background_tasks: BackgroundTasks, keywords: str, location: str):
    if not _status["running"]:
        background_tasks.add_task(_scrape_task, keywords, location)
    return JSONResponse({"queued": True})

@router.get("/status")
def scrape_status():
    return _status
```

**HTMX polling pattern:**
```html
<!-- templates/scrape.html — polls every 2 seconds while running -->
<div id="scrape-status"
     hx-get="/scrape/status"
     hx-trigger="every 2s [document.querySelector('#running').value === 'true']"
     hx-swap="outerHTML">
  ...
</div>
```

### Pattern 3: Search Config Persistence (SRCH-05)

**What:** On form submit, save keywords/location/experience_level/work_mode to `search_configs` table. On page load, read latest active config and pre-fill the form.

**When to use:** Every scrape trigger; every page load of the search config form.

**Implementation note:** `JobRepository.add_search_config()` and `list_search_configs()` already exist in `repository.py`. Phase 2 just calls them. Consider adding `get_latest_search_config()` to the repository if pre-fill is needed (returns `list_search_configs()[0]` or `None`).

### Anti-Patterns to Avoid

- **Awaiting `run_scrape()` inside an async route:** JobSpy is sync and will block the event loop. Always use `BackgroundTasks` or `run_in_executor`, never `await scrape_jobs(...)`.
- **Storing pandas DataFrames in the DB session:** Convert rows to plain dicts or ORM model kwargs immediately; never pass a DataFrame to a repository method.
- **Calling `session.commit()` in a loop per job:** The current `add_job()` commits once per insert — acceptable for personal-use volumes (<250 jobs/scrape). Do not batch-commit in a way that bypasses the existing repository interface.
- **Ignoring DataFrame column absence:** JobSpy columns vary by site and version. Always use `row.get("column_name")` not `row["column_name"]` — a KeyError will silently crash the background task.
- **Using `easy_apply=True` for LinkedIn:** This filter is broken in JobSpy as of 2026 — it returns 0 results. Do not include it. [VERIFIED: GitHub Issues search]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-site concurrent scraping | Custom HTTP scrapers per site | `jobspy.scrape_jobs()` | JobSpy handles concurrency, rate-limit headers, UA rotation, and DataFrame output |
| SHA-256 hashing | Custom fingerprinting scheme | `hashlib.sha256()` stdlib | Deterministic, collision-resistant, already planned in model (`job_hash` column) |
| DataFrame-to-dict normalization | Complex pandas transformation pipelines | Simple `row.get()` per column in a for-loop | JobSpy DataFrame is already flat; no complex transform needed |
| Background task execution | Custom threading / subprocess | FastAPI `BackgroundTasks` | Framework-native; runs sync callable in threadpool automatically |
| Progress state tracking | Redis / Celery task state | Module-level `_status` dict | Sufficient for single-user, single-worker personal app |

**Key insight:** JobSpy is the hard part. Everything else (hashing, insert, status) is 10–20 lines of straightforward Python. Don't over-engineer it.

---

## Common Pitfalls

### Pitfall 1: LinkedIn Returns 0 Results
**What goes wrong:** `scrape_jobs()` returns an empty DataFrame for LinkedIn despite valid parameters.
**Why it happens:** LinkedIn blocks scraping aggressively. Known causes: outdated user-agent (pre-2026), `easy_apply=True` (broken), `hours_old` combined with incompatible filters, or IP rate-limit.
**How to avoid:** Do not use `easy_apply`. Do not combine `hours_old` with LinkedIn in initial implementation. Pass `verbose=1` during development to see per-site errors.
**Warning signs:** DataFrame has rows for Indeed/Glassdoor but not LinkedIn — check `df['site'].value_counts()` in logs.
**Recovery:** LinkedIn returning 0 is a known ecosystem issue — treat it as degraded-graceful: still persist Indeed + Glassdoor results. [CITED: https://github.com/speedyapply/JobSpy/issues]

### Pitfall 2: DataFrame Column Access KeyError
**What goes wrong:** `row["min_amount"]` raises `KeyError` if that column isn't present for a given site.
**Why it happens:** JobSpy returns different columns per site. Some salary columns only appear when Indeed/Glassdoor have data.
**How to avoid:** Always use `row.get("column", None)` for nullable columns. Guard numeric columns: `row.get("min_amount") or None` (avoids storing `NaN`).
**Warning signs:** Background task silently completes with 0 inserts; exception swallowed.

### Pitfall 3: BackgroundTask Session Lifecycle
**What goes wrong:** SQLAlchemy session created before the BackgroundTask runs, then used inside the task after the request context is gone — raises `DetachedInstanceError` or session already closed.
**Why it happens:** If session is created in a FastAPI dependency (e.g., `Depends(get_session)`), it closes when the route handler returns — before the background task runs.
**How to avoid:** `run_scrape()` must create its OWN `SessionLocal()` session internally. Never pass a session from a route dependency into a BackgroundTask. [ASSUMED based on FastAPI/SQLAlchemy behavior — well-known pattern]

### Pitfall 4: NaN values in string columns
**What goes wrong:** `job.title = float('nan')` gets stored; later queries fail or display "nan".
**Why it happens:** pandas fills missing string cells with `NaN` (float), not empty string.
**How to avoid:** Always `str(row.get("title") or "").strip()` — the `or ""` coerces NaN to empty string, then `str()` is safe.

### Pitfall 5: experience_level has no direct JobSpy parameter
**What goes wrong:** SRCH-03 asks for experience level filtering, but `scrape_jobs()` has no `experience_level` param.
**Why it happens:** JobSpy doesn't expose this filter for LinkedIn/Indeed at the scrape level.
**How to avoid:** Store `experience_level` in `search_configs` for UI display and future use. Optionally embed it in `search_term` (e.g., "senior software engineer"). Post-scrape filtering on description text is unreliable. [VERIFIED: JobSpy README — no experience_level parameter listed]

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All | ✓ | runtime confirmed (Phase 1 complete) | — |
| jobspy package | SCRP-01 | Unconfirmed — not importable | listed in requirements.txt | `pip install -r requirements.txt` |
| pandas | normalization | Unconfirmed | listed in requirements.txt | same |
| SQLite | storage | ✓ | stdlib, Phase 1 verified | — |
| internet access | JobSpy scraping | ✓ assumed | — | no fallback for scraping |

**Missing dependencies with no fallback:**
- `jobspy` and `pandas` must be installed (`pip install -r requirements.txt`). If not installed, scrape will fail at import time with `ModuleNotFoundError`. Plan must include a Wave 0 step verifying install.

---

## Code Examples

### JobSpy Minimum Viable Call
```python
# Source: [CITED: https://github.com/speedyapply/JobSpy/blob/main/README.md]
from jobspy import scrape_jobs

jobs_df = scrape_jobs(
    site_name=["linkedin", "indeed", "glassdoor"],
    search_term="software engineer",
    location="Tel Aviv, Israel",
    country_indeed="Israel",
    job_type="fulltime",
    results_wanted=50,
    verbose=0,
    linkedin_fetch_description=True,
)
print(jobs_df.columns.tolist())
# ['id', 'site', 'job_url', 'job_url_direct', 'title', 'company',
#  'location', 'date_posted', 'job_type', 'salary_source', 'interval',
#  'min_amount', 'max_amount', 'currency', 'is_remote', 'job_level',
#  'job_function', 'listing_type', 'emails', 'description',
#  'company_industry', 'company_url', 'company_logo', ...]
```

### Safe DataFrame Row Access
```python
# [ASSUMED pattern — standard pandas defensive coding]
for _, row in jobs_df.iterrows():
    title = str(row.get("title") or "").strip()
    company = str(row.get("company") or "").strip()
    location = str(row.get("location") or "").strip()
    is_remote = bool(row.get("is_remote")) if row.get("is_remote") is not None else False
    min_amount = row.get("min_amount")
    salary_min = float(min_amount) if min_amount and str(min_amount) != "nan" else None
```

### Session-Safe Background Task
```python
# [ASSUMED pattern — FastAPI + SQLAlchemy session lifecycle, well-known]
from app.database import SessionLocal

def _scrape_task(keywords: str, location: str):
    # Create session INSIDE the task — never pass session from route
    with SessionLocal() as session:
        repo = JobRepository(session)
        # ... scrape and insert
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JobSpy `tbliu/JobSpy` (original) | `speedyapply/JobSpy` fork | ~2024 | speedyapply is the maintained fork; always use it |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ | Phase 1 already uses lifespan correctly |
| `easy_apply` LinkedIn filter | Do not use | Broken as of 2026 [CITED: GitHub Issues] | Returns 0 results |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | BackgroundTask session must be created inside the task, not passed from route | Pitfall 3, Code Examples | Session lifecycle error at runtime — DetachedInstanceError |
| A2 | experience_level has no direct JobSpy parameter | Pitfall 5, Phase Requirements | If JobSpy adds it, could enable cleaner filtering |
| A3 | Module-level `_status` dict is sufficient for single-worker personal app | Architecture Patterns | If uvicorn is started with multiple workers, each worker has its own dict; status poll returns wrong worker's state. Fix: use single worker (already recommended in CLAUDE.md) |

---

## Open Questions (RESOLVED)

1. **country_indeed value for target location** — RESOLVED: defaults to `"USA"` as a hardcoded constant in `scraper.py`. Future enhancement: promote to a `SearchConfig` field.

2. **results_wanted per site** — RESOLVED: `RESULTS_WANTED = 50` constant in `scraper.py` (150 total max across 3 sites), adjustable by editing the constant directly.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: project codebase] `app/models.py`, `app/repository.py`, `app/database.py` — Phase 1 established schema and repository interface
- [VERIFIED: project codebase] `requirements.txt` — confirmed library versions
- [CITED: https://github.com/speedyapply/JobSpy/blob/main/README.md] — JobSpy `scrape_jobs()` API, parameter list, DataFrame columns
- [CITED: https://fastapi.tiangolo.com/tutorial/background-tasks/] — FastAPI BackgroundTasks pattern

### Secondary (MEDIUM confidence)
- [CITED: https://github.com/speedyapply/JobSpy/issues] — LinkedIn `easy_apply` broken, 0-results issues confirmed in open issues 2026
- WebSearch: FastAPI BackgroundTasks vs run_in_executor — multiple sources confirm sync tasks run in threadpool

### Tertiary (LOW confidence — see Assumptions Log)
- Session lifecycle inside BackgroundTask: well-known pattern, not verified against current FastAPI docs in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are in requirements.txt, Phase 1 codebase verified
- Architecture: HIGH — patterns derived from existing code + official FastAPI docs
- Pitfalls: MEDIUM — LinkedIn 0-results verified via GitHub Issues; session lifecycle is assumed (common pattern)
- JobSpy DataFrame columns: HIGH — verified from official README

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (JobSpy is actively maintained; LinkedIn scraping behavior can change within weeks)
