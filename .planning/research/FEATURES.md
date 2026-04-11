# Feature Research

**Domain:** Personal job finder / tracker web app
**Researched:** 2026-04-11
**Overall confidence:** HIGH (multiple independent sources confirm patterns)

---

## Table Stakes

Features that users expect. Missing any of these makes the app feel broken or incomplete.

| Feature | Description | Complexity |
|---------|-------------|------------|
| Keyword + location search | Text field for job title / keywords, location field with remote toggle. Universal across all job boards. | Low |
| Job type filter | Full-time / Part-time / Contract / Internship. Standard on every job board. | Low |
| Remote / on-site / hybrid filter | Separate from location. Users filter by work arrangement independently of geography. | Low |
| Experience level filter | Entry / Mid / Senior. Standard on LinkedIn, Indeed, Glassdoor. | Low |
| Job results list | Paginated or scrollable list showing title, company, location, salary range (if available), source site, posted date. | Low |
| Job detail view | Full job description, salary, company, direct apply URL. Users need the full description to evaluate a role. | Low |
| Source site indicator | Show which site(s) the job came from (LinkedIn / Indeed / Glassdoor). Multi-source aggregation requires this for trust. | Low |
| Deduplication across sources | Same job posted on multiple boards shown once. Without this, results feel noisy and unprofessional. Implement as: normalize title+company+location into a hash; fall back to job_url matching. JobSpy returns `job_url` per source — hash `(title.lower().strip(), company.lower().strip(), city.lower())` as the dedup key. | Medium |
| Application status tracking | Per-job status: Saved / Applied / Interviewing / Offer / Rejected. The canonical pipeline for job trackers (Teal, Simplify, Kula all use this exact set). | Low |
| Notes per job | Free-text notes field on each job card. Users record interview dates, contacts, impressions. | Low |
| AI fit score | 0–100 numeric score per job, with label bucket (Poor 0–39 / Fair 40–59 / Good 60–74 / Excellent 75–100). 0–100 is the dominant design pattern (JobQuest, OwlApply, Teal, Resumly all use it). Show alongside job title in list view. | Medium |
| AI job summary | 3–5 sentence plain-language summary of the job: role focus, key requirements, why it matches or doesn't match the user's profile. Generated from job description + user profile. Replaces need to read full JD to decide if worth applying. | Medium |
| User profile input | Manual skills + experience text fields. LinkedIn URL as optional supplement (scraping LinkedIn profile is out of scope for POC — store URL as reference only). Required to generate meaningful fit scores. | Low |
| Watch rules / alerts | User defines rules: company name, role keyword, or sector. New scraped jobs matching a rule are flagged with a visual highlight (badge/color) in-app. No email/push for POC. | Medium |
| In-app notification badge | Unread count of newly flagged jobs matching watch rules. Users need to know something new matched without re-scanning results. | Low |
| Filter scraped results | Post-scrape filters: status, fit score range, source site, watched flag. Users need to slice results after they're in the app. | Low |

---

## Differentiators

Features not universally expected, but provide competitive advantage or high value for this specific use case.

| Feature | Description | Complexity |
|---------|-------------|------------|
| AI profile improvement suggestions | Groq analyzes the user's profile and suggests improvements (missing skills, weak descriptions). Already in PROJECT.md. Teal does keyword matching but not free-form profile coaching. | Medium |
| Fit score gap analysis | Alongside the score, show which specific skills/keywords the job requires that the user's profile lacks. Makes scores actionable rather than just numeric. Pattern from JobQuest, Teal keyword matching. | Medium |
| Multi-source score breakdown | Show which source(s) a deduplicated job came from, and surface the "best" URL (prefer direct apply link over aggregator). Reduces friction to applying. | Low |
| Salary range display and filter | JobSpy returns `min_amount` / `max_amount` / `interval`. Surface salary range prominently and allow filtering. Many listings don't have salary — handle gracefully. | Low |
| Scrape history / last-scraped timestamp | Show when results were last refreshed per search config. Users need to know result freshness without re-running scrapes. | Low |
| Watch rule match explanation | When a job is flagged by a watch rule, show which rule matched and why (e.g., "Matched: company = Stripe"). Transparency builds trust in the alert system. | Low |
| Sort by fit score | Default sort by AI fit score descending. Users should see best-matched jobs first. Requires scores to exist before sorting — batch-score after scrape. | Low |
| Search config persistence | Save multiple named search configurations (e.g., "Senior backend roles NYC" vs "Remote ML roles"). Allows reuse without re-entering filters. | Medium |

