# User Decisions (2026-04-12)

1. **Remote jobs**: No — keep filtering out remote jobs
2. **Scope**: Discovery & tracking only — no auto-apply features
3. **Scrape frequency**: At least daily, wants more than 50 results per scrape
4. **Notifications**: In-app sufficient for now

## Result Volume Strategy

Current limit: `RESULTS_WANTED = 50` in `scraper.py`. LinkedIn caps at ~250/search/IP.

Options to increase volume:
- Raise `RESULTS_WANTED` to 150-200 per search
- Run multiple active SearchConfigs per scrape cycle (already supported by model)
- Stagger keyword variations (e.g., "python developer" + "python engineer" + "backend developer")
- Dedup handles overlap across configs automatically via job_hash
