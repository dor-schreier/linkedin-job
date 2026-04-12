---
phase: quick-260412-sij
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
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
  - tests/test_ui_redesign.py
autonomous: true
must_haves:
  truths:
    - "All pages render with fixed left sidebar nav instead of horizontal top nav"
    - "All pages use Manrope headlines, Inter body, Material Symbols icons"
    - "All pages use design token colors (no gray-*, blue-*, bg-white cards)"
    - "Job cards use surface-container-lowest with hover glow, no divide-y"
    - "Watch rules page has two-column layout with create form on right"
    - "Profile page has two-column layout with meta panels on right"
  artifacts:
    - path: "app/templates/partials/nav.html"
      provides: "Sidebar nav component"
    - path: "tests/test_ui_redesign.py"
      provides: "Playwright verification tests"
---

<objective>
Implement full UI redesign per .claude/.spec/UI-REDESIGN-SPEC.md — replace horizontal nav with sidebar, apply Material Design token system, redesign job cards, watch rules, and profile pages.

Purpose: Transform the app from default Tailwind gray/blue to a cohesive "Digital Curator" design system.
Output: All 13 Jinja2 templates updated, Playwright test file created.
</objective>

<execution_context>
@.claude/.spec/UI-REDESIGN-SPEC.md
@.claude/.spec/DESIGN-GUIDE.md
</execution_context>

<context>
@app/templates/partials/nav.html
@app/templates/jobs.html
@app/templates/partials/job_list.html
@app/templates/profile.html
@app/templates/watch_rules.html
@app/templates/watch_matches.html
@app/templates/scrape.html
@app/templates/search_config.html
@app/templates/profile_optimizer.html
@app/templates/partials/ai_insights.html
@app/templates/partials/job_score.html
@app/templates/partials/linkedin_analysis.html
@app/templates/health.html
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace nav + update global shell on all pages</name>
  <files>
    app/templates/partials/nav.html,
    app/templates/jobs.html,
    app/templates/profile.html,
    app/templates/watch_rules.html,
    app/templates/watch_matches.html,
    app/templates/scrape.html,
    app/templates/search_config.html,
    app/templates/profile_optimizer.html,
    app/templates/health.html
  </files>
  <action>
1. Replace `partials/nav.html` with the sidebar version from UI-REDESIGN-SPEC.md section "1. Shared Nav". The nav items tuple changes from 3-element (key, href, label) to 4-element (key, href, icon, label). Copy the exact HTML from the spec.

2. On EVERY page template (jobs.html, profile.html, watch_rules.html, watch_matches.html, scrape.html, search_config.html, profile_optimizer.html, health.html), apply these changes to the `<head>`:
   - Replace `<script src="https://cdn.tailwindcss.com"></script>` with `<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>`
   - Add after the HTMX script: the Google Fonts links for Manrope+Inter and Material Symbols Outlined (exact URLs from spec "Base HTML head")
   - Add the Tailwind config script block with ALL color tokens from DESIGN-GUIDE.md section 3, plus fontFamily extensions (headline: Manrope, body: Inter, label: Inter)
   - Add the `<style>` block for .material-symbols-outlined settings, body font-family Inter, h1/h2/h3/.font-headline Manrope, .htmx-request opacity

3. On EVERY page template, change `<body class="bg-gray-100 min-h-screen">` to `<body class="bg-background text-on-surface min-h-screen">`.

4. On EVERY page template, wrap the page content (everything after `{% include "partials/nav.html" %}`) in `<div class="ml-64 min-h-screen">...</div>`.

5. On EVERY page template, add the appropriate sticky `<header>` inside the ml-64 wrapper:
   - jobs.html: "Ranked Feed" header with search input (from spec section 2)
   - watch_rules.html: "Watch Rules" header with "Create New Rule" button (from spec section 4)
   - profile.html: header with search input + notifications/settings buttons + "Scraper Active" pill (from spec section 5)
   - Other pages: generic sticky header with page title matching the current h1 text

6. Token replacements on ALL pages — do a sweep for:
   - `bg-white` -> `bg-surface-container-lowest`
   - `border border-gray-200 rounded` -> `bg-surface-container-lowest rounded-xl` (remove border)
   - `border border-gray-300 rounded` inputs -> `bg-surface-container-low border-none rounded-lg`
   - `bg-blue-600 text-white` -> `bg-primary text-on-primary rounded-lg`
   - `text-gray-800` -> `text-on-surface`
   - `text-gray-700` -> `text-on-surface-variant`
   - `text-gray-600` -> `text-on-surface-variant`
   - `text-gray-500` -> `text-outline`
   - `text-gray-400` -> `text-outline`
   - `bg-gray-100` -> `bg-background`
   - `bg-gray-50` -> `bg-surface-container-low`
   - `text-blue-600` -> `text-primary`
   - `border-blue-600` -> `border-primary`
   - `bg-red-600` -> `bg-error`
   - `text-white` (on colored bg) -> `text-on-primary` or `text-on-error` as appropriate
   - Remove all `divide-y divide-gray-200` classes
  </action>
  <verify>
    <automated>cd C:/Users/DorSchreier/Documents/GitHub/linkedin-job && grep -rn "bg-gray-100\|text-gray-\|bg-blue-600\|bg-white\|divide-y" app/templates/ | grep -v "{#" | head -20</automated>
  </verify>
  <done>All templates have sidebar nav, global head with fonts/tokens/icons, ml-64 wrapper, sticky headers, and zero old gray/blue color classes remaining.</done>
