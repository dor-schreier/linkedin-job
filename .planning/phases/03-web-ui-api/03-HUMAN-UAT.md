---
status: partial
phase: 03-web-ui-api
source: [03-VERIFICATION.md]
started: 2026-04-12T00:00:00Z
updated: 2026-04-12T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Jobs list page renders
expected: http://localhost:8000/jobs shows nav bar, filter bar, and job cards (or empty state "No jobs found")
result: [pending]

### 2. HTMX partial update works
expected: Changing the Status filter dropdown updates only #job-list — no full page reload (network tab shows request to /jobs with HX-Request header)
result: [pending]

### 3. Silent status POST persists
expected: Changing a job's status dropdown sends hx-post silently; refreshing the page shows the new status pre-selected
result: [pending]

### 4. Nav active state is correct
expected: Current page nav link is blue-underlined; other nav links are gray — works for /jobs, /profile, /watch-rules, /search-config
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
