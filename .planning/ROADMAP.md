# Roadmap: Job Finder

## Overview

Five phases ordered strictly by dependency: the database schema is established first (everything else writes to it), then the scrape-dedup pipeline validates data quality at the CLI level, then a working browser UI exposes that data, then AI scoring layers on top of confirmed data flow, and finally watch rules and in-app notifications complete the feature set. Every phase ends with a working app in the browser. Granularity is coarse — 5 phases, 1–2 plans each.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Storage Foundation** - SQLite schema + WAL mode — the contract all other components depend on
- [ ] **Phase 2: Scraper + Dedup Pipeline** - JobSpy → normalize → hash → INSERT OR IGNORE, validated at CLI
- [ ] **Phase 3: Web UI + API** - FastAPI + Jinja2/HTMX — first working browser app, jobs list + search config
- [ ] **Phase 4: Profile + AI Scoring** - Groq fit scoring (on-demand) + profile editor + salary estimation
- [ ] **Phase 5: Watch Rules + Notifications** - Watch rule CRUD + post-scrape match flagging + nav badge

## Phase Details

### Phase 1: Storage Foundation
**Goal**: The SQLite database exists with the full schema and WAL mode enabled; the repository layer owns all SQL
**Depends on**: Nothing (first phase)
**Requirements**: SCRP-03, SCRP-04
**Success Criteria** (what must be TRUE):
  1. Running the app creates a `.db` file with all tables (jobs, profile, search_configs, watch_rules, notifications)
  2. WAL mode and busy_timeout are configured at DB init — no "database is locked" errors under concurrent access
  3. The repository module provides typed read/write methods; no other file touches the `.db` directly
  4. A minimal health-check page is reachable in the browser (HTTP 200) confirming the server started
**Plans:** 2 plans
Plans:
- [x] 01-01-PLAN.md — SQLite schema, WAL mode, ORM models, repository layer
- [x] 01-02-PLAN.md — FastAPI app with lifespan DB init and health-check route
**UI hint**: yes

### Phase 2: Scraper + Dedup Pipeline
**Goal**: Jobs flow from JobSpy through deduplication and into the database, validated without a UI
**Depends on**: Phase 1
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SCRP-01, SCRP-02
**Success Criteria** (what must be TRUE):
  1. User can trigger a scrape run (via UI button or CLI) that fetches jobs from LinkedIn, Indeed, and Glassdoor
  2. Running the same scrape twice does not produce duplicate rows — jobs already in the DB are silently skipped
  3. Each stored job carries: title, company, location, description, source, apply URL, scraped date
  4. Search configuration (keywords, location, experience level, work mode) is saved and pre-filled on next visit
  5. A scrape triggered from the browser returns immediately; progress is visible without blocking the page
**Plans:** 2 plans
Plans:
- [ ] 02-01-PLAN.md — Scraper service module (JobSpy call, normalization, dedup, CLI validation)
- [ ] 02-02-PLAN.md — Scrape route, search config form, background task, HTMX status polling

### Phase 3: Web UI + API
**Goal**: Users can browse, filter, and manage scraped jobs in the browser with full search config control
**Depends on**: Phase 2
**Requirements**: JOBS-01, JOBS-05, JOBS-06, JOBS-07, UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. User can open the app in a browser and see a paginated/scrollable list of all scraped jobs
  2. User can filter jobs by status, company, and (if present) salary range without a full page reload
  3. User can set a per-job status (Saved / Applied / Interviewing / Offer / Rejected) from the job list
  4. Jobs with a listed salary display the actual salary range; jobs without salary show nothing (AI estimate comes in Phase 4)
  5. Navigation links to Jobs, Profile, Search Config, and Watch Rules pages all resolve without 404s
**Plans:** 2 plans
Plans:
- [ ] 02-01-PLAN.md — Scraper service module (JobSpy call, normalization, dedup, CLI validation)
- [ ] 02-02-PLAN.md — Scrape route, search config form, background task, HTMX status polling
**UI hint**: yes

### Phase 4: Profile + AI Scoring
**Goal**: Users can input their profile and see Groq-generated fit scores and salary estimates on demand
**Depends on**: Phase 3
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, JOBS-02, JOBS-03, JOBS-04
**Success Criteria** (what must be TRUE):
  1. User can save a profile (LinkedIn URL + skills/experience/target title) that persists across browser sessions
  2. User can trigger AI scoring for one or more jobs; each scored job shows a 0–100 fit score and label (Poor/Fair/Good/Excellent)
  3. Each scored job shows a brief AI summary explaining why it is or isn't a good match
  4. Jobs without a listed salary display a Groq-estimated salary range labeled "Estimated"
  5. The profile page shows Groq-generated improvement recommendations after the user saves their profile
**Plans:** 2 plans
Plans:
- [ ] 02-01-PLAN.md — Scraper service module (JobSpy call, normalization, dedup, CLI validation)
- [ ] 02-02-PLAN.md — Scrape route, search config form, background task, HTMX status polling
**UI hint**: yes

### Phase 5: Watch Rules + Notifications
**Goal**: Users can define watch rules and see matched jobs surfaced as in-app notifications after each scrape
**Depends on**: Phase 4
**Requirements**: WTCH-01, WTCH-02, WTCH-03, WTCH-04, WTCH-05, WTCH-06, WTCH-07
**Success Criteria** (what must be TRUE):
  1. User can create and delete watch rules matching by company name, role keyword, or sector tag from the UI
  2. After a scrape completes, any newly matched jobs are flagged and a badge count appears in the nav
  3. User can view all watch-matched jobs in a dedicated section
  4. The badge count resets to zero after the user views the watch matches section
**Plans:** 2 plans
Plans:
- [ ] 02-01-PLAN.md — Scraper service module (JobSpy call, normalization, dedup, CLI validation)
- [ ] 02-02-PLAN.md — Scrape route, search config form, background task, HTMX status polling
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Storage Foundation | 0/2 | Not started | - |
| 2. Scraper + Dedup Pipeline | 0/TBD | Not started | - |
| 3. Web UI + API | 0/TBD | Not started | - |
| 4. Profile + AI Scoring | 0/TBD | Not started | - |
| 5. Watch Rules + Notifications | 0/TBD | Not started | - |
