# Job Search Improvements

Recommendations to make search configs sharper and more focused, based on your profile (Team Lead/EM primary, Senior Dev secondary; Israel; fulltime; remote opt-in).

Companion doc: [linkedin-optimization-research.md](./linkedin-optimization-research.md)

---

## TL;DR — Priority Order

1. **Fix the `work_mode` bug** — field is collected but never sent to JobSpy ([scraper.py:121-130](../app/scraper.py)). Currently `is_remote=True` jobs are *dropped* ([scraper.py:28-30](../app/scraper.py)) even if user wanted them. This alone is the biggest win.
2. **Add `role_level` field** — team lead / manager / senior IC is your core filter. Today "experience_level" conflates seniority with role family.
3. **Switch country to Israel** — `country_indeed="israel"` is supported (verified in JobSpy v1.1.82). Currently hardcoded `"USA"`.
4. **Add `hours_old` filter** — from the optimization research, "apply within 24-48h" is the single highest-leverage timing factor. JobSpy supports it natively.
5. **Add exclusion keywords + company blocklist** — kills noise before AI scoring burns Groq tokens on junk.
6. **Add remote opt-in toggle** — now that (1) is fixed, expose `include_remote` defaulting to false.

Everything below is additive. Steps 1-4 are the sharp edge.

---

## Schema Changes (`SearchConfig` model)

Current fields ([models.py:90-100](../app/models.py)):
`keywords, location, experience_level, work_mode, is_active, created_at`

### Add these columns

| Field | Type | Values / Example | Why |
|-------|------|------------------|-----|
| `role_level` | String | `ic_senior`, `team_lead`, `engineering_manager`, `director`, `vp` | Your primary dimension. Team lead vs senior IC have different titles and the JD reads differently — needs its own axis, not folded into "experience_level". |
| `include_remote` | Bool | default `False` | Opt-in per your answer. When False, filter `is_remote=True` out (current behavior). When True, pass `is_remote=True` *and* keep on-site/hybrid — i.e., don't exclude. |
| `country` | String | default `"israel"` | Replaces hardcoded USA. Lets future-you add a second config without code changes. |
| `max_age_hours` | Int | default `72`, nullable | Maps to JobSpy `hours_old`. "Apply Soon" threshold from optimization research. Set to 168 (7 days) if you want a wider net. |
| `exclude_keywords` | String (CSV) | `"crypto, gambling, junior, unpaid"` | Drop jobs whose title/description matches any term. Run pre-AI to save tokens. |
| `blocked_companies` | String (CSV) | `"OutbrainTaboola, FooCo"` | Hard filter on `Job.company`. Probably graduates into its own table later but CSV is fine for POC. |
| `results_wanted` | Int | default `50` | Already hardcoded; expose it. LinkedIn cap ~250/IP noted in CLAUDE.md. |
| `min_salary` | Int | nullable | Optional floor. JobSpy doesn't filter by salary natively, so this is a post-scrape filter against `Job.min_amount`. |

### Field you *don't* need to add

- **`job_type`** — you said fulltime only. Keep it hardcoded to `FULL_TIME` (current behavior is correct, just make it a constant with a comment instead of a magic string).
- **`sites`** — LinkedIn/Indeed/Glassdoor is fine. Glassdoor is weak in Israel but harmless to keep.

---

## Role-Level → Search Term Mapping

The LinkedIn algorithm weights *job title* above everything else (see optimization research §"Recruiter Behavior"). So `role_level` should actively reshape the `search_term` passed to JobSpy, not just post-filter.

Suggested mapping (build a helper in `scraper.py`):

```python
ROLE_LEVEL_TERMS = {
    "team_lead":            ["team lead", "tech lead", "engineering lead"],
    "engineering_manager":  ["engineering manager", "software engineering manager", "R&D manager"],
    "director":             ["director of engineering", "head of engineering"],
    "vp":                   ["vp engineering", "vp r&d"],
    "ic_senior":            ["senior software engineer", "senior backend", "staff engineer"],
}
```

**Strategy:** if `role_level` is set, run one `scrape_jobs()` call per title variant and dedupe (you already have dedup by `url_hash`). This gives the recruiter-search-style title boost without needing LinkedIn Boolean.

**Two active configs = your two tracks.** Create one config for `team_lead`/`engineering_manager` and one for `ic_senior`. `list_search_configs(active_only=True)` already iterates them. No multi-persona infra needed.

