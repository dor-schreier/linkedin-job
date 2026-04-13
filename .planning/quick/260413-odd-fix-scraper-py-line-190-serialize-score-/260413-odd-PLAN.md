# Quick Task 260413-odd: Fix score_breakdown_json serialization

**Date:** 2026-04-13
**Status:** Executed

## Task

`score_breakdown_json` is a `TEXT` column in SQLite but was being assigned a raw `dict`, causing a `sqlite3.ProgrammingError` on flush.

## Changes

1. Add `import json` to `app/scraper.py`
2. Replace `created.score_breakdown_json = score_result` with `created.score_breakdown_json = json.dumps(score_result)`
