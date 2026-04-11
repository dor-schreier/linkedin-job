# Job Finder

## What This Is

A personal job opportunity finder web app. The user defines search criteria (keywords, location, job type), inputs their profile/experience, and the app scrapes jobs from multiple sites, deduplicates results, analyzes fit with Groq AI, and lets the user set watch rules to be notified in-app when matching roles appear.

## Core Value

Surface the most relevant job opportunities for the user, deduplicated and AI-ranked, without manual searching.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can define search parameters: keywords, location, job type, remote, company type
- [ ] User can input their profile: LinkedIn URL and/or manual skills/experience fields
- [ ] App scrapes jobs via JobSpy (LinkedIn capped ~250/search, Indeed/Glassdoor uncapped)
- [ ] App deduplicates jobs across sources (same job from multiple sites shown once)
- [ ] Groq AI analyzes user profile and recommends improvements
- [ ] Groq AI summarizes each job and scores fit against user profile
- [ ] User can define watch rules (company / role / sector) to flag matching jobs
- [ ] Flagged jobs surface as in-app notifications/highlights
- [ ] Web UI to browse, filter, and manage jobs

### Out of Scope

- Email or desktop push notifications — in-app only for POC simplicity
- Proxy rotation for bypassing LinkedIn rate limits — accept ~250 job cap per search
- Multi-user support — personal use only
- Auto-applying to jobs — browse and track only
- Storing or parsing uploaded resume files — use manual input or LinkedIn URL

## Context

- Scraper: **speedyapply/JobSpy** — multi-site (LinkedIn, Indeed, Glassdoor, ZipRecruiter), returns pandas DataFrames, actively maintained. LinkedIn capped at ~10 pages (~250 jobs) per IP; other sites uncapped.
- AI: **Groq API** — fast inference for profile analysis summaries and job fit scoring
- Research of alternatives documented in `.research/projects.md`
- POC for personal use — minimal complexity, working app at end of each phase

## Constraints

- **Tech stack**: Python backend (JobSpy is Python), web UI served locally
- **Scraping**: LinkedIn capped ~250 jobs/search per IP — acceptable for personal use
- **AI**: Groq API only (no OpenAI) — user has Groq API key
- **Scope**: POC / personal use — no auth, no multi-tenancy, minimal infrastructure

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| JobSpy for scraping | Multi-site, actively maintained, pandas output, easiest to integrate | — Pending |
| Groq API for AI | User preference, fast inference, free tier available | — Pending |
| Web app UI | Browser-based, no install, easiest to build in Python (Flask/FastAPI + simple frontend) | — Pending |
| In-app notifications only | POC scope — avoid email/push complexity | — Pending |
| Accept LinkedIn 250-job cap | Sufficient for personal POC; proxy rotation deferred | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-11 after initialization*
