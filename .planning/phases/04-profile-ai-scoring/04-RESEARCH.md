# Phase 4: Profile + AI Scoring - Research

**Researched:** 2026-04-12
**Domain:** Groq SDK (sync), FastAPI route extension, SQLAlchemy migration, HTMX partial updates
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Profile improvement recommendations are triggered by a manual "Analyze Profile" button — NOT auto-generated on save.
- **D-02:** Recommendations display in a separate "AI Insights" section on the profile page (not inline below the form).
- **D-03:** Recommendation format: bullet list of 3–5 concise, actionable suggestions from Groq.
- **D-04:** Recommendations are persisted to the database so they survive page refresh.

### Claude's Discretion
- Scoring trigger UX (per-job button vs batch "Score all") — Claude decides based on simplicity
- Groq prompt design — what context to pass, how to structure the prompt, token limits
- Salary estimation trigger — whether to bundle with fit scoring or handle separately
- DB column for persisting recommendations — Claude decides column name/type on Profile table
- Fit score label thresholds (Poor/Fair/Good/Excellent) — Claude decides cutoffs
- HTMX swap strategy for AI Insights section — Claude decides partial update pattern

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROF-01 | User can input their LinkedIn profile URL | Profile form → existing `Profile.linkedin_url` column |
| PROF-02 | User can input skills, current/target job title, and years of experience | Profile form → existing columns; upsert via `JobRepository.upsert_profile()` |
| PROF-03 | AI analyzes profile and returns improvement recommendations | Groq `chat.completions.create()` sync; persist in new `ai_recommendations` TEXT column |
| PROF-04 | Profile persists locally and pre-fills on subsequent visits | `get_profile()` on page load; form values populated via Jinja2 |
| JOBS-02 | Each job displays AI fit score (0–100) | Groq scoring endpoint; `Job.fit_score` column already in DB |
| JOBS-03 | Fit score includes brief AI summary | `Job.fit_summary` column already in DB |
| JOBS-04 | Jobs without listed salary show Groq-estimated salary range | `Job.salary_estimated` column already in DB; bundle with fit score call |
</phase_requirements>

---

## Summary

Phase 4 extends the existing FastAPI app with two capabilities: a full profile editor with persisted AI recommendations, and on-demand Groq-powered fit scoring for jobs. Both features build directly on columns already present in the SQLite schema (`fit_score`, `fit_summary`, `salary_estimated` on `Job`; all profile fields on `Profile`). The only schema change needed is adding an `ai_recommendations TEXT` column to the `profile` table, which must be done via `ALTER TABLE` since `init_db()` uses `create_all` (which does not modify existing tables).

Groq SDK 1.1.1 is already installed. The sync client (`groq.Groq`) matches the existing sync route pattern. Available models include `llama-3.3-70b-versatile` (best reasoning) and `llama-3.1-8b-instant` (fastest/cheapest). The recommended approach: use `llama-3.1-8b-instant` for fit scoring (many calls) and `llama-3.3-70b-versatile` for profile recommendations (one call, higher quality).

HTMX partial swap patterns are already established in the codebase. The profile AI Insights section and per-job score display both follow the same `hx-post` → partial template return pattern used for scrape status and job list filters.

**Primary recommendation:** Extend `pages.py` with a full profile GET+POST handler, add a `POST /profile/analyze` endpoint that returns an `#ai-insights` partial, add `POST /jobs/{id}/score` that scores one job and returns an updated job card partial. Bundle salary estimation inside the fit score call to minimize Groq API round trips.

