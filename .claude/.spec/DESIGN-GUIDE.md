# Design Guide — Job Finder UI Redesign
> Design system derived from the Stitch mockups (`/stitch/slate_syntax/DESIGN.md`) applied to the Job Finder app.

---

## 1. Creative North Star

**"The Digital Curator"** — information treated with editorial reverence. The aesthetic is **Developer-High-End**: premium, focused, cognitively easy. We use **Intentional Asymmetry** — large display type offset from dense info blocks — and expansive breathing margins over rigid boxes.

---

## 2. Layout System

### Navigation: Top Bar → Left Sidebar
The current horizontal top-nav is replaced with a **fixed left sidebar** (w-64) plus a **sticky top header bar** per page.

| Zone | Width | Role |
|------|-------|------|
| Sidebar | `w-64` fixed | App name, user context, primary nav links, primary CTA |
| Main canvas | `ml-64` | Page header + content |
| Top header | Full width, sticky | Page title, search, status indicators |

### Main content max-width
`max-w-6xl mx-auto p-8` — generous padding, not full-bleed.

### Detail panel (job detail)
A slide-in **Focus Blade** panel (`w-[450px]`, fixed inset-y-0 right-0) replaces full-page job detail routes where applicable. Uses `backdrop-blur` on the overlay.

---

## 3. Color Tokens

All Tailwind color extensions from the Stitch config. **Never use default Tailwind blue-* or gray-* for anything design-system-related.**

```js
// tailwind.config extend.colors
{
  "background":               "#f7f9fb",   // page bg
  "surface":                  "#f7f9fb",   // same as background
  "surface-bright":           "#f7f9fb",
  "surface-dim":              "#cfdce3",
  "surface-container-lowest": "#ffffff",   // card "pop"
  "surface-container-low":    "#f0f4f7",   // hover state, input bg
  "surface-container":        "#e8eff3",   // tag bg
  "surface-container-high":   "#e1e9ee",   // secondary btn
  "surface-container-highest":"#d9e4ea",   // strong emphasis
  "surface-variant":          "#d9e4ea",
  "on-surface":               "#2a3439",   // primary text
  "on-surface-variant":       "#566166",   // secondary text
  "outline":                  "#717c82",   // subtle meta text
  "outline-variant":          "#a9b4b9",   // ghost borders (at 15% opacity only)
  "primary":                  "#565e74",   // brand / active / CTAs
  "primary-dim":              "#4a5268",   // icon tint
  "primary-fixed":            "#dae2fd",
  "primary-fixed-dim":        "#ccd4ee",
  "primary-container":        "#dae2fd",   // score badge bg (high match)
  "on-primary":               "#f7f7ff",   // text on primary bg
  "on-primary-container":     "#4a5167",
  "secondary":                "#506076",
  "secondary-container":      "#d3e4fe",   // source badge (LinkedIn)
  "on-secondary-container":   "#435368",
  "tertiary":                 "#5b5d78",
  "tertiary-container":       "#dcddfe",   // source badge (Indeed)
  "on-tertiary-container":    "#4c4e69",
  "error":                    "#9f403d",
  "error-container":          "#fe8983",
  "on-error-container":       "#752121",
}
```

### Surface Hierarchy (The "Stack of Paper" Rule)
Use background color shifts — **no 1px solid borders for sectioning**.

```
background (page)
  └─ surface-container-low  (sidebar, section separators)
       └─ surface-container-lowest  (cards — natural "pop")
            └─ surface-container-high  (secondary interactive areas)
```

---

## 4. Typography

### Font Stack
```html
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet"/>
```

```js
// tailwind.config extend.fontFamily
{
  "headline": ["Manrope"],
  "body":     ["Inter"],
  "label":    ["Inter"]
}
```

| Role | Font | Size | Weight | Token |
|------|------|------|--------|-------|
| App title | Manrope | `text-lg` | `font-extrabold` | `display` |
| Page heading | Manrope | `text-xl` | `font-bold` | `title-lg` |
| Card title | Manrope | `text-xl` | `font-bold` | `headline` |
| Card subtitle | Inter | `text-sm` | `font-semibold` | `title-sm` |
| Body text | Inter | `text-sm` | `font-normal` | `body-md` |
| Meta / labels | Inter | `text-xs` | `font-medium` | `label-md` |
| Tags / badges | Inter | `text-[11px]` | `font-bold uppercase tracking-tight` | `label-sm` |

Body text `leading-relaxed` (1.625). Never use pure black.

---

## 5. Border Radius

```js
// tailwind.config extend.borderRadius
{
  "DEFAULT": "0.25rem",   // sm — inputs, inline chips
  "lg":      "0.5rem",    // buttons, sidebar nav items
  "xl":      "0.75rem",   // cards
  "full":    "9999px"     // pills, avatar, FAB
}
```

---

## 6. Elevation & Shadows

- **No heavy drop-shadows.** Use background tier shifts for separation.
- **Cards on hover:** `hover:shadow-xl hover:shadow-primary/5` (primary-tinted ambient glow).
- **Floating elements (FAB, modal):** `shadow-2xl`
- **Ghost border (accessibility fallback only):** `border border-outline-variant/15`

---

## 7. Component Patterns

### Sidebar Nav Item
```html
<!-- Active -->
<a class="flex items-center gap-3 px-4 py-3 rounded-lg font-semibold text-on-surface bg-surface-container-low border-r-2 border-primary">
  <span class="material-symbols-outlined">dashboard</span>
  Label
</a>

<!-- Inactive -->
<a class="flex items-center gap-3 px-4 py-3 rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors">
  <span class="material-symbols-outlined">person_search</span>
  Label
</a>
```

