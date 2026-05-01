# Job Post Statuses and States

## `status` — Application Pipeline (JobStatus enum, manual)

| Value | Meaning |
|---|---|
| `new` | Default on scrape — not yet reviewed |
| `saved` | Bookmarked for later |
| `applied` | Application submitted |
| `interviewing` | In an interview process |
| `offer` | Received an offer |
| `rejected` | Rejected or withdrew |

## `is_rejected` — Auto-Reject Flag (Boolean, system-set)

Set by the reject-rules engine or manually. Independent of `status`.
- `False` (default) — passes all reject rules
- `True` — filtered out by a rule or manually rejected

A job can be `is_rejected=True` with `status=new` if rules ran before you reviewed it.

## `is_active` — Listing Liveness (Boolean, system-checked)

- `True` (default) — posting still live externally
- `False` — posting found closed/removed during liveness check

## `ScrapeLog.status` — Scrape Run State (String, system)

| Value | Meaning |
|---|---|
| `running` | Scrape in progress |
| `success` | Completed successfully |
| `error` | Failed (see `error` column) |

## Key Distinctions

- `status` = where *you* are in the hiring funnel (manual)
- `is_rejected` = whether the *system* filtered it via rules (automatic)
- `is_active` = whether the *job posting* is still live externally

A job can simultaneously have `status=new`, `is_rejected=True`, `is_active=False`.