---

## Anti-Features (Defer)

Things to deliberately NOT build for the POC. Each has a clear reason why it adds cost disproportionate to value at this stage.

| Feature | Why Defer |
|---------|-----------|
| Email / push notifications | PROJECT.md explicitly out of scope. Adds infrastructure (SMTP, push service) with no POC benefit. In-app highlight is sufficient. |
| Auto-apply / one-click apply | Out of scope per PROJECT.md. Requires form-filling automation, CAPTCHA handling, and per-site integrations — a separate product entirely. |
| Resume file upload / parsing | Out of scope per PROJECT.md. PDF/DOCX parsing (PyMuPDF, docx2txt) adds complexity with marginal benefit over manual text input for a single user. |
| Kanban / drag-drop pipeline board | Teal's pipeline board is the pattern competitors use, but it's UI-heavy to implement. A status dropdown on each job row achieves the same outcome for a POC. Defer visual kanban. |
| Browser extension (save from job boards) | Teal's Chrome extension is a major retention driver for them. Not needed here because JobSpy does the scraping automatically — saving from external sites is redundant. |
| Multi-user / auth | Out of scope per PROJECT.md. Personal use only. |
| Proxy rotation for LinkedIn | Out of scope per PROJECT.md. ~250 jobs per IP is acceptable. |
| Analytics dashboard (application funnel) | Interesting but requires meaningful volume of applications tracked over time. Add after the tracker itself has been used. |
| Interview prep / AI coaching | Adjacent product. Not core to finding + scoring jobs. |
| Company research / Glassdoor rating integration | Nice-to-have context, but adds API dependency and scope without improving the core scrape-rank-alert loop. |
| Calendar integration (interview scheduling) | Requires OAuth with Google/Outlook. Out of scope for POC. |
| Boolean search operators | LinkedIn alerts support AND/OR syntax. JobSpy passes keywords as simple strings to each site's native search — advanced boolean is per-site and unreliable. |

---

## Dependencies

Feature dependency graph — build in this order to avoid blocking:

```
User Profile Input
  └─> AI Fit Score (requires profile to compare against)
        └─> Fit Score Gap Analysis (requires score calculation)
        └─> Sort by Fit Score (requires scores to exist)
  └─> AI Profile Improvement Suggestions (requires profile)

Scrape (JobSpy)
  └─> Deduplication (must run before storing results)
        └─> Job Results List (displays deduplicated set)
              └─> Job Detail View (requires a job to exist)
              └─> Application Status Tracking (per-job, requires jobs to exist)
              └─> Notes Per Job (per-job, requires jobs to exist)
              └─> AI Fit Score (per-job, requires jobs to exist)
              └─> AI Job Summary (per-job, requires jobs to exist)

Search Config
  └─> Scrape (feeds keywords/location/filters to JobSpy)
  └─> Search Config Persistence (wraps config saving around existing config fields)

Watch Rules
  └─> Scrape (watch rules evaluated against new results post-scrape)
        └─> In-App Notification Badge (derived from watch rule matches)
        └─> Watch Rule Match Explanation (annotates matched jobs)
```

**Critical path for MVP:**
Search Config → Scrape → Deduplication → User Profile → AI Fit Score → Job Results List with status tracking

**Can be built in parallel once jobs exist:**
- Notes, Status, Watch Rules (all per-job, no inter-dependency)
- AI Job Summary and AI Fit Score can share a single Groq prompt call per job

