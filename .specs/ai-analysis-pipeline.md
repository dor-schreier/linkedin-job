# AI Analysis Pipeline Spec

Combines: Enhanced Fit Scoring (#2), Job Description Intelligence Extraction (#3), Profile Keyword Gap Analysis (#4).

These are sequentially dependent: JD extraction produces structured data → scoring uses it → keyword gap aggregates across scored jobs.

## References
- Groq SDK: `groq` Python package, sync client (match JobSpy sync model)
- Model: Use model specified in CLAUDE.md Groq config
- Resume Matcher pattern (from research): show matching qualifications, gaps, and specific wording changes per job
- LinkedIn recruiter behavior: current job title is most weighted field; keyword density matters

---

## Phase 1: Job Description Intelligence Extraction (Section 3)

Extract structured fields from raw job descriptions using Groq on scrape/import.

### Tasks

- [x] Define a `JobIntelligence` Pydantic model with fields:
  - `required_skills: list[str]`
  - `preferred_skills: list[str]`
  - `seniority_level: str` (actual, not listed)
  - `remote_policy: str` (onsite/hybrid/remote)
  - `tech_stack: list[str]`
  - `team_size_signals: str | None`
  - `salary_signals: str | None`
  - `red_flags: list[str]` (e.g., "fast-paced" = understaffed, "wear many hats" = under-resourced)
- [x] Create Groq prompt that takes raw JD text and returns structured JSON matching `JobIntelligence`
- [x] Add `intelligence_json` column to `Job` model (JSON text field)
- [x] Create Alembic migration for the new column
- [x] Hook extraction into the scrape pipeline — after dedup, before DB insert
- [x] Add error handling: if Groq extraction fails, store job without intelligence (don't block insert)
- [x] Rate limit Groq calls during batch extraction (respect Groq rate limits)
- [x] Add "Re-extract" button on job detail view for manual re-run
- [x] Display extracted fields on job detail page in structured format

## Phase 2: Enhanced Fit Scoring (Section 2)

Expand Groq scoring from single number to structured breakdown.

### Tasks

- [ ] Define `FitScoreBreakdown` Pydantic model:
  - `overall_score: int` (0-100)
  - `matching_qualifications: list[str]`
  - `missing_qualifications: list[str]`
  - `experience_alignment: str` (seniority match assessment)
  - `red_flags: list[str]` (from JD intelligence)
  - `application_priority: str` (High/Medium/Low — combines fit + posting age + salary match)
  - `summary: str` (2-3 sentence recommendation)
- [ ] Update Groq scoring prompt to:
  - Accept structured JD intelligence (from Phase 1) instead of raw text when available
  - Accept user profile fields (skills, experience, target title)
  - Return `FitScoreBreakdown` JSON
- [ ] Add `score_breakdown_json` column to `Job` model
- [ ] Create Alembic migration
- [ ] Update scoring endpoint to store full breakdown
- [ ] Update job card UI to show priority badge (High/Medium/Low) instead of just number
- [ ] Add expandable score breakdown section on job card or detail view
- [ ] Show matching vs. missing qualifications visually (green checks / red gaps)
- [ ] Factor in `date_posted` age when computing `application_priority`

## Phase 3: Profile Keyword Gap Analysis (Section 4)

Aggregate keywords across matched jobs and compare against user profile.

### Tasks

- [ ] Create aggregation function that:
  - Pulls `required_skills` and `tech_stack` from all jobs with intelligence data
  - Counts frequency of each skill/keyword
  - Compares against user profile `skills` field
  - Identifies gaps: skills appearing in >20% of matched jobs but missing from profile
- [ ] Create `KeywordGap` Pydantic model:
  - `keyword: str`
  - `frequency_pct: float` (% of matched jobs containing it)
  - `in_profile: bool`
- [ ] Add keyword gap analysis endpoint
- [ ] Build UI panel on profile page: "Add X to your profile — it appears in Y% of your matched jobs"
- [ ] Optionally use Groq to generate natural-language recommendation from gap data
- [ ] Add "Refresh Analysis" button that re-runs aggregation
- [ ] Consider filtering by recent jobs only (last 30 days) to keep recommendations current

## Testing

- [ ] Unit test: Groq JD extraction prompt returns valid `JobIntelligence` for sample JDs
- [ ] Unit test: Scoring prompt returns valid `FitScoreBreakdown`
- [ ] Unit test: Keyword aggregation correctly counts frequencies and identifies gaps
- [ ] Integration test: Full pipeline — scrape → extract → score → aggregate
- [ ] Edge case: Job with minimal/empty description
- [ ] Edge case: User profile with no skills filled in
