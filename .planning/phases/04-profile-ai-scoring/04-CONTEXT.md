# Phase 4: Profile + AI Scoring - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a working profile editor and on-demand Groq AI scoring to the existing jobs UI. Users save their background (LinkedIn URL, skills, titles, experience), trigger AI scoring for jobs, and see fit scores + salary estimates inline on the jobs list. A separate "AI Insights" section on the profile page shows Groq-generated improvement recommendations on demand.

</domain>

<decisions>
## Implementation Decisions

### Profile Improvement Recommendations (PROF-03)
- **D-01:** Recommendations are triggered by a manual "Analyze Profile" button — NOT auto-generated on save. User clicks after saving when they want feedback.
- **D-02:** Recommendations display in a separate "AI Insights" section on the profile page (not inline below the form).
- **D-03:** Format: bullet list of 3–5 concise, actionable suggestions from Groq.
- **D-04:** Recommendations are persisted to the database so they survive page refresh — user sees last recommendations on every visit without re-triggering Groq.

### Claude's Discretion
- Scoring trigger UX (per-job button vs batch "Score all") — Claude decides based on simplicity
- Groq prompt design — what context to pass, how to structure the prompt, token limits
- Salary estimation trigger — whether to bundle with fit scoring or handle separately
- DB column for persisting recommendations — Claude decides column name/type on Profile table
- Fit score label thresholds (Poor/Fair/Good/Excellent) — Claude decides cutoffs
- HTMX swap strategy for AI Insights section — Claude decides partial update pattern

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §PROF-01, §PROF-02, §PROF-03, §PROF-04 — profile input and AI recommendations
- `.planning/REQUIREMENTS.md` §JOBS-02, §JOBS-03, §JOBS-04 — fit score, fit summary, salary estimation

### Technology decisions
- `CLAUDE.md` §Technology Stack — Groq SDK (sync client), FastAPI, HTMX, Tailwind, SQLAlchemy sync

### Existing schema
- `app/models.py` — Profile table columns, Job table columns (`fit_score`, `fit_summary`, `salary_estimated` already present)
- `app/repository.py` — existing repository patterns to extend for profile read/write and job score updates

### Existing templates
- `app/templates/profile.html` — placeholder template to be replaced with full profile editor + AI Insights section
- `app/templates/jobs.html` — existing jobs list to extend with fit score display

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/models.py` — `Profile` model already has all needed columns; `Job` model already has `fit_score`, `fit_summary`, `salary_estimated`
- `app/repository.py` — `JobRepository` pattern to follow for profile CRUD; extend with `update_job_scores()` method
- `app/templates/jobs.html` + `partials/` — HTMX partial swap pattern established; reuse for score display
- Tailwind + HTMX already wired in all templates via CDN

### Established Patterns
- HTMX partial updates via `hx-post` / `hx-swap` — used in scrape status polling, reuse for score updates
- Sync route handlers in `app/routes/` — Groq SDK is sync, consistent with existing pattern
- Repository dependency injection via `Depends(get_db)` — follow same pattern for profile routes

### Integration Points
- `app/routes/pages.py` — profile route currently returns placeholder; replace with full profile handler
- `app/routes/jobs.py` — extend to handle per-job or batch scoring requests
- `app/main.py` — Groq client init (add alongside existing DB lifespan setup)
- `data/jobs.db` — schema already supports Phase 4 columns (no migration needed for Job; Profile may need `ai_recommendations` column)

</code_context>

<specifics>
## Specific Ideas

- The "AI Insights" section on profile page is a distinct visual section (not a tab), appearing below the profile form, containing the last saved recommendations as a bullet list. The "Analyze Profile" button triggers a Groq call and swaps this section via HTMX.
- Recommendations persist in DB so the section is populated on page load if they already exist.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Scoring trigger, Groq prompt design, and salary estimation UX were not discussed — left to Claude's discretion per the decisions above.

</deferred>

---

*Phase: 04-profile-ai-scoring*
*Context gathered: 2026-04-12*
