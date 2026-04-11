<!-- GSD:project-start source:PROJECT.md -->
## Project

**Job Finder**

A personal job opportunity finder web app. The user defines search criteria (keywords, location, job type), inputs their profile/experience, and the app scrapes jobs from multiple sites, deduplicates results, analyzes fit with Groq AI, and lets the user set watch rules to be notified in-app when matching roles appear.

**Core Value:** Surface the most relevant job opportunities for the user, deduplicated and AI-ranked, without manual searching.

### Constraints

- **Tech stack**: Python backend (JobSpy is Python), web UI served locally
- **Scraping**: LinkedIn capped ~250 jobs/search per IP — acceptable for personal use
- **AI**: Groq API only (no OpenAI) — user has Groq API key
- **Scope**: POC / personal use — no auth, no multi-tenancy, minimal infrastructure
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
| Layer | Choice | Version | Rationale | Confidence |
|-------|--------|---------|-----------|------------|
| Web framework | FastAPI | `>=0.115` (latest stable) | ASGI, async-native, built-in Pydantic validation, auto Swagger docs, background tasks via lifespan, first-class HTMX/Jinja2 support. Faster than Flask for this use case because the job scrape + Groq AI calls are I/O-bound and benefit from async. Flask is fine but is WSGI-sync and adds no advantage here. | HIGH |
| ASGI server | Uvicorn | `>=0.30` | Standard ASGI server for FastAPI. Single command to run the app locally. No Gunicorn needed for single-user POC. | HIGH |
| Frontend rendering | Jinja2 + HTMX | Jinja2 `>=3.1`, HTMX `2.x` (CDN) | Server-side rendering via Jinja2 (ships with FastAPI/Starlette) for zero JS build tooling. HTMX via CDN `<script>` tag gives dynamic partial updates (filter jobs, refresh feed) without React/Vite/webpack. No separate frontend project, no npm, no bundler. Correct choice for a Python POC with one developer. | HIGH |
| CSS | TailwindCSS (CDN) | Latest CDN build | No build step, small HTML classes, looks good fast. Alternative is plain CSS — both acceptable. Avoid Bootstrap if using HTMX; Bootstrap JS can conflict. | MEDIUM |
| Database | SQLite via SQLAlchemy | SQLAlchemy `2.0.x` (latest: 2.0.49) | SQLite is zero-config, file-based, no server process. SQLAlchemy 2.0 is the right ORM layer: Pythonic models, future-proofs migration to Postgres if needed, Alembic for schema changes, much cleaner than raw `sqlite3` for a schema with 3+ tables (jobs, search configs, watch rules). Use sync SQLAlchemy (not asyncio variant) since JobSpy itself is sync — mixing async DB with sync scraper adds complexity for no gain. | HIGH |
| Job scraper | jobspy (speedyapply) | `>=1.1.79` (latest: 1.1.79, Mar 2026) | Project requirement. Returns pandas DataFrames. Multi-site concurrent scraping. | HIGH |
| AI / LLM | groq (official SDK) | `1.1.1` (latest, Mar 2026) | Project requirement. `pip install groq`. OpenAI-compatible API surface. Both sync and async clients available. Use sync client to match JobSpy's sync execution model. | HIGH |
| Env / secrets | python-dotenv | `>=1.0` | Standard pattern for keeping `GROQ_API_KEY` out of source code. Load `.env` at startup. Essential since this repo could be pushed to GitHub. | HIGH |
| Job scheduling / polling | APScheduler | `3.11.2` (latest stable, Dec 2025) | Runs recurring job refresh inside the FastAPI process using `AsyncIOScheduler` started in the `lifespan` context. No separate process, no Redis, no Celery. Cron and interval triggers supported. Only caveat: don't use multiple uvicorn workers (single worker is correct for local personal-use app). | HIGH |
| Data manipulation | pandas | `>=2.2` | Required by JobSpy (returns DataFrames). Use it for deduplication before persisting to SQLite. Do not store DataFrames — convert to dicts/ORM models before writing. | HIGH |
| Validation / data models | Pydantic | `>=2.0` (ships with FastAPI) | FastAPI bundles Pydantic v2. Use it for API request/response schemas and for the Groq response parsing. No separate install needed. | HIGH |
## What NOT to Use
| Option | Avoid Because |
|--------|---------------|
| **Flask** | WSGI (synchronous). No built-in async — you'd need threading workarounds to run APScheduler background jobs cleanly alongside request handling. FastAPI is strictly better here with no added complexity. |
| **Streamlit** | Re-runs the entire script top-to-bottom on every user interaction. Fine for data demos, but breaks down for a stateful app with background scraping, watch rules, and persistent storage. No proper routing. You'd hit a wall in Phase 2. |
| **Django** | Way too much overhead — ORM, migrations, admin, auth — none of which are needed for a single-user POC. Brings weeks of setup cost with no benefit. |
| **React / Vue / Next.js** | Separate frontend project means a JS build toolchain (npm, Vite/webpack), CORS config, and two codebases to maintain. This is a Python POC. HTMX + Jinja2 gives 90% of the UX with 10% of the complexity. |
| **PostgreSQL / MySQL** | No server process needed for personal use. SQLite handles the load. Switching to Postgres later via SQLAlchemy is one URL change. |
| **Celery + Redis** | Celery is for distributed task queues across multiple workers and machines. This is a single-user local app. APScheduler in-process is the right scope. Celery adds a Redis dependency and a separate worker process for zero benefit here. |
| **SQLAlchemy asyncio mode** | JobSpy is synchronous. Mixing async SQLAlchemy (which requires greenlet or async driver) with sync scraping creates session management complexity. Use sync SQLAlchemy. FastAPI can run sync routes on a threadpool — no blocking issues for a personal app. |
| **Raw `sqlite3` module** | Viable for a tiny script, but you'll want schema evolution (Alembic), typed models, and relationship queries as soon as watch rules and job deduplication land. SQLAlchemy Core pays for itself by Phase 2. |
| **APScheduler 4.x (beta)** | APScheduler 4 is a full rewrite with a completely different API, still pre-stable as of late 2025. Stick with 3.x which has a massive stable install base and clear FastAPI integration patterns. |
| **LangChain / LangGraph** | Unnecessary abstraction for this use case. You're making direct Groq API calls for job summaries and profile analysis — the `groq` SDK is all you need. LangChain adds hundreds of MB of dependencies and opaque abstractions for simple chat completion calls. |
## Notes
### Project structure
### Key install command
### APScheduler + FastAPI lifespan pattern (use this, not @app.on_event)
### Groq model to use
### SQLite file location
### LinkedIn scraping cap
### JobSpy scraping cadence
## Sources
- FastAPI vs Flask comparison: https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison
- FastAPI + HTMX + Jinja2: https://testdriven.io/blog/fastapi-htmx/ and https://fastapi.tiangolo.com/advanced/templates/
- JobSpy GitHub (speedyapply): https://github.com/speedyapply/JobSpy
- Groq Python SDK: https://pypi.org/project/groq/ and https://github.com/groq/groq-python
- SQLAlchemy 2.0: https://www.sqlalchemy.org/ (latest: 2.0.49, April 2026)
- APScheduler 3.x: https://pypi.org/project/APScheduler/ (latest: 3.11.2, December 2025)
- APScheduler + FastAPI lifespan: https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186
- Streamlit limitations vs FastAPI: https://www.kaggle.com/questions-and-answers/475580
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
