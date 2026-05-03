# LinkedIn Job Finder

A self-hosted job search automation tool that scrapes jobs from LinkedIn, Indeed, and Glassdoor, scores them against your profile using AI, and helps you track applications — all from a local web UI.

## Features

- **Multi-source job scraping** — pulls from LinkedIn, Indeed, and Glassdoor via JobSpy
- **AI fit scoring** — rates each job 0–100 against your profile (skills, target title, seniority level) using Groq cloud or a local Ollama model
- **Scheduled scraping** — runs your saved search configs on a configurable interval (default: every 6 hours)
- **Job tracking** — move jobs through statuses: NEW → SAVED → APPLIED → INTERVIEWING → OFFER / REJECTED
- **Watch rules & notifications** — get alerted when jobs matching a company, keyword, or sector appear
- **Company enrichment** — AI-generated company summaries (sector, type, what they do)
- **Keyword gap analysis** — compares job intelligence data against your profile skills to surface missing keywords
- **Job link cleanup** — background checker that re-validates job URLs and marks inactive postings
- **CV export** — scrape your LinkedIn profile and generate a downloadable PDF/JSON CV
- **Profile optimizer** — AI recommendations for strengthening your LinkedIn profile

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy (SQLite), APScheduler
- **Frontend:** React + Vite (SPA, served as static files in production)
- **AI:** Groq API (`llama-3.1-8b-instant` / `llama-3.3-70b-versatile`) or Ollama (`qwen2.5:14b`)
- **Scraping:** JobSpy + Playwright

## Requirements

- Python 3.10+
- For local inference: [Ollama](https://ollama.com) with `qwen2.5:14b` pulled
- For cloud inference: a [Groq API key](https://console.groq.com)
- For CV export: your LinkedIn session cookie (from browser DevTools)

## Setup

```bash
git clone <repo-url>
cd linkedin-job

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Optional: install Playwright browsers for CV scraping
playwright install
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Key variables in `.env`:

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `ollama` or `groq` |
| `GROQ_API_KEY` | If using Groq | API key from console.groq.com |
| `OLLAMA_MODEL` | If using Ollama | Model name, default `qwen2.5:14b` |
| `LINKEDIN_SESSION_COOKIE` | For CV export | Session cookie from browser DevTools |
| `DATABASE_URL` | No | Defaults to `sqlite:///data/jobs.db` |

For Ollama:

```bash
winget install Ollama.Ollama   # Windows
ollama pull qwen2.5:14b
```

## Running

**Production (single process):**

```bash
cd frontend && npm run build && cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). The built React app is served directly by uvicorn.

**Development (two processes, hot reload):**

```bash
# Terminal 1 — backend
DEBUG=1 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) for the Vite dev server (proxies `/api` to port 8000).

API docs available at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger) and `/redoc`.

## Usage

1. **Set up your profile** — go to `/profile` and add your skills, target title, and seniority level
2. **Create a search config** — go to `/search-config` and define your keywords, location, and filters
3. **Run a scrape** — go to `/scrape` and trigger a manual run, or enable the scheduler
4. **Review jobs** — go to `/jobs` to see scored results, filter by status/sector/salary, and track applications
5. **Set watch rules** — go to `/watch-rules` to get notified about jobs from specific companies or sectors
6. **Export your CV** — go to `/cv/export`, enter your LinkedIn URL, and download a PDF

## E2E Tests

Playwright e2e tests live in `frontend/e2e/` and cover four main flows: scrape, job review, watch rules, and CV export.

```bash
cd frontend
npm run test:e2e
```

Playwright will start both the backend (`uvicorn`) and the Vite dev server automatically. Reuse running servers by setting `reuseExistingServer: true` (already the default).

## Scripts

```bash
# Test the scraper without starting the server
python scripts/run_scrape.py "software engineer" "New York"

# Import a LinkedIn official data export ZIP
python scripts/import_linkedin_zip.py --zip ~/Downloads/linkedin-data.zip --output cv_output/

# Backfill existing jobs with AI summaries and company enrichment
python backfill_enrichment.py
```

## Project Structure

```
app/
├── main.py           # FastAPI app, startup/shutdown hooks
├── database.py       # SQLAlchemy engine, schema init, migrations
├── models.py         # ORM models
├── schemas/          # Pydantic schemas
├── scraper.py        # JobSpy wrapper, LinkedIn profile scraping
├── repository.py     # Data access layer
├── routes/           # FastAPI route handlers (all JSON API)
└── services/         # Business logic (LLM, CV, scheduler, watch rules)
    └── cv_export/    # CV Jinja2 templates (server-rendered for PDF)
frontend/             # React + Vite SPA
scripts/              # Standalone CLI utilities
data/                 # SQLite database (git-ignored)
```

## Notes

- The `LINKEDIN_SESSION_COOKIE` is sensitive — never commit it. Keep it in your local `.env` only.
- SQLite runs in WAL mode; the `data/` directory is git-ignored.
- Database schema migrations run automatically on startup.
