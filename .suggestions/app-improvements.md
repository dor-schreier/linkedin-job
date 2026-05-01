# App Improvement Suggestions

Based on full codebase analysis (2026-04-12).

---

## HIGH IMPACT — Core Job-Finding Effectiveness

### 1. Application Timing Urgency Indicator
**Problem:** Jobs posted >72 hours ago have dramatically lower callback rates, but the app shows no age urgency.
**Suggestion:** Add a `posted_age` urgency badge to job cards: "Fresh" (<24h), "Apply Soon" (24-72h), "Late" (>72h). JobSpy returns `date_posted` — use it. This alone could meaningfully improve the user's success rate.

### 2. Enhanced Fit Scoring (Structured Breakdown)
**Problem:** Current Groq scoring returns a single 0-100 number + 1-2 sentence summary. Not actionable enough.
**Suggestion:** Expand the scoring prompt to return:
- **Matching qualifications** (what the user already has)
- **Missing qualifications** (gaps to address or acknowledge)
- **Experience alignment** (seniority match)
- **Red flags** (signals like "fast-paced" = understaffed, "wear many hats" = under-resourced)
- **Application priority** (combine fit score + posting age + salary match)

### 3. Job Description Intelligence Extraction
**Problem:** Job descriptions are stored as raw text blobs. No structured data extracted.
**Suggestion:** Use Groq to extract structured fields on scrape:
- Required vs. nice-to-have skills
- Actual seniority level (vs. what's listed)
- Remote/hybrid/onsite policy
- Tech stack
- Team size signals
- Salary signals (even if not listed)
Store these as structured JSON on the Job model for better filtering and matching.

### 4. Profile Keyword Gap Analysis
**Problem:** No feedback loop between what jobs want and what the user's profile says.
**Suggestion:** Aggregate the most common keywords/skills across matched jobs, compare against the user's profile, and surface: "Add 'Kubernetes' to your profile — it appears in 68% of your matched jobs but isn't in your profile." This directly improves LinkedIn recruiter visibility.

### 5. Activate APScheduler for Recurring Scrapes
**Problem:** APScheduler is installed but completely unused. Scrapes are manual-only. Watch rules only trigger on manual scrapes.
**Suggestion:** Wire up APScheduler in the FastAPI lifespan (the pattern is already documented in CLAUDE.md). Allow users to set scrape frequency (e.g., every 6 hours). This makes watch rules actually useful — jobs surface automatically instead of requiring the user to remember to scrape.

---

## MEDIUM IMPACT — Better Matching & Filtering

### 6. Semantic Deduplication
**Problem:** Current dedup is exact hash of (title|company|location). "Software Engineer" and "SWE" at the same company are different jobs.
**Suggestion:** Add a second dedup pass using Groq or embedding similarity. Before inserting, check if any existing job at the same company has a title similarity >0.85. Flag as "possible duplicate" rather than auto-deduping (let user decide).

### 7. Location Normalization
**Problem:** "NYC", "New York", "New York, NY", "New York City" are all different locations in the hash.
**Suggestion:** Build a simple alias map for common locations, or normalize via Groq before hashing. This prevents duplicate jobs from appearing just because sources format locations differently.

### 8. Remote Job Toggle (Not Always Filter)
**Problem:** Remote jobs are unconditionally filtered out in `_normalize_row()`.
**Suggestion:** Make remote filtering a user preference on the search config. Many users want remote jobs.

### 9. Watch Rule Improvements
**Problem:** Watch rules use simple substring matching. "company" type requires exact full-string match. No regex, no compound rules.
**Suggestion:**
- Make company matching substring-based (like keyword/sector)
- Add "title" rule type (separate from keyword which searches title, sector searches description)
- Add negative rules ("exclude company X", "exclude keyword Y")
- Add compound rules ("keyword X AND location Y")

### 10. Job Status Workflow
**Problem:** Status transitions (NEW → SAVED → APPLIED → etc.) have no timestamps, no notes.
**Suggestion:** Add `status_updated_at` and `status_notes` fields. Track when the user applied, interview dates, etc. This turns the app from a job finder into an application tracker.

---

## LOWER IMPACT — Polish & Completeness

### 11. Fix Profile Strength Meter
**Problem:** Hardcoded at 85%. Not dynamic.
**Suggestion:** Calculate based on filled fields: linkedin_url (+10), skills (+20), current_title (+15), target_title (+15), years_experience (+10), ai_recommendations generated (+15), linkedin_analysis done (+15).

### 12. Back Work History with a Model
**Problem:** Template has work history section but no DB model or CRUD.
**Suggestion:** Add `WorkExperience` model (company, title, start_date, end_date, description). Feed into Groq scoring for much better fit analysis.

### 13. Search History UI
**Problem:** SearchConfig records are persisted but there's no UI to browse or replay past searches.
**Suggestion:** Add a search history panel showing past configs with a "Re-run" button.

### 14. Score Caching
**Problem:** Clicking "Score" re-calls Groq every time. No caching.
**Suggestion:** Only re-score if profile or job description changed. Store `scored_at` timestamp and `profile_hash_at_scoring` to detect staleness.

### 15. Batch Scoring
**Problem:** Jobs are scored one at a time via button click.
**Suggestion:** Add "Score All Unscored" button that queues batch scoring as a background task (similar to scrape). Show progress via HTMX polling.

---

## Questions Needing User Input

1. **Remote jobs** — Do you want remote jobs included? Currently they're all filtered out.
2. **Application automation** — Would you want the app to help auto-apply (Easy Apply), or strictly discovery/tracking?
3. **Job age data** — Does JobSpy reliably return `date_posted` for your searches? This determines if timing features are feasible.
4. **Scrape frequency** — How often would you want automated scrapes? (Affects LinkedIn rate limiting)
5. **Additional job sites** — Are LinkedIn + Indeed + Glassdoor sufficient, or do you want to add others (ZipRecruiter, company career pages)?
6. **Notification channel** — Is in-app notification sufficient, or do you want email/desktop notifications?
