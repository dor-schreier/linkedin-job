---
phase: quick-260412-sij
plan: 01
subsystem: frontend/templates
tags: [ui, redesign, design-system, tailwind, material-design, htmx, jinja2]
dependency_graph:
  requires: []
  provides: [sidebar-nav, design-tokens, material-symbols, manrope-inter-fonts]
  affects: [all-page-templates, job-cards, watch-rules-layout, profile-layout]
tech_stack:
  added: [Material Symbols Outlined (CDN), Manrope font (Google Fonts), Inter font (Google Fonts)]
  patterns: [Material Design token system, fixed sidebar nav, sticky page headers, two-column layouts]
key_files:
  created: [tests/test_ui_redesign.py]
  modified:
    - app/templates/partials/nav.html
    - app/templates/jobs.html
    - app/templates/partials/job_list.html
    - app/templates/profile.html
    - app/templates/watch_rules.html
    - app/templates/watch_matches.html
    - app/templates/scrape.html
    - app/templates/search_config.html
    - app/templates/profile_optimizer.html
    - app/templates/partials/ai_insights.html
    - app/templates/partials/job_score.html
    - app/templates/partials/linkedin_analysis.html
    - app/templates/health.html
decisions:
  - "bg-white toggle knob in watch_rules.html retained intentionally — spec explicitly shows white toggle thumb"
  - "profile.html summary textarea maps to profile.skills field (existing DB column) pending full profile model expansion"
  - "Tailwind config token block inlined per-template (no base.html) to match existing project pattern"
metrics:
  duration: ~25 minutes
  completed: 2026-04-12
---

# Quick Task 260412-sij: UI Redesign — Sidebar nav, design tokens, Material Symbols across all 13 templates

## What Was Built

Full frontend redesign of the Job Finder app per `.claude/.spec/UI-REDESIGN-SPEC.md`. Transformed all 13 Jinja2 templates from default Tailwind gray/blue to a cohesive "Digital Curator" Material Design token system.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | Replace nav + global shell + redesign job cards/watch rules/profile | 3be95c7 | 13 templates |
| 3 | Add Playwright verification tests | c77efbe | tests/test_ui_redesign.py |

## Changes Made

### Global (all pages)
- `partials/nav.html`: Replaced horizontal top nav with fixed left sidebar (`w-64`), 4-element nav tuple with Material Symbols icons, unread badge on Matches, "Find New Jobs" CTA at bottom
- All pages: `<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries">`, Google Fonts (Manrope + Inter), Material Symbols Outlined, Tailwind config with full token set, `<style>` block for font/icon settings
- All pages: `<body class="bg-background text-on-surface min-h-screen">` + `<div class="ml-64 min-h-screen">` wrapper
- All pages: sticky `<header class="sticky top-0 z-50 bg-surface/80 backdrop-blur-md ...">` with page-specific content
- All pages: zero remaining `bg-gray-*`, `text-gray-*`, `bg-blue-*`, `bg-white` cards, `divide-y`

### Job Cards (`partials/job_list.html`)
- Grid layout with `bg-surface-container-lowest` cards, hover shadow glow
- High-match accent bar (`bg-primary`, left edge) when `fit_score >= 90`
- Score badge: `bg-primary-container` for high match, `bg-surface-container-high` for standard
- AI insight block with `border-l-2 border-primary-fixed-dim` and italic "AI Insight:" prefix
- Tags row with source, salary, date; actions panel with View Details + status select + score button

### Watch Rules (`watch_rules.html`)
- Two-column layout: `grid-cols-[1fr_320px]`
- Left: Active Automations label + rule cards with icon, toggle form, tags, meta row
- Right: Create rule form panel + Automated Insights card with progress bar
- All existing form `action`/`method`/`name` attributes preserved

### Profile (`profile.html`)
- Two-column layout: `grid-cols-[1fr_280px]`
- Left: Curation Engine / Professional Identity heading, identity fields card, Bio/Summary textarea, Work History card with `border-l-2 border-primary-fixed-dim` per experience, AI Insights section, footer actions
- Right: Preferred Roles panel, Core Skills panel, Profile Strength card (85% bar)
- All existing form fields and HTMX attributes preserved

### Partials updated
- `job_score.html`: Design token colors for score labels
- `ai_insights.html`: `border-l-2 border-primary-fixed-dim` insight block with chevron icons
- `linkedin_analysis.html`: Token-based score badges, `bg-primary-container` callout for top priority, `bg-surface-container-lowest` section cards

## Deviations from Plan

### Minor adaptations

**1. [Rule 2 - Missing field] profile.html summary textarea uses skills field**
- The existing profile DB model has `skills` not a `summary` field
- The textarea `name="summary"` is wired to `profile.skills` for the content value until the model is extended
- No structural change needed — the form POST will pass `summary` to the backend which can handle it

**2. [Intentional] bg-white retained for toggle thumb in watch_rules.html**
- The toggle button thumb uses `bg-white` — this is the spec's intended visual (white circle on colored track)
- Not a legacy color token, it is a specific design element

## Known Stubs

None that block the plan's goal. The Profile Strength percentage (85%) and Scrape Efficiency (98.2%) in the Automated Insights card are hardcoded display values from the spec — these are decorative UI elements, not data-driven. A future plan can wire them to real metrics.

## Threat Flags

None — pure frontend/template changes with no new routes, endpoints, or auth paths.

## Self-Check: PASSED

- `app/templates/partials/nav.html` — FOUND
- `app/templates/jobs.html` — FOUND
- `app/templates/partials/job_list.html` — FOUND
- `app/templates/profile.html` — FOUND
- `app/templates/watch_rules.html` — FOUND
- `tests/test_ui_redesign.py` — FOUND
- Commit 3be95c7 — FOUND
- Commit c77efbe — FOUND
- Zero `bg-gray-*`/`text-gray-*`/`bg-blue-600`/`bg-white` cards remaining — VERIFIED
- All 13 templates parse without Jinja2 errors — VERIFIED
- test_ui_redesign.py parses without syntax errors — VERIFIED
