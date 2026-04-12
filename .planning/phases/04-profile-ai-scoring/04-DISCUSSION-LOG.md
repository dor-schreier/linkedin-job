# Phase 4: Profile + AI Scoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 04-profile-ai-scoring
**Areas discussed:** Profile Improvement Recommendations

---

## Profile Improvement Recommendations

| Option | Description | Selected |
|--------|-------------|----------|
| On save | Auto-generate on every profile save | |
| Manual button | Separate "Analyze Profile" button after saving | ✓ |
| On first save only | Generate once, refresh on demand | |

**User's choice:** Manual button

---

| Option | Description | Selected |
|--------|-------------|----------|
| Below the form | Render in a card directly below the profile form | |
| Inline after button click | HTMX swap next to the Analyze button | |
| Separate section/tab | Distinct "AI Insights" section on profile page | ✓ |

**User's choice:** Separate section/tab

---

| Option | Description | Selected |
|--------|-------------|----------|
| Bullet list | 3–5 concise actionable bullet points | ✓ |
| Free-form paragraph | Short narrative paragraph | |
| Structured (strength + gaps) | Two-section format: strengths and gaps | |

**User's choice:** Bullet list

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, persist to DB | Save last recommendations; visible on every visit | ✓ |
| No, in-memory only | Shown once after Analyze, cleared on refresh | |

**User's choice:** Yes, persist to DB

---

## Claude's Discretion

- Scoring trigger UX
- Groq prompt design and data sent
- Salary estimation trigger
- DB column for persisting recommendations
- Fit score label thresholds
- HTMX swap strategy

## Deferred Ideas

None.
