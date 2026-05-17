# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000

# Run tests
pytest tests/
pytest tests/test_scraper.py          # single test file
pytest tests/test_scraper.py::test_fn # single test

# Setup
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
playwright install
cp .env.example .env                  # then fill in API keys

# Utility scripts
python scripts/run_scrape.py "software engineer" "New York"
python scripts/import_linkedin_zip.py --zip ~/Downloads/linkedin-data.zip --output cv_output/
python backfill_enrichment.py
```

## Architecture

Self-hosted job search automation platform. FastAPI backend with Jinja2/HTMX frontend, SQLite storage, APScheduler for background scrapes, and provider-agnostic LLM integration (Groq cloud or Ollama local).

**Data flow:**
1. `app/scraper.py` — Calls JobSpy (LinkedIn/Indeed/Glassdoor), filters, deduplicates by SHA256(title+company+location), inserts into DB
2. `app/services/llm_service.py` — Scores jobs (fit_score 0–100) and extracts intelligence (skills, red_flags, company summaries) via LLM; abstracts Groq vs Ollama using OpenAI-compatible SDK
3. `app/repository.py` — All DB queries go through `JobRepository`; no raw SQL in routes
4. `app/routes/` — FastAPI routes, support both HTML (Jinja2) and JSON responses via `Accept` header
5. `app/services/scheduler.py` — APScheduler runs `run_scrape()` on interval (default 6h); uses `threading.Lock` to prevent concurrent scrapes

**Key models** (SQLite, auto-migrated in `app/database.py`):
- `Job` — core record; `status` enum (NEW/SAVED/APPLIED/INTERVIEWING/OFFER/REJECTED), `is_rejected` bool kept in sync via SQLAlchemy validators, JSON blobs for `intelligence_json` and `score_breakdown_json`
- `Company` — enriched with `sector`, `company_type`, `what_they_do`
- `Profile` — user skills/title/experience; drives LLM fit scoring
- `SearchConfig` — scrape parameters (role_level track, blocked_companies, exclude_keywords, min_salary)
- `RejectRule` / `RejectAuditLog` — auto-reject engine with full audit trail
- `WatchRule` / `Notification` — alert rules that fire when scraped jobs match criteria

**LLM provider config** (`.env`):
```
LLM_PROVIDER=ollama|groq|vertexai
GROQ_API_KEY=...
GROQ_FIT_MODEL=llama-3.1-8b-instant
GROQ_RECOMMEND_MODEL=llama-3.3-70b-versatile
OLLAMA_MODEL=qwen2.5:14b
VERTEX_LLM_FIT_MODEL=gemini-2.5-flash-lite # default; LLM_PROVIDER=vertexai only
VERTEX_LLM_RECOMMEND_MODEL=gemini-2.5-flash # default; LLM_PROVIDER=vertexai only
# Vertex AI LLM auth/project/location are shared with the Vertex AI Search section below
# (GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION, GOOGLE_APPLICATION_CREDENTIALS).
```

**Schema migrations** are in `app/database.py` — `ALTER TABLE` wrapped in try/except for idempotency. Add new columns there, not as separate migration files.

**Comeet search backend config** (`.env`):
```
GOOGLE_SEARCH_BACKEND=vertex     # default; options: vertex | vertexai | cse | ddgs | google | playwright | serpapi
GOOGLE_CLOUD_PROJECT=            # GCP project ID
VERTEX_AI_DATA_STORE_ID=         # Discovery Engine data store ID (Web App, restricted to comeet.com/*)
VERTEX_AI_ENGINE_ID=             # App/Engine ID — required if data store lacks Enterprise edition (website search needs it)
VERTEX_AI_LOCATION=global        # default; use "us" or "eu" if your data store is regional
GOOGLE_APPLICATION_CREDENTIALS=  # path to service account JSON (omit to use ADC)
GOOGLE_CSE_KEY=                  # legacy — existing CSE customers only (closed to new signups)
GOOGLE_CSE_CX=                   # legacy — Programmable Search Engine ID
```
- **Vertex AI Search setup**: create a Web App data store in GCP → Vertex AI Agent Builder, restrict it to `comeet.com/*`, grant `Discovery Engine Viewer` to your service account, then set the four `GOOGLE_*` / `VERTEX_AI_*` vars above (or use `gcloud auth application-default login` for ADC).
- **CSE is closed to new customers** (as of 2025). Existing customers may continue using it until January 1, 2027.
- Fallback chain (automatic): configured primary → GoogleScrapeBackend → PlaywrightGoogleBackend. `DdgsBackend` is still selectable via `GOOGLE_SEARCH_BACKEND=ddgs` but is no longer in the automatic fallback chain.

## Logging

Session logs are written to `logs/app-YYYYMMDD-HHMMSS.log` — one file per app start, never overwritten. Console output (stdout) receives the same lines. The `logs/` directory is gitignored.

**Log format:** `%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s`

**Logger groups** (defined in `app/logging_config.py`):
- `app.scraper`, `app.scrapers` — scraping subsystem
- `app.services.llm_service` — LLM calls
- `app.services.scheduler` — background jobs
- `app.services` — other services (cv, watch, analysis, cleanup, reject)
- `app.routes` — API/HTTP layer
- `app.repository`, `app.database` — data layer
- `uvicorn`, `uvicorn.access`, `apscheduler` — third-party (default `WARNING` to suppress noisy access logs)

**Level env vars** (`.env`):
```
LOG_LEVEL=INFO            # controls all app.* loggers; set DEBUG for verbose output
LOG_LEVEL_UVICORN=WARNING # controls uvicorn and apscheduler loggers
```