---

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| groq | 1.1.1 | LLM API calls | [VERIFIED: requirements.txt] Project requirement; sync client matches existing patterns |
| fastapi | >=0.115 | Route handlers | [VERIFIED: requirements.txt] Already in use |
| sqlalchemy | >=2.0 | ORM + DB writes | [VERIFIED: requirements.txt] Existing pattern |
| jinja2 | >=3.1 | Template rendering | [VERIFIED: requirements.txt] Existing pattern |
| htmx | 2.0.4 (CDN) | Partial DOM updates | [VERIFIED: app/templates/*.html] Already loaded via CDN |

### No New Dependencies Required

All libraries needed for Phase 4 are already installed. No `pip install` needed.

---

## Architecture Patterns

### Recommended Project Structure Changes

```
app/
├── routes/
│   ├── pages.py          # EXTEND: profile GET+POST, profile analyze POST
│   └── jobs.py           # EXTEND: add POST /jobs/{id}/score
├── services/
│   └── groq_service.py   # NEW: encapsulate all Groq calls
├── templates/
│   ├── profile.html       # REPLACE: full profile editor + AI Insights section
│   └── partials/
│       ├── job_list.html          # EXTEND: add fit score display
│       ├── job_score.html         # NEW: single job score partial (swap target)
│       └── ai_insights.html       # NEW: profile AI Insights partial (swap target)
```

### Pattern 1: Profile Page — GET + POST (no HTMX, full page)

The profile form is a standard HTML form with a POST action. No HTMX needed for save — a full page redirect after save is simpler and avoids double-fetch issues. HTMX is used only for the "Analyze Profile" button which swaps the `#ai-insights` div.

```python
# Source: existing patterns in app/routes/pages.py and app/routes/scrape.py

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    return templates.TemplateResponse(request, "profile.html", {"profile": profile})

@router.post("/profile", response_class=HTMLResponse)
def profile_save(
    request: Request,
    linkedin_url: str = Form(""),
    skills: str = Form(""),
    current_title: str = Form(""),
    target_title: str = Form(""),
    years_experience: Optional[int] = Form(None),
    db: Session = Depends(get_session),
):
    repo = JobRepository(db)
    repo.upsert_profile(
        linkedin_url=linkedin_url or None,
        skills=skills or None,
        current_title=current_title or None,
        target_title=target_title or None,
        years_experience=years_experience,
    )
    from starlette.responses import RedirectResponse
    return RedirectResponse("/profile", status_code=303)
```

### Pattern 2: HTMX Partial — "Analyze Profile" button

The "Analyze Profile" button posts to `/profile/analyze` and swaps the `#ai-insights` div with the returned partial.

```html
<!-- In profile.html — Source: established HTMX pattern in jobs.html -->
<button
  hx-post="/profile/analyze"
  hx-target="#ai-insights"
  hx-swap="innerHTML"
  hx-indicator="#analyze-spinner"
  class="..."
>Analyze Profile</button>

<div id="ai-insights">
  {% include "partials/ai_insights.html" %}
</div>
```

```python
@router.post("/profile/analyze", response_class=HTMLResponse)
def profile_analyze(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    if not profile:
        return HTMLResponse("<p>Save your profile first.</p>")
    recommendations = groq_service.get_profile_recommendations(profile)
    repo.upsert_profile(ai_recommendations=recommendations)
    profile = repo.get_profile()
    return templates.TemplateResponse(request, "partials/ai_insights.html", {"profile": profile})
```

### Pattern 3: Per-Job Scoring via HTMX

Each job card has a "Score" button. Clicking posts to `/jobs/{id}/score` and swaps the job card's score section (not the full card) with the returned partial. Bundle salary estimation in the same call.

```html
<!-- In partials/job_list.html — per-job score trigger -->
<button
  hx-post="/jobs/{{ job.id }}/score"
  hx-target="#job-score-{{ job.id }}"
  hx-swap="innerHTML"
  class="text-xs text-blue-600 border border-blue-300 rounded px-2 py-0.5 hover:bg-blue-50"
>Score</button>
<div id="job-score-{{ job.id }}">
  {% if job.fit_score is not none %}
    <!-- existing score display -->
  {% endif %}
</div>
```

### Pattern 4: Groq Service Module

All Groq calls live in `app/services/groq_service.py`. The Groq client is instantiated once and passed in (or created on demand — both acceptable for a single-user app).

```python
# Source: groq SDK 1.1.1 installed in .venv
import os
from groq import Groq

def get_fit_score_and_salary(job, profile) -> dict:
    """Returns {"fit_score": int, "fit_summary": str, "salary_estimated": str|None}"""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    # Single call returns all three: score, summary, salary estimate
    ...

def get_profile_recommendations(profile) -> str:
    """Returns newline-separated bullet recommendations."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    ...
```

### Pattern 5: Groq Client Init in `main.py` lifespan (optional)

For a single-user app, instantiating `Groq()` per-request is acceptable and simpler than storing on `app.state`. The SDK reads `GROQ_API_KEY` from env automatically if not passed explicitly. No lifespan change is required unless caching the client is desired.

### Fit Score Label Thresholds (Claude's Discretion — decided here)

| Score Range | Label |
|-------------|-------|
| 0–39 | Poor |
| 40–59 | Fair |
| 60–79 | Good |
| 80–100 | Excellent |

These are intuitive quartile-ish boundaries. The Jinja2 template can derive the label with a simple `{% if %}` chain.

### Salary Estimation Trigger (Claude's Discretion — decided here)

Bundle salary estimation inside the fit score Groq call as part of the same JSON response. One API round trip per job instead of two. Jobs that already have `salary_min`/`salary_max` should skip the salary estimation portion of the prompt (pass a flag telling the model not to estimate).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON response parsing from Groq | Custom regex parser | Structured prompt + `json.loads()` on response content | Groq LLMs produce reliable JSON when asked directly in the system prompt |
| Groq retry logic | Custom retry loop | `groq.Groq()` client has built-in retry | SDK handles rate limit retries automatically |
| HTML escaping in templates | Manual `str.replace()` | Jinja2 autoescaping | Already enabled; don't disable it |

---

## Schema Migration: `ai_recommendations` column

The `profile` table already exists in `data/jobs.db` with 7 columns. `Base.metadata.create_all()` does NOT add columns to existing tables — it only creates missing tables. To add `ai_recommendations`, one of two approaches is needed:

**Approach A (simplest for POC): Raw ALTER TABLE in `init_db()`**

```python
# In app/database.py init_db() — add after create_all()
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
        conn.commit()
    except Exception:
        pass  # Column already exists — SQLite ALTER TABLE ADD COLUMN is idempotent via try/except
```

**Approach B: Alembic migration** — introduces `alembic/` directory overhead. Not justified for one column in a POC.

**Decision: Use Approach A.** It's consistent with the existing no-Alembic setup and safe to run on every startup.

Also update `app/models.py` Profile class to add the column:

```python
ai_recommendations = Column(Text, nullable=True)  # Phase 4: persisted Groq recommendations
```

---

## Groq Prompt Design

### Fit Score + Salary Prompt (per-job)

**Model:** `llama-3.1-8b-instant` — fast, cheap, good for structured extraction.

**Strategy:** Single call returning JSON. Keep the job description truncated to ~1500 chars to stay well within context limits and control latency.

```python
system_prompt = """You are a job fit analyzer. Respond ONLY with valid JSON, no other text.
Schema: {"fit_score": <int 0-100>, "fit_summary": "<1-2 sentence reason>", "salary_estimated": "<range or null>"}
fit_score: how well the candidate matches this job (0=no match, 100=perfect match).
fit_summary: brief explanation why.
salary_estimated: if no salary is listed, estimate typical range for this role and location (e.g. "$90,000 – $120,000/yr"). If salary is already provided, return null."""

user_prompt = f"""Candidate profile:
- Current title: {profile.current_title}
- Target title: {profile.target_title}
- Skills: {profile.skills}
- Years of experience: {profile.years_experience}

Job:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}
- Salary listed: {salary_listed_str}
- Description (first 1500 chars): {(job.description or "")[:1500]}"""
```

### Profile Recommendations Prompt

**Model:** `llama-3.3-70b-versatile` — higher quality for this one-shot advisory call.

```python
system_prompt = """You are a career coach. Given a job seeker's profile, return ONLY a JSON object:
{"recommendations": ["bullet 1", "bullet 2", "bullet 3"]}
Provide 3-5 concise, actionable suggestions to strengthen their profile for job searching."""

user_prompt = f"""Profile:
- LinkedIn: {profile.linkedin_url or "not provided"}
- Current title: {profile.current_title}
- Target title: {profile.target_title}
- Skills: {profile.skills}
- Years of experience: {profile.years_experience}"""
```

### Response Parsing

```python
import json

response = client.chat.completions.create(model=model, messages=[...], max_tokens=512)
content = response.choices[0].message.content.strip()
data = json.loads(content)
```

If `json.loads` raises, catch the exception and return a safe fallback (score=None, summary="Scoring unavailable", salary_estimated=None).

---

## Repository Extensions Needed

Add to `JobRepository` in `app/repository.py`:

```python
def update_job_scores(self, job_id: int, fit_score: int, fit_summary: str, salary_estimated: str | None) -> Optional[Job]:
    job = self.session.get(Job, job_id)
    if job:
        job.fit_score = fit_score
        job.fit_summary = fit_summary
        if salary_estimated is not None:
            job.salary_estimated = salary_estimated
        self.session.commit()
        self.session.refresh(job)
    return job

def get_job(self, job_id: int) -> Optional[Job]:
    return self.session.get(Job, job_id)
```

The `upsert_profile` method already exists and can accept `ai_recommendations` once the column is added.

---

## Common Pitfalls

### Pitfall 1: `create_all()` Does Not Migrate Existing Tables
**What goes wrong:** Developer adds `ai_recommendations` to `Profile` model, restarts app, column is silently missing in DB, profile analyze endpoint crashes on write.
**Why it happens:** `create_all()` skips tables that already exist — it only creates missing tables from scratch.
**How to avoid:** Use `ALTER TABLE ... ADD COLUMN` in `init_db()` wrapped in try/except.
**Warning signs:** `OperationalError: table profile has no column named ai_recommendations`.

### Pitfall 2: Groq Returns Non-JSON Despite Instructions
**What goes wrong:** LLM includes a markdown code fence (` ```json `) around the response, breaking `json.loads()`.
**Why it happens:** Models sometimes wrap JSON in markdown even when told not to.
**How to avoid:** Strip ` ```json ` and ` ``` ` from the content before parsing. Alternatively, use `response_format={"type": "json_object"}` if the model supports it.
**Warning signs:** `json.decoder.JSONDecodeError` on first Groq call.

### Pitfall 3: Scoring a Job With No Profile
**What goes wrong:** User navigates to /jobs and clicks Score before saving a profile. Groq call gets empty context, returns garbage scores.
**How to avoid:** In the score endpoint, check `repo.get_profile()` first. If None or all fields empty, return a 400 or render a "Save your profile first" message in the partial.

### Pitfall 4: HTMX `hx-swap` Target Mismatch
**What goes wrong:** The button's `hx-target` points to `#ai-insights` but the element doesn't exist on the page on first load (profile is empty).
**Why it happens:** Jinja2 conditionally renders the section only when recommendations exist.
**How to avoid:** Always render the `#ai-insights` div (even if empty), not conditionally. The partial replaces its `innerHTML`.

### Pitfall 5: `Form(...)` vs `Form("")` for Optional String Fields
**What goes wrong:** FastAPI returns 422 if a form field is missing and its default is `Form(...)`.
**Why it happens:** HTML forms don't submit empty inputs as absent — they submit `""`. But if the user clears a field entirely, it submits as empty string.
**How to avoid:** Use `Form("")` (empty string default) for optional profile fields. Convert `""` to `None` before DB write.

---

## Code Examples

### Groq sync client call (verified against installed groq 1.1.1)
```python
# Source: [VERIFIED: groq 1.1.1 in .venv — Completions.create signature inspected]
from groq import Groq
import os, json

client = Groq(api_key=os.environ["GROQ_API_KEY"])
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "system", "content": "Respond only with valid JSON."},
        {"role": "user", "content": "..."},
    ],
    max_tokens=512,
)
content = response.choices[0].message.content.strip()
data = json.loads(content)
```

### FastAPI POST form handler returning redirect
```python
# Source: [VERIFIED: established pattern in app/routes/scrape.py]
from starlette.responses import RedirectResponse

@router.post("/profile")
def profile_save(...):
    # ... save logic ...
    return RedirectResponse("/profile", status_code=303)
```

### HTMX partial swap — POST returning HTML fragment
```python
# Source: [VERIFIED: established pattern in app/routes/jobs.py]
@router.post("/profile/analyze", response_class=HTMLResponse)
def profile_analyze(request: Request, db: Session = Depends(get_session)):
    # ... call groq, persist ...
    return templates.TemplateResponse(request, "partials/ai_insights.html", {"profile": profile})
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| groq SDK | All Groq calls | Yes | 1.1.1 | — |
| GROQ_API_KEY env var | Groq client init | Unknown — not verified at research time | — | Will fail at runtime if missing |
| SQLite data/jobs.db | Schema migration | Yes | Phase 1-3 created it | — |

**Missing dependencies with no fallback:**
- `GROQ_API_KEY` must be present in `.env`. The plan must include a Wave 0 step to verify `.env` contains the key before any Groq route is exercised.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` are available on the user's Groq account and free tier | Groq Prompt Design | Scoring endpoints will 401/429 at runtime; use a different available model |
| A2 | Groq free tier RPD is sufficient for per-job on-demand scoring (not auto-scoring all) | Architecture | Hit RPD limit during testing; mitigation: scoring is already on-demand only |
| A3 | `json_object` response format is supported by `llama-3.1-8b-instant` | Pitfall 2 mitigation | Fall back to string-stripping approach |

---

## Open Questions

1. **GROQ_API_KEY presence**
   - What we know: `python-dotenv` is installed; `.env` is the convention
   - What's unclear: Whether a `.env` with a valid key exists on the dev machine
   - Recommendation: Wave 0 task verifies `GROQ_API_KEY` is set; plan should not assume it

2. **Score "all unscored" batch operation**
   - What we know: User context left this to Claude's discretion
   - Recommendation: Implement per-job score button only (simpler, avoids RPD exhaustion). A "Score all" button can be added as a v2 feature.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: app/models.py] — Profile and Job table columns confirmed directly
- [VERIFIED: data/jobs.db PRAGMA] — Live DB schema confirmed, `ai_recommendations` column absent
- [VERIFIED: groq 1.1.1 .venv] — `Completions.create` signature and available models confirmed
- [VERIFIED: requirements.txt] — All dependencies confirmed installed
- [VERIFIED: app/routes/jobs.py, pages.py, scrape.py] — Existing route and HTMX patterns confirmed

### Secondary (MEDIUM confidence)
- [CITED: groq SDK source in .venv] — Model names (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`) confirmed in Literal type hints

### Tertiary (LOW confidence — see Assumptions Log)
- A1: Groq model availability on user's account — not verified against live API

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from requirements.txt and .venv
- Architecture: HIGH — all patterns confirmed from existing codebase
- DB migration: HIGH — confirmed via live PRAGMA inspection
- Groq prompt design: MEDIUM — structure verified, quality depends on model behavior
- Pitfalls: HIGH — derived from direct code inspection + known SQLAlchemy/HTMX behaviors

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable stack; Groq model availability may change faster)
