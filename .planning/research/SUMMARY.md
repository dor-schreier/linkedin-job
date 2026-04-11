# Project Research Summary

**Project:** Job Finder
**Domain:** Personal job aggregator / AI-ranked job tracker web app
**Researched:** 2026-04-11
**Confidence:** HIGH

## Executive Summary

Job Finder is a single-user, locally-run Python web app that aggregates job postings from LinkedIn, Indeed, Glassdoor, and ZipRecruiter via JobSpy, deduplicates them across sources, and uses Groq AI to score each job's fit against the user's profile. The research is clear on how to build this: FastAPI + Jinja2/HTMX for the server-rendered UI, SQLite + SQLAlchemy for persistence, APScheduler for in-process background scraping, and the Groq SDK for AI — all running in a single process with no external services. This is a well-scoped POC; the stack is proven for this exact combination of sync scraping and async web serving.

The recommended approach is a five-phase build ordered by dependency: database schema first, then the scrape-dedup-store pipeline, then a minimal browser UI, then AI scoring, and finally watch rules and notifications. This order ensures every phase delivers a working vertical slice and avoids building display logic before data is confirmed to flow correctly.

The three material risks are: (1) SQLite locking when the scraper runs concurrently with web requests — solved by enabling WAL mode at DB init; (2) Groq free-tier daily request limits (1,000 RPD for llama-3.3-70b) exhausted by bulk scoring — solved by on-demand or batched scoring rather than auto-scoring all results; (3) JobSpy field schema drift on upgrades silently breaking data ingestion — solved by pinning the jobspy version and using `.get()`/`fillna()` guards on all DataFrame access.

---

## Key Findings

### Recommended Stack

The stack is all-Python with no separate frontend build toolchain. FastAPI provides ASGI async handling, built-in Pydantic validation, and Jinja2 template support; HTMX (CDN) delivers dynamic partial updates without React/Vite. SQLAlchemy 2.0 with sync SQLite is the right ORM layer — async SQLAlchemy would add complexity for no gain since JobSpy itself is synchronous. APScheduler 3.x (not the pre-stable 4.x rewrite) runs scheduled scrapes inside the FastAPI lifespan, eliminating any need for Celery or Redis.

**Core technologies:**
- FastAPI `>=0.115` + Uvicorn: ASGI web framework — async-native, auto Swagger docs, background tasks via lifespan
- Jinja2 `>=3.1` + HTMX 2.x (CDN): Server-side rendering — zero JS build toolchain
- SQLAlchemy `2.0.x` + SQLite: Persistence — zero-config DB, ORM migrations via Alembic if needed
- JobSpy `>=1.1.79`: Multi-site scraper — returns pandas DataFrames, actively maintained
- Groq SDK `1.1.1`: AI inference — use sync client to match JobSpy's sync execution model
- APScheduler `3.11.2`: In-process job scheduling — interval/cron triggers, `AsyncIOScheduler` in lifespan
- pandas `>=2.2`: Required by JobSpy — convert DataFrames to dicts immediately, never persist DataFrames
- python-dotenv `>=1.0`: Secrets management — `GROQ_API_KEY` out of source code

**Do not use:** Flask (WSGI), Streamlit (stateful scraping breaks it), Django (excessive overhead), React/Vue (separate build toolchain), Celery+Redis (overkill for single-process app), SQLAlchemy asyncio mode (conflicts with sync JobSpy).

### Expected Features

**Must have (table stakes):**
- Keyword + location search with job type, remote, and experience-level filters
- Job results list (title, company, location, salary, source, date) and job detail view
- Deduplication across sources — SHA-256 hash of `(title, company, location)` normalized; `INSERT OR IGNORE` via UNIQUE constraint
- Application status tracking (New / Saved / Applied / Interviewing / Offer / Rejected) and notes per job
- Source site indicator (LinkedIn / Indeed / Glassdoor / ZipRecruiter)
- AI fit score (0–100 integer with label buckets: Poor / Fair / Good / Excellent) displayed in list view
- AI job summary (3–5 sentences: role focus, key requirements, fit reasoning)
- User profile input (skills + experience text, LinkedIn URL as reference)
- Watch rules (company / role keyword / sector) with in-app notification badge for matches
- Post-scrape filters: status, fit score range, source, watched flag

