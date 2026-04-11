# Architecture

**Domain:** Personal job aggregator / finder web app
**Researched:** 2026-04-11
**Overall confidence:** HIGH — patterns are well-established in the JobSpy ecosystem

---

## Components

### 1. Scraper

**Responsibility:** Call JobSpy with user-supplied search parameters, return raw job records.

**Boundaries:**
- Input: search config (keywords, location, job type, remote flag, sites to query, results count)
- Output: list of normalized job dicts (flattened from pandas DataFrame)
- Has no knowledge of the database, AI layer, or HTTP layer
- Runs synchronously inside a FastAPI BackgroundTask or APScheduler job; does NOT serve HTTP directly

**Notes:**
- JobSpy returns a `pandas.DataFrame`; convert to `list[dict]` immediately and discard the DataFrame
- LinkedIn capped ~250 results per search per IP — design around this, not against it
- Wrap in a try/except per site so one site failure does not abort the whole run

---

### 2. Deduplication / Normalizer

**Responsibility:** Produce a stable `job_hash` for each scraped record; filter records already in the database.

**Boundaries:**
- Input: list of raw job dicts from Scraper
- Output: list of new-only job dicts (existing ones silently dropped)
- Reads from the database (hash lookup) but does not write
- Pure Python, no external dependencies

**Hash strategy:** SHA-256 of `(title.lower().strip() + "|" + company.lower().strip() + "|" + location.lower().strip())`. URL is deliberately excluded because the same job may appear with different tracking parameters across sites.

---

### 3. Storage (Repository)

**Responsibility:** All SQLite reads and writes. Single source of truth.

**Boundaries:**
- No business logic — only INSERT, SELECT, UPDATE operations
- Exposes typed methods: `save_jobs()`, `get_jobs()`, `get_job()`, `update_job_status()`, `save_profile()`, `get_profile()`, `save_watch_rule()`, `get_watch_rules()`, `mark_notified()`
- All other components call this; nothing else touches the `.db` file directly
- Uses Python's built-in `sqlite3` module (no ORM needed at this scale)

---

### 4. AI Processor

**Responsibility:** Call Groq API to produce a fit score and summary for a job against the user profile.

**Boundaries:**
- Input: single job dict + user profile dict
- Output: `{score: int, summary: str, strengths: [str], gaps: [str]}`
- Reads profile from Storage; writes score/summary back to Storage via the Repository
- Runs as a background task after jobs are saved — never in the HTTP request path
- Rate-limit aware: process one job at a time with a small delay between calls (Groq free tier has TPM limits)

**Profile analysis** (separate from per-job scoring):
- Input: user profile text / LinkedIn URL
- Output: `{profile_summary: str, improvement_suggestions: [str]}`
- Triggered once when the user saves/updates their profile

---

### 5. Watch Rule Engine

**Responsibility:** After each scrape+save cycle, evaluate all active watch rules against newly saved jobs and flag matches.

**Boundaries:**
- Input: list of new job IDs just saved + all active watch rules from Storage
- Output: writes `notification` records to Storage for each match
- Pure Python, no external calls
- Runs synchronously after the Scraper → Dedup → Storage pipeline completes

**Match logic:** A job matches a rule when ALL specified rule criteria (company substring, role keyword, sector tag) match the job's fields (case-insensitive).

---

### 6. Web API (FastAPI)

**Responsibility:** Serve the HTTP interface consumed by the frontend. Coordinate component calls.

**Boundaries:**
- Owns request/response validation (Pydantic models)
- Delegates to Storage for reads, triggers Scraper as a BackgroundTask for writes
- Never calls Groq directly — AI Processor is invoked as a background job
- Routes: jobs CRUD, profile CRUD, watch rules CRUD, search trigger, notifications read/dismiss
- No authentication (personal use)

---

### 7. Frontend

**Responsibility:** Single-page UI served by FastAPI as static files.

**Boundaries:**
- Plain HTML + vanilla JS (or minimal framework like Alpine.js) — no build step required
- Communicates exclusively via the Web API (JSON over HTTP)
- Three views: Jobs browser (filter/sort/search), Profile editor, Watch rules manager
- Notifications surface as a badge count + dismissable list — no WebSocket needed; polls `/api/notifications` on page load

---

## Data Flow

