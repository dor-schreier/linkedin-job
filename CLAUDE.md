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
LLM_PROVIDER=ollama|groq
GROQ_API_KEY=...
GROQ_FIT_MODEL=llama-3.1-8b-instant
GROQ_RECOMMEND_MODEL=llama-3.3-70b-versatile
OLLAMA_MODEL=qwen2.5:14b
```

**Schema migrations** are in `app/database.py` — `ALTER TABLE` wrapped in try/except for idempotency. Add new columns there, not as separate migration files.

**Comeet search backend config** (`.env`):
```
GOOGLE_SEARCH_BACKEND=cse    # default; options: cse | ddgs | google | playwright
GOOGLE_CSE_KEY=              # Google Cloud API key with Custom Search API enabled
GOOGLE_CSE_CX=               # Programmable Search Engine ID
```
- Create a Programmable Search Engine at https://programmablesearchengine.google.com — restrict it to `comeet.com/*` for cleaner results.
- Enable the "Custom Search API" in the associated GCP project and generate an API key restricted to that API.
- Free quota: 100 queries/day; paid tier $5/1k beyond. Set a GCP budget alert.
- Fallback chain (automatic): CSE → DdgsBackend → GoogleScrapeBackend → PlaywrightGoogleBackend. If CSE is unconfigured, falls through to `ddgs` cleanly.
