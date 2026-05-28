# LinkedIn Job Finder

A self-hosted job search automation tool that scrapes jobs from LinkedIn, Indeed, Glassdoor, and Comeet, scores them against your profile using AI, and helps you track applications — all from a local web UI.

## Features

- **Multi-source job scraping** — pulls from LinkedIn, Indeed, Glassdoor (via JobSpy), and Comeet (via Google site-search)
- **AI fit scoring** — rates each job 0–100 against your profile (skills, target title, seniority level)
- **CV upload & parsing** — upload your LinkedIn PDF export; LLM extracts your experience, skills, and profile data automatically
- **CV tailoring** — one-click AI-tailored CV per job posting, downloadable as PDF or DOCX
- **Scheduled scraping** — runs your saved search configs on a configurable interval (default: every 6 hours)
- **Real-time scrape progress** — live phase + row-count tracking while a scrape runs
- **Job tracking** — move jobs through statuses: NEW → SAVED → APPLIED → INTERVIEWING → OFFER / REJECTED
- **Watch rules & notifications** — get alerted when jobs matching a company, keyword, or sector appear
- **Auto-reject rules** — define criteria to automatically reject jobs on ingest
- **Company enrichment** — AI-generated company summaries (sector, type, what they do)
- **Keyword gap analysis** — compares job intelligence data against your profile skills to surface missing keywords
- **Profile optimizer** — AI recommendations for strengthening your LinkedIn profile
- **Job link cleanup** — background checker that re-validates job URLs and marks inactive postings

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy (SQLite), APScheduler
- **Frontend:** React 19 + Vite (SPA, served as static files in production), TailwindCSS 4, React Query
- **AI:** Groq, Ollama (local), or Vertex AI (Gemini) — switch via `LLM_PROVIDER`
- **Scraping:** JobSpy + Playwright; Comeet via configurable Google search backend

## Requirements

- Python 3.10+
- Node 18+ (for the frontend)
- LLM access: Groq API key, local Ollama, or Google Cloud (Vertex AI)
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

# Optional: install Playwright browsers for CV scraping and Comeet fallback
playwright install
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `groq`, `ollama`, or `vertexai` |
| `GROQ_API_KEY` | If `LLM_PROVIDER=groq` | API key from console.groq.com |
| `GROQ_FIT_MODEL` | No | Default `llama-3.1-8b-instant` |
| `GROQ_RECOMMEND_MODEL` | No | Default `llama-3.3-70b-versatile` |
| `OLLAMA_MODEL` | If `LLM_PROVIDER=ollama` | Default `qwen2.5:14b` |
| `OLLAMA_BASE_URL` | No | Default `http://localhost:11434/v1` |
| `GOOGLE_CLOUD_PROJECT` | If `LLM_PROVIDER=vertexai` | GCP project ID |
| `VERTEX_AI_LOCATION` | If `LLM_PROVIDER=vertexai` | Default `us-central1` |
| `VERTEX_LLM_FIT_MODEL` | No | Default `gemini-2.5-flash-lite` |
| `VERTEX_LLM_RECOMMEND_MODEL` | No | Default `gemini-2.5-flash` |
| `LINKEDIN_SESSION_COOKIE` | For CV scrape export | Session cookie from browser DevTools |
| `DATABASE_URL` | No | Defaults to `sqlite:///data/jobs.db` |

For Ollama:

```bash
winget install Ollama.Ollama   # Windows
ollama pull qwen2.5:14b
```

## Running

**Production (single process):**

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). The built React app is served directly by uvicorn.

**Development (two processes, hot reload):**

