# Pitfalls

**Domain:** Personal job scraper / finder web app
**Stack:** Python + JobSpy + Groq API + SQLite + local web server
**Researched:** 2026-04-11
**Overall confidence:** HIGH (verified against JobSpy issues tracker, Groq official docs, SQLite concurrency literature)

---

## Critical (will break the app)

| Pitfall | Warning Signs | Prevention | Phase |
|---------|---------------|------------|-------|
| **SQLite "database is locked" from concurrent scraper + web server** | Flask returns 500 errors intermittently when background scrape is running; logs show `sqlite3.OperationalError: database is locked` | Enable WAL mode (`PRAGMA journal_mode=WAL`) at DB init. Set `busy_timeout` to at least 3000 ms. Never share a single connection object across threads — use per-request connections or a connection factory. Use `check_same_thread=False` only with proper per-thread connection management. | Scraping phase (background job) |
| **JobSpy LinkedIn 429 rate-limit mid-scrape silently returns partial results** | Scrape runs without exception but returns far fewer jobs than expected (e.g., 20 instead of 200); no error raised in code | Check `len(results)` after every scrape call. Log HTTP response codes from JobSpy when `verbose=2`. Add a minimum-results threshold warning. Accept the ~250/10-page cap as a hard ceiling and document it in UI. | Scraping phase |
| **Groq free-tier RPD exhausted during bulk job scoring** | First N jobs score fine, then all subsequent jobs return empty scores or `429` responses; app silently drops AI analysis | On free tier: llama-3.3-70B = 1,000 req/day hard ceiling. With 250 jobs per scrape, one full run = 250 requests, leaving only 750 for the day. Either batch into a single prompt (many jobs → one request), use llama-3.1-8b-instant (14,400 RPD), or gate AI scoring behind an explicit "score now" button rather than auto-scoring all results. | AI scoring phase |
| **JobSpy field schema changes break downstream code** | After `pip install --upgrade python-jobspy`, fields that previously existed return `NaN` or `KeyError`; salary, date, or description fields suddenly missing | Pin `python-jobspy` to a specific version in `requirements.txt`. Do not auto-upgrade. Read the releases changelog before upgrading. Wrap all DataFrame column accesses with `.get()` / `fillna()` guards so missing fields degrade gracefully rather than crashing. | Scraping phase |
| **Groq API key exposed in code or logs** | API key appears in version control, server logs, or error tracebacks | Load from environment variable (`os.environ["GROQ_API_KEY"]`), never hardcode. Add `.env` to `.gitignore` before first commit. | Project setup / Phase 1 |

---

## Important (will hurt UX)

| Pitfall | Warning Signs | Prevention | Phase |
|---------|---------------|------------|-------|
| **Deduplication fails: same job shown multiple times with slightly different titles** | User sees "Software Engineer II" from LinkedIn and "Mid-Level Software Engineer" from Indeed for the same role at the same company | Deduplicate on composite key: `(normalized_company, normalized_title, location)`. Normalize by lowercasing, stripping punctuation, collapsing whitespace. Fuzzy match with `rapidfuzz` (token_sort_ratio >= 85) as a second pass for title variations. Do not rely on job URL alone — different boards use entirely different URLs for the same post. | Scraping / dedup phase |
| **Watch rule matching too strict — user never sees alerts** | User creates rule "Google / Backend Engineer" but no jobs ever match because the posted title is "Backend Software Engineer, Core Infra" | Use substring + token matching for watch rules, not exact match. Match on individual tokens from the rule against the job title. Provide a "test rule" preview showing how many current jobs would match before saving. | Watch rules phase |
| **Watch rule matching too loose — every job triggers an alert** | User is flooded with matches for a "software" rule because it matches "software" in every job description | Scope watch rule matching to job title + company name only, not full description. Require all tokens in a multi-word rule to match (AND logic, not OR). | Watch rules phase |
| **Stale jobs accumulate — closed roles never removed** | Job list grows indefinitely with roles that were filled weeks ago; user wastes time on dead listings | Store `scraped_at` timestamp. Flag jobs older than a configurable threshold (default: 14 days) as stale in the UI. On re-scrape, mark jobs not seen in latest results as `likely_closed`. Do not auto-delete — surface the status in UI. | Scraping phase |
| **Groq token cost blows up on long job descriptions** | Single job description with 3,000 tokens of boilerplate JD text consumes 3x the expected tokens; daily limit hit after 80 jobs instead of 250 | Truncate job description to 800–1,200 tokens before sending to Groq. Strip boilerplate patterns (EEO statements, "About us" sections) with a regex pre-filter. Log token usage per request using Groq's response headers. | AI scoring phase |
| **Scrape blocks the web server — UI freezes during scrape** | Browser tab hangs or shows spinner for 30–90 seconds when scrape is triggered; Flask's dev server is single-threaded by default | Run scraper in a background thread or subprocess. Use a `scrape_status` table row in SQLite that the frontend polls. Return immediately from the scrape endpoint with a job ID; poll `/scrape/status/<id>` for progress. Never run scraping synchronously in a request handler. | Scraping phase |
| **LinkedIn selector breakage from LinkedIn DOM changes** | Scrape runs without error but returns 0 jobs from LinkedIn; other sources still work | Monitor JobSpy releases — LinkedIn scraper has broken 3+ times in 2025 from DOM changes. Pin versions. Add a post-scrape assertion: if LinkedIn returns 0 results when other sites return results, log a specific warning "LinkedIn scraper may be broken — check JobSpy release notes." | Scraping phase |
| **Groq prompt returns inconsistent score format** | AI fit score is sometimes a number (85), sometimes a string ("8.5/10"), sometimes missing entirely; downstream sort/filter breaks | Define a strict JSON output schema in the system prompt. Validate the parsed response with a Pydantic model or simple type check. On parse failure, store `score=None` and surface "score unavailable" in UI rather than crashing. | AI scoring phase |

