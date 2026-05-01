# Fuzzy Multi-Filter Rules

## Goal
Add a stackable text-rule filter system to the Jobs page so users can compose multiple include/exclude fuzzy-text rules (e.g., include "lead", exclude "frontend", exclude "senior") and only see jobs matching ALL rules. Operates client-side alongside the existing global `q` search.

## Context
- Jobs page lives in `app/templates/jobs.html` and renders cards via `app/templates/partials/job_list.html`.
- Fuse.js is already loaded (`jobs.html:9`) and currently powers the global search input (`jobs.html:508-547`) over `data-title`, `data-company`, `data-location`.
- Card markup (`partials/job_list.html:4-8`) exposes `data-title`, `data-company`, `data-location`. Other fields (description, tech, summary) are rendered as text inside the card but not as data attributes.
- The existing `q` search remains untouched and continues to filter the same way it does today. The new rules system is additive and runs as a second pass on top of `q` results.
- Persistence is in-memory only for the session — no localStorage, no URL params, no server-side storage.
- All filtering is client-side; only currently-loaded cards are filtered (consistent with existing `q` behavior).

## Tasks

### Phase 1: Card data exposure
- [x] In `partials/job_list.html`, add a `data-filter-text` attribute on the job card root (`job-card-{{ job.id }}`) containing a single concatenated lowercase string of: title, company, location, source, summary fields (`summary_general_description`, `summary_experience_needed`), tech stack, qualifications, and `fit_summary`. This is the haystack rules will match against.

### Phase 2: Rule UI
- [x] In `jobs.html`, add a "Rules" section directly under the existing filter bar (after the form ending around line 332). Include:
  - A header row with label "Rules" and an "Add rule" button.
  - A container `#filter-rules-list` that holds rule rows (initially empty).
  - Each rule row contains: an include/exclude toggle (segmented control or select), a text input for the term, a remove (×) button.
  - A small helper line: "Showing jobs matching ALL rules. Fuzzy match — typos OK."
- [x] Style consistent with existing filter bar (Tailwind tokens already in the template: `surface-container-low`, `outline-variant/40`, etc.).

### Phase 3: Rule engine
- [x] Add a script block at the bottom of `jobs.html` (near the existing fuzzy-search block) that:
  - Maintains an in-memory array of rules `[{ mode: 'include'|'exclude', term: string }, ...]`.
  - Builds a Fuse index over cards using `data-filter-text` (single key, threshold ~0.35, `minMatchCharLength: 2`). Rebuild on `htmx:afterSwap`.
  - On rule add/edit/remove (debounced ~150ms on text input), recomputes visibility: a card is shown iff every include rule matches it AND no exclude rule matches it. Empty-term rules are ignored.
  - Composes correctly with the existing `q` search: a card is visible only if BOTH the `q` filter and the rules pass. Refactor the existing `applyFilter` so both passes share visibility state (e.g., a single `applyAllFilters()` that re-evaluates from scratch using current `q` + rules).
- [x] Update the `#filtered-job-count` display to reflect the post-rules visible count (currently it shows server `total`).

### Phase 4: Polish
- [x] When a rule's text input is empty, treat the rule as inactive (don't filter on it) but keep the row visible so the user can type into it.
- [x] Show a small badge near the "Rules" header with the count of active (non-empty) rules, mirroring the existing `#active-filter-count` pattern.
- [x] Pressing Enter inside a rule input should not submit the surrounding form (the rules block lives outside the existing `#jobs-filter-form`, so verify this).

## Acceptance criteria
- [ ] User can click "Add rule" and a new rule row appears with mode toggle, text input, remove button.
- [ ] User can add 3+ rules and each is independently editable.
- [ ] Typing "lead" in an include rule hides cards whose `data-filter-text` doesn't fuzzy-match "lead".
- [ ] Adding an exclude rule "frontend" further hides any remaining card matching "frontend".
- [ ] Removing a rule re-shows the cards it was hiding (assuming no other rule excludes them).
- [ ] The global `q` search continues to work and combines with rules (intersection).
- [ ] Reloading the page clears all rules (session-only).
- [ ] The visible job count updates as rules change.

## Verification
1. Start the app and open `/jobs` with at least ~20 jobs loaded.
2. Add an include rule "lead" — confirm only jobs whose title/description fuzzy-match "lead" remain.
3. Add an exclude rule "frontend" — confirm any frontend-matching job disappears.
4. Add an exclude rule "senior" — confirm seniors disappear too.
5. Remove the "frontend" rule — confirm those cards return (unless excluded by another rule).
6. Type in the global search box at the top — confirm rules + search compose (intersection).
7. Reload the page — confirm rules are cleared.
8. Check the visible count badge matches the number of rendered (non-hidden) cards.