</task>

<task type="auto">
  <name>Task 2: Redesign job cards, watch rules, and profile pages</name>
  <files>
    app/templates/partials/job_list.html,
    app/templates/partials/job_score.html,
    app/templates/partials/ai_insights.html,
    app/templates/jobs.html,
    app/templates/watch_rules.html,
    app/templates/profile.html
  </files>
  <action>
1. **job_list.html**: Replace the entire card structure with the new job card HTML from UI-REDESIGN-SPEC.md section 3 "Job List Partial". Keep all existing Jinja2 variables (job.title, job.company, job.location, job.ai_score, job.ai_summary, job.job_type, job.is_remote, job.site, job.salary_min, job.date_posted, job.job_url, job.status). The new structure uses grid layout, surface-container-lowest cards, hover glow, accent bar for ai_score >= 90, score badge, AI insight block, tags row, and actions panel. Remove all divide-y separators.

2. **job_score.html**: Update any remaining gray/blue tokens. If it shows score, use the score badge pattern from DESIGN-GUIDE.md (bg-primary-container for high match, bg-surface-container-high for standard).

3. **ai_insights.html**: Update to use the AI insight block pattern: `bg-surface-container-low/50 p-3 rounded-lg border-l-2 border-primary-fixed-dim` with `font-bold text-primary mr-1 italic` for the "AI Insight:" prefix.

4. **jobs.html filter bar**: Replace the current white bordered filter form with the new filter bar from spec section 2: borderless selects with `bg-transparent border-none`, "All Filters" ghost button with filter_list icon, divider line, count text. Keep all existing hx-* attributes and form behavior intact.

5. **watch_rules.html**: Replace entire page body (inside ml-64 wrapper) with the two-column layout from spec section 4. Left column: "Active Automations" label + rule cards with icon, toggle, tags, meta row. Right column: Create rule form panel + Automated Insights card. Keep all existing form actions, method, name attributes, and Jinja2 loops ({% for rule in rules %}) intact.

6. **profile.html**: Replace entire page body (inside ml-64 wrapper) with the two-column layout from spec section 5. Left column: "Curation Engine" / "Professional Identity" heading, Bio/Summary textarea card, Work History card with border-l-2 accent per experience, footer actions. Right column: Preferred Roles panel with tags, Core Skills panel, Profile Strength card. Keep all existing form actions and Jinja2 variables (summary, experiences, preferred_roles, skills) intact.
  </action>
  <verify>
    <automated>cd C:/Users/DorSchreier/Documents/GitHub/linkedin-job && python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('app/templates')); [env.get_template(t) for t in ['jobs.html','profile.html','watch_rules.html','partials/job_list.html']]" && echo "All templates parse OK"</automated>
  </verify>
  <done>Job cards use new grid layout with hover glow and score badges. Watch rules has two-column layout with create form panel. Profile has two-column layout with meta panels. All Jinja2 variables and HTMX attributes preserved.</done>
</task>

<task type="auto">
  <name>Task 3: Add Playwright verification tests</name>
  <files>tests/test_ui_redesign.py</files>
  <action>
Copy the complete Playwright test file from UI-REDESIGN-SPEC.md section "Playwright Verification Tests" into tests/test_ui_redesign.py. This file contains 8 test classes: TestSidebarNav, TestStickyHeader, TestJobCards, TestWatchRules, TestProfilePage, TestColorTokens, TestMaterialSymbols, TestFonts. Copy exactly as specified — no modifications needed.

Verify pytest-playwright is in requirements or note it as a dev dependency.
  </action>
  <verify>
    <automated>cd C:/Users/DorSchreier/Documents/GitHub/linkedin-job && python -c "import ast; ast.parse(open('tests/test_ui_redesign.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>tests/test_ui_redesign.py exists with all 8 test classes, parses without syntax errors.</done>
</task>

</tasks>

<verification>
1. `grep -rn "bg-gray-100\|text-gray-\|bg-blue-600\|bg-white\b\|divide-y" app/templates/` returns zero matches (excluding Jinja2 comments)
2. All templates parse without Jinja2 errors
3. tests/test_ui_redesign.py parses without syntax errors
4. Manual: start server with `uvicorn app.main:app --reload` and verify sidebar nav appears on /jobs, /profile, /watch-rules
</verification>

<success_criteria>
- Sidebar nav with Material Symbols icons on all pages
- Manrope + Inter fonts loaded on all pages
- All color tokens migrated from gray/blue to design system tokens
- Job cards: surface-container-lowest, hover glow, score badges, accent bars
- Watch rules: two-column layout with create form + insights panel
- Profile: two-column layout with preferred roles, skills, profile strength panels
- Zero remaining bg-gray-*, text-gray-*, bg-blue-*, bg-white, divide-y classes
- Playwright test file ready for verification
</success_criteria>

<output>
After completion, create `.planning/quick/260412-sij-implement-ui-redesign-per-claude-spec-ui/260412-sij-SUMMARY.md`
</output>