### Primary Button
```html
<button class="py-2.5 px-4 bg-primary text-on-primary rounded-lg font-bold text-sm hover:opacity-90 transition-opacity">
  Action
</button>
```

### Secondary Button
```html
<button class="py-2.5 px-4 bg-surface-container-high text-on-surface rounded-lg font-bold text-sm hover:bg-surface-container-highest transition-colors">
  Secondary
</button>
```

### Tertiary / Ghost Button
```html
<button class="py-2.5 px-4 text-primary rounded-lg font-bold text-sm hover:bg-primary-container/30 transition-colors">
  Tertiary
</button>
```

### FAB (Floating Action Button)
```html
<div class="fixed bottom-8 right-8 z-[60]">
  <button class="flex items-center gap-3 bg-primary text-on-primary px-6 py-4 rounded-full shadow-2xl hover:scale-105 transition-transform duration-200">
    <span class="material-symbols-outlined">add_task</span>
    <span class="font-bold tracking-tight">Label</span>
  </button>
</div>
```

### Job Card
```html
<div class="group bg-surface-container-lowest rounded-xl p-6 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300 flex flex-col md:flex-row gap-6 relative overflow-hidden">
  <!-- High-match accent bar -->
  <div class="absolute top-0 left-0 w-1.5 h-full bg-primary"></div>
  <!-- ... content ... -->
</div>
```

### AI Insight Block (within card)
```html
<p class="text-sm text-on-surface-variant leading-relaxed bg-surface-container-low/50 p-3 rounded-lg border-l-2 border-primary-fixed-dim">
  <span class="font-bold text-primary mr-1 italic">AI Insight:</span>
  …
</p>
```

### Score Badge
```html
<!-- High match (98+) -->
<div class="bg-primary-container text-on-primary-container px-3 py-1 rounded-lg">
  <span class="text-lg font-extrabold">98</span>
  <span class="text-xs font-medium">/100</span>
</div>
<!-- Standard -->
<div class="bg-surface-container-high text-on-surface px-3 py-1 rounded-lg">
  <span class="text-lg font-extrabold">85</span>
  <span class="text-xs font-medium">/100</span>
</div>
```

### Source Pill / Tag
```html
<!-- LinkedIn -->
<span class="px-2.5 py-1 bg-secondary-container text-on-secondary-container text-[11px] font-bold rounded uppercase tracking-tight">LinkedIn</span>
<!-- Indeed -->
<span class="px-2.5 py-1 bg-tertiary-container text-on-tertiary-container text-[11px] font-bold rounded uppercase tracking-tight">Indeed</span>
<!-- Generic tag -->
<span class="px-2.5 py-1 bg-surface-container text-on-surface-variant text-[11px] font-bold rounded uppercase tracking-tight">Remote</span>
```

### Status Pill
```html
<!-- Active/Success -->
<div class="flex items-center gap-2 px-3 py-1.5 bg-primary-container text-on-primary-container rounded-full text-xs font-bold">
  <span class="w-2 h-2 bg-primary rounded-full animate-pulse"></span>
  Scraper Active
</div>
<!-- Error -->
<div class="px-3 py-1.5 bg-error-container text-on-error-container rounded-full text-xs font-bold">
  Error
</div>
```

### Watch Rule Row (list item, no dividers)
```html
<li class="px-4 py-4 flex items-center justify-between hover:bg-surface-container-low rounded-lg transition-colors">
  <div class="flex items-center gap-3">
    <span class="material-symbols-outlined text-primary-dim">rule</span>
    <div>
      <span class="text-xs uppercase text-outline font-bold mr-2">keyword</span>
      <span class="text-sm text-on-surface">value</span>
    </div>
  </div>
  <button class="text-error text-xs font-semibold hover:underline">Delete</button>
</li>
```

### Input Field
```html
<input class="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-surface-bright transition-colors" />
```

### Select (filter bar)
```html
<select class="bg-transparent border-none text-sm font-medium text-on-surface-variant focus:ring-0">
  <option>…</option>
</select>
```

### Top Header Bar
```html
<header class="w-full sticky top-0 z-50 bg-surface/80 backdrop-blur-md flex items-center justify-between px-8 py-4 border-b border-outline-variant/15">
  <h2 class="text-xl font-bold font-headline tracking-tight text-on-surface">Page Title</h2>
  <!-- right side: status pills, icon buttons -->
</header>
```

---

## 8. Icons

Use **Material Symbols Outlined** via Google Fonts CDN.

```html
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<style>
  .material-symbols-outlined {
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    vertical-align: middle;
  }
</style>
```

Key icon names used: `dashboard`, `person_search`, `rule`, `notifications`, `settings`, `search`, `filter_list`, `location_on`, `link`, `add`, `add_task`, `work`, `language`.

---

## 9. Do's and Don'ts

### Do
- Use `surface-container-lowest` cards on `surface-container-low` backgrounds — the shift *is* the separator.
- Use `xl` (1.5rem) / `6` padding inside cards. Breathing room is core to the design.
- Use Manrope for all headings (`font-headline` class or `font-family: Manrope`).
- Use `primary-dim` for icon tint to keep icons subtle.
- Use asymmetric layouts: wide left column for content, narrow right column for meta or actions.

### Don't
- **No `border border-gray-200` for sectioning.** Borders are abolished as structural elements.
- **No `bg-gray-100`, `text-gray-*`, `blue-*`.** Use design tokens only.
- **No `divide-y divide-gray-200` between list items.** Use vertical padding + hover bg instead.
- **No heavy `shadow-md`/`shadow-lg` in resting state.** Reserve shadow for hover/float.
- Don't crowd screens. Job listings need `leading-relaxed` and vertical breathing room.
