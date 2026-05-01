# Spec: Restrict Filter Dropdowns to Active Jobs Only

## Goal

All dropdown filter values on the Jobs page must reflect only jobs where `is_active = True`. Inactive jobs (e.g., expired, rejected, or manually deactivated) should not contribute values to any filter dropdown.

## Current State

| Filter Dropdown | Repository Method | is_active Filtered? |
|---|---|---|
| Location | `get_distinct_locations()` | Yes (already done) |
| Company | `get_distinct_companies()` | No |
| Source | `get_distinct_sources()` | No |
| Sector | `get_distinct_sectors()` | No |
| Company Type | `get_distinct_company_types()` | No |
| Status | Hardcoded enum values | N/A |
| Sort / Salary / Fresh / Hide Rated / Show Inactive | Hardcoded options | N/A |

## Required Changes

### `app/repository.py`

Apply `Job.is_active == True` to each of the four methods below, matching the pattern already used in `get_distinct_locations()`.

---

**`get_distinct_companies()`** (currently ~line 164)

Add filter:
```python
Job.is_active == True
```

Result:
```python
def get_distinct_companies(self) -> list[str]:
    rows = (
        self.session.query(Job.company)
        .filter(
            Job.company.isnot(None),
            Job.company != "",
            Job.is_active == True,
        )
        .distinct()
        .order_by(Job.company)
        .all()
    )
    return [r[0] for r in rows]
```

---

**`get_distinct_sources()`** (currently ~line 154)

Add filter:
```python
Job.is_active == True
```

Result:
```python
def get_distinct_sources(self) -> list[str]:
    rows = (
        self.session.query(Job.source)
        .filter(
            Job.source.isnot(None),
            Job.source != "",
            Job.is_active == True,
        )
        .distinct()
        .order_by(Job.source)
        .all()
    )
    return [r[0] for r in rows]
```

---

**`get_distinct_sectors()`** (currently ~line 174)

This queries `Company.sector`. Join to `Job` so the `is_active` filter can be applied.

Result:
```python
def get_distinct_sectors(self) -> list[str]:
    rows = (
        self.session.query(Company.sector)
        .join(Job, Job.company == Company.name)
        .filter(
            Company.sector.isnot(None),
            Company.sector != "",
            Job.is_active == True,
        )
        .distinct()
        .order_by(Company.sector)
        .all()
    )
    return [r[0] for r in rows]
```

> Note: Verify the join condition (`Job.company == Company.name`) matches the actual FK/relationship in `models.py`. Adjust if the join uses a different key.

---

**`get_distinct_company_types()`** (currently ~line 184)

Same as sectors — join to `Job`.

Result:
```python
def get_distinct_company_types(self) -> list[str]:
    rows = (
        self.session.query(Company.company_type)
        .join(Job, Job.company == Company.name)
        .filter(
            Company.company_type.isnot(None),
            Company.company_type != "",
            Job.is_active == True,
        )
        .distinct()
        .order_by(Company.company_type)
        .all()
    )
    return [r[0] for r in rows]
```

---

### No Template Changes Required

The template (`app/templates/jobs.html`) passes filter values directly from the repo methods into the dropdowns. Fixing the repo methods is sufficient — no Jinja2 changes needed.

### No Route Changes Required

The route (`app/routes/jobs.py`) calls the repo methods and passes the results to the template unchanged. No changes needed there either.

## Acceptance Criteria

1. A job with `is_active = False` does not cause its company name to appear in the Company dropdown.
2. A job with `is_active = False` does not cause its source to appear in the Source dropdown.
3. A sector only appears in the Sector dropdown if at least one active job (`is_active = True`) belongs to a company in that sector.
4. A company type only appears in the Company Type dropdown if at least one active job belongs to a company of that type.
5. The Location dropdown continues to behave as before (already filtered).
6. Selecting a filter value and applying it still returns correct results — no regressions in the main job list query.