**Should have (differentiators):**
- AI profile improvement suggestions (Groq analyzes profile, returns actionable gaps)
- Fit score gap analysis (which skills the job requires that the profile lacks)
- Salary range display and filter
- Scrape history / last-scraped timestamp per search config
- Watch rule match explanation (which rule matched and why)
- Sort by fit score (default descending — show best matches first)
- Search config persistence (save multiple named search sets)

**Defer to v2+:**
- Email / push notifications (adds SMTP/push infra for no POC value)
- Auto-apply / one-click apply (separate product, CAPTCHA complexity)
- Resume file upload / parsing (distinct 2–4 week sub-project)
- Visual kanban pipeline board (status dropdown achieves same outcome for POC)
- Multi-user / auth (3x complexity multiplier, explicitly out of scope)
- Proxy rotation for LinkedIn (accepted 250-job cap)

**Critical path for MVP:** Search Config → Scrape → Deduplication → User Profile → AI Fit Score → Job Results List with status tracking.

**Note on Groq prompt efficiency:** AI fit score and AI job summary should be generated in a single prompt call per job (same inputs: job description + user profile). Parse `{score, label, summary, missing_skills}` from one JSON response to halve API call volume.

### Architecture Approach

The app is a single-process FastAPI server with seven distinct components: Scraper (JobSpy wrapper, returns `list[dict]`), Deduplication/Normalizer (computes `job_hash`, filters existing records), Storage/Repository (all SQLite reads/writes via a single `repository.py`), AI Processor (Groq calls for per-job scoring and profile analysis, runs as a background task), Watch Rule Engine (evaluates rules against new job IDs post-scrape, writes notification records), Web API (FastAPI routes that orchestrate the above; never calls Groq in the request path), and Frontend (Jinja2-rendered HTML + HTMX partial updates, three views: jobs browser, profile editor, watch rules manager). Data flows one-way through the pipeline: Scraper → Dedup → Storage, then AI Processor and Watch Rule Engine run in parallel against newly saved jobs, and the Web API reads Storage to serve the frontend. The only shared resource across components is the SQLite file accessed via the Repository — all other components are stateless.

**Major components:**
1. `app/core/scraper.py` — JobSpy wrapper, converts DataFrame to `list[dict]`
2. `app/core/dedup.py` — SHA-256 hash computation, filters already-seen jobs
3. `app/db/repository.py` — single file owning all SQL; no other file touches the `.db`
4. `app/core/ai_processor.py` — Groq fit scoring + profile analysis, background task only
5. `app/core/watch_engine.py` — rule evaluation against new job IDs, writes notifications
6. `app/api/` — FastAPI route handlers, Pydantic request/response validation
7. `app/static/` — Jinja2 templates + HTMX, no build step

### Critical Pitfalls

1. **SQLite "database is locked" under concurrent scrape + web server** — Enable `PRAGMA journal_mode=WAL` and `busy_timeout=3000` in DB init (not in scraper code). Use per-request connections; never share a connection object across threads.

2. **Groq free-tier RPD exhaustion during bulk scoring** — llama-3.3-70b is capped at 1,000 req/day. 250 jobs per scrape = 250 requests. Use on-demand scoring ("Score now" button) or batch multiple jobs per prompt rather than auto-scoring all results. Alternatively switch to llama-3.1-8b-instant (14,400 RPD) if quality is acceptable.

3. **JobSpy field schema drift on upgrades** — Pin `python-jobspy` to a specific version in `requirements.txt`. Wrap all DataFrame column accesses with `.get()` / `fillna()` guards so missing fields degrade gracefully instead of crashing.

4. **Groq API key exposed in code or logs** — Load from `os.environ["GROQ_API_KEY"]` only. Add `.env` to `.gitignore` before the first commit. Never hardcode or log the key.