```bash
# Terminal 1 — backend
DEBUG=1 uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) for the Vite dev server (proxies `/api` to port 8000).

API docs available at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger) and `/redoc`.

## Usage

1. **Set up your profile** — go to `/profile`, add your skills, target title, and seniority level; optionally upload your LinkedIn PDF for richer data
2. **Create a search config** — go to `/search-config` and define your keywords, location, and filters
3. **Run a scrape** — go to `/scrape` and trigger a manual run, or enable the scheduler; watch real-time progress
4. **Review jobs** — go to `/jobs` to see scored results, filter by status/sector/salary, and track applications
5. **Tailor your CV** — open any job and click "Generate Tailored CV" to produce a job-specific PDF or DOCX
6. **Set watch rules** — go to `/watch-rules` to get notified about jobs from specific companies or sectors

## CV Features

### Upload & Parse

Upload a LinkedIn PDF export from your browser (`Settings → Data Privacy → Get a copy of your data`). The LLM extracts your full profile — experience, skills (with endorsement counts), education, certifications, projects — and stores it for use in fit scoring and CV tailoring.

Routes:
- `POST /api/profile/cv-upload` — upload and parse
- `GET /api/profile/cv-upload` — fetch latest parsed result
- `DELETE /api/profile/cv-upload` — remove stored PDF

### Tailored CV generation

For any job, click "Generate Tailored CV". The LLM rewrites your experience bullets to emphasize the job's required skills and tech stack, selects your top 12 most relevant skills, and writes a 3–4 line professional summary. Output is downloadable as PDF or DOCX.

Routes:
- `POST /api/jobs/{job_id}/cv/generate` — generate (LLM call)
- `GET /api/jobs/{job_id}/cv/pdf` — download as PDF
- `GET /api/jobs/{job_id}/cv/docx` — download as DOCX
- `DELETE /api/jobs/{job_id}/cv` — delete generated CV

## Scraping

### JobSpy sources (LinkedIn, Indeed, Glassdoor)

The default scrape path uses [JobSpy](https://github.com/Bunsly/JobSpy) to pull from LinkedIn, Indeed, and optionally Glassdoor (Glassdoor is only enabled for countries it supports: US, CA, UK, etc.).

### Comeet

When **Include Comeet** is toggled on in the search config, the scraper issues a `site:comeet.com/jobs/ {keyword}` search for each keyword, fetches the resulting job pages, and parses title/company/location/description from the server-rendered HTML. Results flow through the same dedup, filter, company enrichment, fit scoring, and reject/watch-rule pipeline as JobSpy rows.

**Search backends** (configured via `GOOGLE_SEARCH_BACKEND`):

| Backend | Key | Notes |
|---|---|---|
| `vertex` / `vertexai` | — | Vertex AI Search (Discovery Engine); most reliable; requires GCP setup |
| `cse` | `GOOGLE_CSE_KEY`, `GOOGLE_CSE_CX` | Google Custom Search Engine; closed to new signups as of 2025 |
| `ddgs` | — | DuckDuckGo; no API key required |
| `google` | — | Scrapes google.com directly; auto-falls back to Playwright on block |
| `playwright` | — | Headless Chromium; last-resort fallback |

**Vertex AI Search setup:** create a Web App data store in GCP → Vertex AI Agent Builder, restrict it to `comeet.com/*`, grant `Discovery Engine Viewer` to your service account, then set `GOOGLE_CLOUD_PROJECT`, `VERTEX_AI_DATA_STORE_ID`, `VERTEX_AI_ENGINE_ID`, and `VERTEX_AI_LOCATION`.

**Automatic fallback chain:** configured primary → GoogleScrapeBackend → PlaywrightGoogleBackend. DDGS is selectable but not in the auto-fallback chain.

Relevant env vars: `GOOGLE_SEARCH_BACKEND`, `COMEET_REQUEST_DELAY_MS`.

## E2E Tests

Playwright e2e tests live in `frontend/e2e/`.

```bash
cd frontend
npm run test:e2e
```

Playwright will start both the backend (`uvicorn`) and the Vite dev server automatically.

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
├── main.py                   # FastAPI app, startup/shutdown hooks
├── database.py               # SQLAlchemy engine, schema init, migrations
├── models.py                 # ORM models
├── schemas/                  # Pydantic request/response schemas
├── schemas_core.py           # Shared domain schemas (CVData, LinkedInProfile, etc.)
├── scraper.py                # JobSpy wrapper, LinkedIn profile scraping
├── repository.py             # Data access layer
├── routes/                   # FastAPI route handlers
│   ├── cv.py                 # CV generation + download endpoints
│   └── cv_upload.py          # LinkedIn PDF upload/parse endpoints
└── services/
    ├── llm_service.py        # Multi-provider LLM (Groq / Ollama / Vertex AI)
    ├── cv_pdf_parser.py      # PDF text extraction + LLM profile parsing
    ├── cv_tailoring.py       # Job-specific CV rewriting via LLM
    ├── cv_renderer.py        # WeasyPrint (PDF) + python-docx (DOCX) rendering
    ├── scheduler.py          # APScheduler background scrape
    └── cv_export/
        └── templates/cv/     # Jinja2 HTML templates for PDF rendering
frontend/                     # React + Vite SPA
scripts/                      # Standalone CLI utilities
data/                         # SQLite database (git-ignored)
```

## Notes

- The `LINKEDIN_SESSION_COOKIE` is sensitive — never commit it. Keep it in your local `.env` only.
- SQLite runs in WAL mode; the `data/` directory is git-ignored.
- Database schema migrations run automatically on startup (`app/database.py`).
- Session logs are written to `logs/app-YYYYMMDD-HHMMSS.log` — one file per app start; the directory is git-ignored.