**Groq API batching note:** AI Fit Score and AI Job Summary should be generated in a single prompt per job to minimize API calls. Both require the same inputs (job description + user profile).

---

## Deduplication Implementation Note

JobSpy does not deduplicate across sources natively. Recommended approach for this app:

1. **Primary key:** Normalize `(title, company, city)` — lowercase, strip whitespace, strip punctuation — then SHA-256 hash as the internal job ID.
2. **Fallback:** If `job_url` contains a canonical job ID (e.g., LinkedIn job IDs in URL path), extract and use directly.
3. **Merge strategy:** When a duplicate is detected, retain all source URLs (store as a list), keep the record with the most complete salary/description data, and note all source sites.
4. **Fuzzy dedup is overkill for POC:** Title+company exact-normalized match catches >90% of true duplicates across boards (Textkernel research confirms near-duplicates are common but exact-normalized matches are the most reliable signal for same-role detection). Semantic dedup (MinHash/LLM) adds complexity for marginal gain at personal-use scale.

---

## AI Fit Score Design Note

Use a **0–100 integer** with label buckets. This is the dominant pattern across JobQuest, OwlApply, Teal, Resumly, and Elasticsearch resume-matching research:

| Score | Label | Meaning |
|-------|-------|---------|
| 75–100 | Excellent | Strong match, apply now |
| 60–74 | Good | Solid match, worth applying |
| 40–59 | Fair | Partial match, gap exists |
| 0–39 | Poor | Weak match |

Groq prompt should return a structured JSON response with: `score` (int), `label` (str), `summary` (str, 3–5 sentences), `missing_skills` (list of str). Parse and store all four fields — they feed both the score display and the gap analysis differentiator.

Expect ±5 point variance across identical calls (LLM non-determinism). This is acceptable at POC scale — don't over-engineer score normalization.

---

## Watch Rules Design Note

Pattern modeled on LinkedIn Alerts and Indeed Alerts (both use keyword + boolean logic):

- Rule types: **Company name exact match**, **Role keyword contains**, **Sector/industry tag match**
- Evaluation: Run rules against each new job after deduplication on every scrape
- Match action: Tag job with `watched: true`, increment unread notification counter
- UI: Highlight matched jobs with a distinct badge/color in the results list; bell icon with unread count in nav

Multiple rules should OR together (a job matching any rule is flagged). Keep rules simple for POC — no AND/NOT boolean chaining within a rule.

---

## Sources

- [Best Free Job Tracker Apps 2026 — ApplyArc](https://applyarc.com/blog/best-free-job-tracker-apps-2026)
- [Teal Job Tracker — Features Overview](https://www.tealhq.com/tools/job-tracker)
- [Teal HQ Review 2026 — ResumeHog](https://resumehog.com/blog/posts/teal-hq-review-2026-is-this-job-search-tool-worth-it.html)
- [What's your Job Match Score? — JobQuest](https://jobquest.ai/blog/whats-a-job-match-score-and-why-it-matters/)
- [AI Job Match Score — OwlApply](https://owlapply.com/en/ai-tools/job-match-score)
- [How to Detect Non-Exact Duplicates in Job Postings — Textkernel](https://www.textkernel.com/learn-support/blog/online-job-postings-have-many-duplicates-but-how-can-you-detect-them-if-they-are-not-exact-copies-of-each-other/)
- [JobSpy GitHub — speedyapply/JobSpy](https://github.com/speedyapply/JobSpy)
- [python-jobspy — PyPI](https://pypi.org/project/python-jobspy/)
- [How Job Alerts Work in Job Boardly](https://www.jobboardly.com/blog/how-job-alerts-work-in-job-boardly)
- [LinkedIn Job Alerts — LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a511279)
- [Assess Job Fit Accuracy with AI Predictions — Resumly](https://www.resumly.ai/blog/how-to-assess-job-fit-accuracy-with-ai-predictions)
- [Match Resumes to Jobs with LLM — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/openwebcrawler-llms-semantic-text-resume-job-search)