5. **Scrape blocking the web server** — Never run JobSpy synchronously in a request handler. Trigger scrape as a FastAPI `BackgroundTask` or APScheduler job; return immediately from the endpoint and poll a `scrape_status` record for progress.

---

## Implications for Roadmap

Based on combined research, the architecture's own suggested build order is well-justified by component dependencies and should be followed directly:

### Phase 1: Storage Foundation
**Rationale:** Every other component depends on the DB schema and Repository. Nothing is testable end-to-end without it.
**Delivers:** SQLite DB with full schema (jobs, profile, search_configs, watch_rules, notifications), `repository.py` with typed read/write methods, WAL mode + busy_timeout configured at init.
**Addresses:** Deduplication (UNIQUE constraint on job_hash), application status and notes columns, AI score/summary columns (nullable until populated).
**Avoids:** SQLite locking pitfall (WAL mode set here, not later), API key exposure (`.env` + `.gitignore` set up in this phase).

### Phase 2: Scraper + Dedup Pipeline
**Rationale:** Validate data quality and dedup correctness before building any display logic. Catch JobSpy field issues and LinkedIn 429s at the CLI level.
**Delivers:** Working `scraper.py` (JobSpy → `list[dict]`) and `dedup.py` (hash + INSERT OR IGNORE); validated with a CLI script or pytest — no UI yet.
**Addresses:** Keyword/location search, job type/remote filters, multi-source aggregation, source indicator, deduplication across sites, last-scraped timestamp.
**Avoids:** Building UI before data flows correctly; JobSpy field drift (`.get()`/`fillna()` guards added here); LinkedIn 0-result silent failures (test with Indeed first).

### Phase 3: Web API + Minimal Frontend
**Rationale:** First working browser app. Exposes scrape trigger and job listing; establishes the FastAPI/Jinja2/HTMX scaffold all later phases build on.
**Delivers:** FastAPI app with routes for jobs list, job detail, scrape trigger (background task), search config CRUD; bare-bones Jinja2 UI with job table, filters, status dropdown, notes field.
**Addresses:** Job results list, job detail view, application status tracking, notes per job, post-scrape filters, search config persistence, salary display.
**Avoids:** Scrape blocking the web server (BackgroundTask pattern established here); full-page reloads on filter (HTMX partial updates).

### Phase 4: Profile + AI Scoring
**Rationale:** AI requires a profile to score against; scoring runs as a background task after jobs exist. Don't wire AI until data is confirmed to flow correctly.
**Delivers:** Profile editor UI + storage; Groq per-job fit scoring (score + label + summary + missing_skills in one prompt call); AI profile improvement suggestions; sort-by-score and score-range filter in job list.
**Addresses:** User profile input, AI fit score, AI job summary, fit score gap analysis, AI profile suggestions, sort by fit score.
**Avoids:** Groq RPD exhaustion (on-demand scoring or explicit "Score now" action, not auto-score-all); prompt returning inconsistent score format (strict JSON schema + Pydantic validation on response); token blowup on long JDs (truncate to 800–1,200 tokens).

### Phase 5: Watch Rules + Notifications
**Rationale:** No new external dependencies; builds entirely on existing Storage and Web API. Highest value-add once the core loop works.
**Delivers:** Watch rules CRUD UI; `watch_engine.py` evaluating rules against new job IDs after each scrape; notification records in DB; bell icon + unread count badge in nav; rule-match explanation on flagged jobs; rule-preview endpoint (match count before saving).
**Addresses:** Watch rules (company/role/sector), in-app notification badge, watch rule match explanation.
**Avoids:** Watch rules too strict (0 matches) or too loose (500+ matches) — rule-preview endpoint mitigates both; scope creep into email/push notifications (explicitly deferred).

### Phase Ordering Rationale

- Storage before everything: schema is the contract all other components depend on; WAL mode must be set before any concurrent code exists.
- Scraper before UI: JobSpy field drift and LinkedIn bot detection failures are caught at the data layer, not in the browser.
- UI before AI: AI calls are slow and rate-limited; confirming data display works before layering scoring prevents debugging two systems at once.
- Watch rules last: zero new external dependencies, clear requirements, and naturally slots after AI scores exist (watch rules can filter on `min_score`).