---

## Watch Out (scope creep / time sinks)

| Pitfall | Prevention |
|---------|------------|
| **Building a "beautiful" UI before the scraper works** | Get data flowing into SQLite first. Use a plain HTML table with minimal CSS until all backend features work. Style last. |
| **Over-engineering the deduplication algorithm** | Composite key + one round of fuzzy matching is sufficient for a personal POC. Do not implement ML-based dedup — it's months of work for marginal gain. |
| **Adding email / Slack / push notifications** | Explicitly out of scope. In-app highlighting is sufficient. Every time this urge appears, document it as a future idea rather than implementing it. |
| **Resume parsing from PDF/DOCX** | Out of scope. Manual skills input + LinkedIn URL covers the POC need. Resume parsing is a distinct 2–4 week sub-project. |
| **Supporting multiple user profiles / saved searches** | Personal use only. Adding multi-profile support requires auth, session management, and data isolation — a 3x complexity multiplier. |
| **Adding "apply tracking" (status columns, notes, contacts)** | This turns the job finder into a full ATS (Applicant Tracking System). Define the boundary: the app finds and scores jobs; it does not manage applications. |
| **Trying to scrape LinkedIn beyond the 250-job cap without proxies** | The 250-job cap per IP is a documented constraint. Proxy rotation was explicitly deferred. Do not attempt to work around it inside the POC. |
| **Building a cron scheduler inside the app** | For a personal POC, a manual "refresh" button is sufficient. OS-level cron / Task Scheduler handles scheduling without in-app complexity. |
| **Chasing 100% dedup accuracy** | Some cross-site duplicates will slip through. For personal use, a 90% dedup rate is acceptable. Do not spend more than one phase iteration on dedup refinement. |
| **Groq model selection analysis paralysis** | Start with `llama-3.3-70b-versatile` for quality. If free tier RPD is hit, switch to `llama-3.1-8b-instant`. That's the entire decision tree. |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Initial DB setup | Forgetting WAL mode + busy_timeout before any concurrent code exists | Set both in DB init script, not in scraper or server code |
| First scrape run | LinkedIn returns 0 due to bot detection on first run from fresh IP | Test with Indeed first; validate data pipeline before testing LinkedIn |
| AI scoring rollout | All 250 jobs scored in one loop exhausts daily Groq quota | Implement batched or on-demand scoring before wiring up auto-score |
| Watch rules | Rule matching produces 0 or 500+ matches — both useless | Add a rule-preview endpoint that returns match count before saving the rule |
| UI refresh | Full page reload on every poll makes app feel broken | Use `fetch()` to poll `/jobs` endpoint and update only the job list DOM element; no full reloads |

---

## Sources

- [JobSpy GitHub Issues](https://github.com/speedyapply/JobSpy/issues) — recurring 429, field bugs, LinkedIn selector breakage
- [JobSpy Releases](https://github.com/speedyapply/JobSpy/releases) — changelog, breaking changes
- [Groq Rate Limits (official)](https://console.groq.com/docs/rate-limits) — RPM, RPD, TPM by model
- [Groq Free Tier Limits 2026 — Grizzly Peak Software](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)
- [SQLite Concurrent Writes and "database is locked"](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [SQLite WAL Mode and Connection Strategies](https://dev.to/software_mvp-factory/sqlite-wal-mode-and-connection-strategies-for-high-throughput-mobile-apps-beyond-the-basics-eh0)
- [LinkedIn Scraping Detection 2025 — GoLogin](https://gologin.com/blog/scraping-data-from-linkedin/)
- [Job Scraping Deduplication Pitfalls 2025 — JobSpikr](https://www.jobspikr.com/blog/guide-to-job-scraping/)
