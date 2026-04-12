---
status: partial
phase: 05-watch-rules-notifications
source: [05-VERIFICATION.md]
started: 2026-04-12T00:00:00Z
updated: 2026-04-12T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-end badge flow
expected: Create a keyword rule (e.g. "Python"), run a scrape — badge with unread count appears in nav on all pages

result: [pending]

### 2. Badge reset to 0
expected: Visit /watch-matches, then load any other page — badge is gone (unread_count = 0)

result: [pending]

### 3. Delete rule via UI
expected: Click Delete on a watch rule, confirm 303 redirect removes the rule from the list

result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