### Research Flags

Phases with well-documented patterns (skip deep research during planning):
- **Phase 1 (Storage):** SQLAlchemy 2.0 + SQLite schema patterns are fully established; WAL mode setup is a one-liner.
- **Phase 3 (Web API + Frontend):** FastAPI + Jinja2 + HTMX integration is well-documented with official examples.
- **Phase 5 (Watch Rules):** Pure Python substring matching with no external dependencies; straightforward to implement.

Phases that may benefit from targeted research during planning:
- **Phase 2 (Scraper):** JobSpy's current LinkedIn behavior (bot detection, field availability) changes with site DOM updates — check the JobSpy releases changelog before implementation.
- **Phase 4 (AI Scoring):** Groq model availability and rate limits change periodically — verify current free-tier RPD for llama-3.3-70b and llama-3.1-8b-instant at https://console.groq.com/docs/rate-limits before implementation.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified against PyPI latest versions; integration patterns confirmed from official docs and working open-source examples |
| Features | HIGH | Cross-referenced against 6+ competing job tracker products (Teal, JobQuest, OwlApply, Resumly, ApplyArc); feature set matches industry patterns exactly |
| Architecture | HIGH | Component boundaries and data flow derived from JobSpy ecosystem references and FastAPI background task patterns; schema is concrete and complete |
| Pitfalls | HIGH | Verified against JobSpy GitHub issues tracker, Groq official rate limit docs, SQLite concurrency literature; all pitfalls are documented recurring problems, not hypotheticals |

**Overall confidence:** HIGH

### Gaps to Address

- **Groq model availability:** Groq deprecates and adds models periodically. The recommendation (`llama-3.3-70b-versatile` for quality, `llama-3.1-8b-instant` as fallback) should be re-verified at `console.groq.com/docs/models` before Phase 4 implementation.
- **JobSpy LinkedIn scraper stability:** LinkedIn selector breakage has occurred 3+ times in 2025. Before Phase 2, check the JobSpy releases page for any recent breaking changes or open issues related to LinkedIn 0-result returns.
- **Dedup accuracy at scale:** The composite-key approach catches ~90% of cross-site duplicates. If the user finds duplicate noise unacceptable after Phase 2, a rapidfuzz token_sort_ratio second pass (threshold 85) is the documented next step — but do not pre-build it.

---

## Sources

### Primary (HIGH confidence)
- https://github.com/speedyapply/JobSpy — JobSpy capabilities, field schema, LinkedIn cap
- https://console.groq.com/docs/rate-limits — Groq free-tier RPD/RPM limits
- https://www.sqlalchemy.org/ — SQLAlchemy 2.0 sync patterns
- https://fastapi.tiangolo.com/tutorial/background-tasks/ — FastAPI background task pattern
- https://pypi.org/project/APScheduler/ — APScheduler 3.11.2 stable release
- https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/ — SQLite WAL mode + busy_timeout

### Secondary (MEDIUM confidence)
- https://testdriven.io/blog/fastapi-htmx/ — FastAPI + HTMX + Jinja2 integration
- https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186 — APScheduler lifespan pattern
- https://github.com/BjornMelin/ai-job-scraper — SQLite FTS5 + pipeline architecture reference
- https://jobquest.ai/blog/whats-a-job-match-score-and-why-it-matters/ — AI fit score 0–100 design pattern
- https://www.textkernel.com/learn-support/blog/online-job-postings-have-many-duplicates-but-how-can-you-detect-them-if-they-are-not-exact-copies-of-each-other/ — dedup accuracy research

### Tertiary (informational)
- https://applyarc.com/blog/best-free-job-tracker-apps-2026 — competitive feature landscape
- https://www.tealhq.com/tools/job-tracker — Teal feature reference
- https://gologin.com/blog/scraping-data-from-linkedin/ — LinkedIn bot detection patterns

---
*Research completed: 2026-04-11*
*Ready for roadmap: yes*