---

## JobSpy Parameter Wiring

Update the call at [scraper.py:121-130](../app/scraper.py):

```python
scrape_jobs(
    site_name=["linkedin", "indeed", "glassdoor"],
    search_term=build_search_term(config),      # role_level + keywords
    location=config.location or "Israel",
    country_indeed=config.country or "israel",  # was "USA"
    job_type="fulltime",
    is_remote=True if config.include_remote else None,  # None = no filter
    hours_old=config.max_age_hours,              # NEW
    results_wanted=config.results_wanted or 50,
    linkedin_fetch_description=True,
)
```

Then fix the post-scrape remote filter at [scraper.py:28-30](../app/scraper.py):

```python
# Before: always drops remote jobs
# After: only drop remote if user didn't opt in
if not config.include_remote:
    df = df[df["is_remote"] != True]
```

---

## Post-Scrape Filters (before AI scoring)

Run these in order to minimize Groq spend — AI fit scoring is the most expensive step per job.

1. **Blocked companies** — `df = df[~df["company"].isin(blocked_companies)]`
2. **Exclude keywords** — regex OR across title + description
3. **Min salary** — `df = df[df["min_amount"].fillna(0) >= min_salary]` (only if set; don't drop nulls when unset)
4. **Dedup** (existing)
5. **AI fit scoring** (existing)

---

## UI Changes ([templates/search_config.html](../app/templates/search_config.html))

Add to the form (keep the existing grid layout):

- **Role level** — select: `Team Lead`, `Engineering Manager`, `Senior IC`, `Director`, `VP`. Required.
- **Country** — select with Israel default, USA as second option. Small dropdown, not a text input.
- **Max posting age** — select: `24h`, `48h`, `72h` (default), `7 days`, `Any`. Label each with a color hint (Fresh / Apply Soon / Late) that matches the badges from the optimization research idea #1.
- **Include remote** — checkbox, unchecked by default. Help text: *"By default, only on-site and hybrid roles in your location are shown."*
- **Exclude keywords** — textarea, comma-separated. Placeholder: *"crypto, gambling, junior"*.
- **Blocked companies** — textarea, comma-separated. Placeholder: *"CompanyA, CompanyB"*.
- **Min salary (₪)** — optional number. Note: Israeli LinkedIn postings rarely include salary, so expect most rows to be null.

Deprecate or repurpose **`experience_level`**: either drop it or narrow it to apply only when `role_level=ic_senior` (where "senior/staff/principal" is meaningful). For team lead/EM tracks it's noise.

---

## AI Scoring Impact

`groq_service.py` fit scoring already uses `profile.target_title` ([groq_service.py:213-281](../app/services/groq_service.py)). Two tweaks:

1. **Pass the active search config's `role_level`** into the prompt so the model knows which track it's scoring against. A job scored against "team lead" should penalize pure IC roles and vice versa — right now it can't distinguish.
2. **Profile should have `target_titles: list`** not a single title, since you have two tracks. Or: score the job against each active config and store the best fit + which config won. This graduates into a `Job.matched_config_id` column later.

Flagging now because skipping this means the AI will give you mushy scores when both configs are active.

---

## Out of Scope (from research, parked for later)

- **StaffSpy for hiring-manager discovery** — compelling but adds a new dependency and a new scraping surface. Revisit after search is tight.
- **Keyword gap analysis** (research idea #2) — great feature but profile-side, not search-side. Separate phase.
- **Structured JD extraction** — already partially implemented in `intelligence_json` ([groq_service.py:389-427](../app/services/groq_service.py)). Could be extended with `seniority_level` and `remote_policy` as first-class columns if you want to filter on them in the UI.
- **Auto-apply (AIHawk)** — explicitly out per the "high risk of account restrictions" note, and you have no Easy Apply dependency yet.

---

## Suggested Phase Breakdown

If you turn this into GSD phases, natural split:

- **Phase A — Search config v2** (schema + UI + scraper wiring): fields 1-6 above, fix the `work_mode` bug, Israel default. Single migration.
- **Phase B — Filter pipeline**: exclude keywords, blocked companies, min salary, `hours_old`. All post-scrape except `hours_old`.
- **Phase C — Role-aware scoring**: pass `role_level` into Groq prompt, multi-target profile. Touches AI layer.

Phase A alone will materially improve signal quality. B and C are force multipliers.