```
User triggers scrape
        |
        v
[ Web API ]  -- POST /api/scrape -->  [ Scraper ] (BackgroundTask)
                                            |
                                    raw job dicts (list)
                                            |
                                            v
                                  [ Deduplication / Normalizer ]
                                     compute job_hash per record
                                     filter hashes already in DB
                                            |
                                    new jobs only (list)
                                            |
                                            v
                                      [ Storage ]
                                     INSERT new jobs
                                            |
                                    new job IDs (list)
                                            |
                                     +------+------+
                                     |             |
                                     v             v
                          [ AI Processor ]   [ Watch Rule Engine ]
                          score each job     evaluate rules against
                          against profile    new job IDs
                          UPDATE score/      INSERT notifications
                          summary in DB      for matches
                                     |             |
                                     v             v
                                      [ Storage ] (reads)
                                            |
                                            v
                                      [ Web API ]
                                   GET /api/jobs
                                   GET /api/notifications
                                            |
                                            v
                                      [ Frontend ]
                                   renders job list
                                   shows notification badge
```

**Direction summary:**
- Scraper → Dedup → Storage (pipeline, left to right, one-way)
- AI Processor reads Storage (profile), writes Storage (scores)
- Watch Rule Engine reads Storage (rules + new job IDs), writes Storage (notifications)
- Web API orchestrates all of the above; Frontend only talks to Web API

---

## Suggested Build Order

Dependencies drive this order: each phase produces a working vertical slice.

### Phase 1 — Storage foundation
Build the SQLite schema and Repository module first. Every other component depends on it. Nothing else can be tested end-to-end without it.

### Phase 2 — Scraper + Dedup + Storage pipeline
Wire JobSpy → normalize → hash → INSERT. Proves data lands in the DB. No UI yet — validate with a CLI script or pytest.

### Phase 3 — Web API + minimal frontend
Expose the scrape trigger and job listing via FastAPI. Build a bare-bones HTML page that lists jobs. This is the first working app you can open in a browser.

### Phase 4 — Profile + AI scoring
Add profile storage, then the Groq scoring loop. Jobs get scores and summaries. Frontend gains a profile editor and displays scores. AI runs as a BackgroundTask after scrape completes.

### Phase 5 — Watch rules + notifications
Add watch rule storage, the rule engine, notification records, and the frontend notification badge. This phase has no new external dependencies — it builds entirely on existing Storage and Web API.

**Why this order:**
- Storage first: nothing else is testable without it
- Scraper before UI: validate data quality before building display logic
- UI before AI: AI is slow and rate-limited; you want to see data flowing before layering scoring on top
- Watch rules last: lowest priority, no blockers, highest value-add once the core loop works

---

## Schema Sketch

```sql
-- User profile (single row, always id=1)
CREATE TABLE profile (
  id          INTEGER PRIMARY KEY DEFAULT 1,
  name        TEXT,
  linkedin_url TEXT,
  skills      TEXT,          -- freeform text or JSON array
  experience  TEXT,          -- freeform text
  target_role TEXT,
  target_location TEXT,
  ai_summary  TEXT,          -- Groq-generated profile summary
  ai_suggestions TEXT,       -- Groq improvement suggestions (JSON array)
  updated_at  TEXT DEFAULT (datetime('now'))
);

-- Jobs (one row per unique job across all scrape runs)
CREATE TABLE jobs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  job_hash      TEXT UNIQUE NOT NULL,  -- SHA-256 of title+company+location
  title         TEXT NOT NULL,
  company       TEXT NOT NULL,
  location      TEXT,
  job_type      TEXT,                  -- fulltime / parttime / contract
  is_remote     INTEGER DEFAULT 0,
  description   TEXT,
  url           TEXT,
  site          TEXT,                  -- linkedin / indeed / glassdoor / etc.
  date_posted   TEXT,
  salary_min    REAL,
  salary_max    REAL,
  salary_currency TEXT,
  -- AI fields (null until processed)
  ai_score      INTEGER,               -- 0-100 fit score
  ai_summary    TEXT,
  ai_strengths  TEXT,                  -- JSON array
  ai_gaps       TEXT,                  -- JSON array
  -- User tracking fields
  status        TEXT DEFAULT 'new',    -- new / saved / applied / rejected / hidden
  user_notes    TEXT,
  -- Metadata
  scraped_at    TEXT DEFAULT (datetime('now')),
  ai_processed_at TEXT
);
CREATE INDEX idx_jobs_hash    ON jobs(job_hash);
CREATE INDEX idx_jobs_status  ON jobs(status);
CREATE INDEX idx_jobs_score   ON jobs(ai_score DESC);
CREATE INDEX idx_jobs_scraped ON jobs(scraped_at DESC);

-- Search configs (saved search parameter sets)
CREATE TABLE search_configs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  keywords    TEXT,
  location    TEXT,
  job_type    TEXT,
  is_remote   INTEGER,
  sites       TEXT,              -- JSON array: ["linkedin","indeed"]
  results_per_site INTEGER DEFAULT 50,
  is_active   INTEGER DEFAULT 1,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Watch rules
CREATE TABLE watch_rules (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  company_pattern  TEXT,         -- substring match, NULL = any
  role_pattern     TEXT,         -- substring match on title, NULL = any
  sector_pattern   TEXT,         -- substring match on company/description, NULL = any
  min_score        INTEGER,      -- only flag if ai_score >= this, NULL = any
  is_active   INTEGER DEFAULT 1,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Notifications (one row per job+rule match)
CREATE TABLE notifications (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id      INTEGER NOT NULL REFERENCES jobs(id),
  rule_id     INTEGER NOT NULL REFERENCES watch_rules(id),
  is_read     INTEGER DEFAULT 0,
  created_at  TEXT DEFAULT (datetime('now')),
  UNIQUE(job_id, rule_id)        -- prevent duplicate alerts for same match
);
```

