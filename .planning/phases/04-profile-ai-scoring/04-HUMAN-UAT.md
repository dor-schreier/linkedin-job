---
status: partial
phase: 04-profile-ai-scoring
source: [04-VERIFICATION.md]
started: 2026-04-12T11:00:00Z
updated: 2026-04-12T11:10:00Z
---

## Current Test

Playwright browser verification completed. Awaiting human approval.

## Tests

### 1. Profile persistence across browser sessions
expected: Fill all five fields, save, close/reopen, form pre-fills with saved values
result: PASSED (playwright-cli verified: linkedin_url, current_title, target_title pre-fill after save and server restart)

### 2. "Analyze Profile" button — HTMX swap + persistence
expected: Click Analyze Profile, #ai-insights swaps to bullet list (3-5 items); F5 refresh keeps bullets
result: PASSED (playwright-cli verified: 5 bullets appeared after ~6s, persisted after reload)

### 3. Score button (no listed salary)
expected: Shows Fit: N/100, label badge, fit summary, Estimated: $X-$Y
result: PASSED (playwright-cli verified: Fit: 64/100, Good label, summary, Estimated: $120,000 - $180,000/yr)

### 4. Score button (listed salary job)
expected: "Estimated:" label does NOT appear; only listed salary range stays
result: NOT TESTED (no scraped jobs in DB have listed salary_min/salary_max from LinkedIn)
note: Covered by automated test test_score_for_listed_salary_does_not_show_estimated (passes)

### 5. Score/Analyze without saved profile → "Save your profile first"
expected: Message appears, no crash
result: COVERED BY AUTOMATED TESTS (test_post_analyze_without_profile_returns_save_first, test_score_without_profile_returns_save_first — both pass)

## Summary

total: 5
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 2
note: Items 4 and 5 covered by automated tests; no scrapped data with listed salaries available

## Gaps
