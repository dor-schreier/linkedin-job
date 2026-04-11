# Phase 1: Storage Foundation - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the SQLite database with the full schema and WAL mode enabled, and a repository layer that owns all SQL. Deliver a minimal health-check page confirming the server starts. This is the data contract all other phases depend on — no UI beyond the health check, no scraping, no AI.

</domain>

<decisions>
## Implementation Decisions

### Project Structure
- **D-01:** All source code lives in an `app/` Python package at the project root (`app/__init__.py`, `app/main.py`, `app/database.py`, `app/models.py`, `app/repository.py`).
- **D-02:** FastAPI routers go in `app/routes/` subdirectory; Jinja2 templates go in `app/templates/` subdirectory.
- **D-03:** The SQLite database file lives at `data/jobs.db` (directory: `data/` at project root).
- **D-04:** `.env` and `requirements.txt` sit at the project root.

### Claude's Discretion
- Schema design (which tables, column types, nullable fields) — Claude decides based on requirements and future-phase needs.
- Health-check page implementation — Claude decides format (JSON vs HTML). HTTP 200 is the only hard requirement.
- Config management — Claude decides approach (dotenv + .env is the standard choice per CLAUDE.md).
- WAL mode and busy_timeout values — Claude decides sensible defaults.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SCRP-03, §SCRP-04 — the two Phase 1 requirements (SQLite + WAL, job storage schema)

### Technology decisions
- `CLAUDE.md` §Technology Stack — full stack rationale, version pins, and what NOT to use

### No external specs
- No ADRs or external design docs yet — all decisions captured above and in CLAUDE.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code.

### Established Patterns
- None yet — Phase 1 establishes the patterns all future phases follow.

### Integration Points
- `app/database.py` → used by `app/main.py` lifespan to call `init_db()` on startup
- `app/repository.py` → the only file allowed to touch `data/jobs.db` directly (enforced by convention)
- `app/routes/` → Phase 3 will add route files here; Phase 1 only needs a health-check route

</code_context>

<specifics>
## Specific Ideas

- The project structure layout chosen:
  ```
  linkedin-job/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py          # FastAPI app + lifespan
  │   ├── database.py      # engine, session, init_db()
  │   ├── models.py        # SQLAlchemy ORM models
  │   ├── repository.py    # typed read/write methods
  │   ├── routes/
  │   └── templates/
  ├── data/
  │   └── jobs.db
  ├── .env
  └── requirements.txt
  ```

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-storage-foundation*
*Context gathered: 2026-04-11*