**Deduplication pattern:**
```python
INSERT OR IGNORE INTO jobs (job_hash, title, ...) VALUES (?, ?, ...)
```
The `UNIQUE` constraint on `job_hash` silently drops re-scraped duplicates.

---

## Project Layout

```
linkedin-job/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── api/
│   │   ├── jobs.py              # GET/PATCH /api/jobs
│   │   ├── scrape.py            # POST /api/scrape (triggers background run)
│   │   ├── profile.py           # GET/PUT /api/profile
│   │   ├── watch_rules.py       # CRUD /api/watch-rules
│   │   └── notifications.py     # GET/PATCH /api/notifications
│   ├── core/
│   │   ├── scraper.py           # JobSpy wrapper → list[dict]
│   │   ├── dedup.py             # hash computation + filter
│   │   ├── ai_processor.py      # Groq fit scoring + profile analysis
│   │   └── watch_engine.py      # rule evaluation → notification records
│   ├── db/
│   │   ├── database.py          # SQLite connection, init_db()
│   │   ├── repository.py        # all SQL read/write methods
│   │   └── schema.sql           # CREATE TABLE statements (run at startup)
│   ├── models/
│   │   └── schemas.py           # Pydantic models for API request/response
│   └── static/
│       ├── index.html           # single-page UI entry point
│       ├── app.js               # vanilla JS, no build step
│       └── style.css
├── data/
│   └── jobs.db                  # SQLite database file (gitignored)
├── config.py                    # settings: DB path, Groq API key, defaults
├── requirements.txt
└── .env                         # GROQ_API_KEY (gitignored)
```

**Key layout decisions:**
- `app/core/` contains pure business logic with no FastAPI imports — easy to unit test in isolation
- `app/db/repository.py` is the only file that imports `sqlite3` — all SQL is centralized
- `app/static/` is served by FastAPI's `StaticFiles` mount — no separate web server needed
- `data/jobs.db` outside `app/` so it is never accidentally included in source trees
- `config.py` reads from environment / `.env` via `python-dotenv`

---

## Sources

- [JobSpy GitHub (speedyapply)](https://github.com/speedyapply/JobSpy) — scraper capabilities and parameters
- [BjornMelin/ai-job-scraper](https://github.com/BjornMelin/ai-job-scraper) — SQLite FTS5 + pipeline architecture reference
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — background task pattern (no Celery)
- [APScheduler + FastAPI (Medium)](https://ahaw021.medium.com/scheduled-jobs-with-fastapi-and-apscheduler-5a4c50580b0e) — scheduler integration pattern
- [SQLite for AI Agents (DEV)](https://dev.to/nathanhamlett/sqlite-is-the-best-database-for-ai-agents-and-youre-overcomplicating-it-1a5g) — deduplication via hash column pattern
- [SQLite Forum — hash-based dedup](https://sqlite.org/forum/forumpost/7fecf11e42c71a91) — UNIQUE index + INSERT OR IGNORE pattern
