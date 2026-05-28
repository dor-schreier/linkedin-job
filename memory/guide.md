# CV Design Guidelines

A reference template defining the visual system for a clean, professional, single-page CV. Use this as the source of truth for typography, color, spacing, and layout decisions.

---

## 1. Page & Layout

| Property             | Value                                                                    |
| -------------------- | ------------------------------------------------------------------------ |
| Page size            | A4 (210 × 297 mm) or US Letter (8.5 × 11 in)                             |
| Orientation          | Portrait                                                                 |
| Margins (top/bottom) | 18–22 mm                                                                 |
| Margins (left/right) | 18–22 mm                                                                 |
| Column structure     | Single column (primary) or 2-column with 30/70 split for sidebar variant |
| Max content width    | Full width minus margins                                                 |
| Target length        | **1 page — strict** (see §13)                                            |

### Vertical Rhythm

- Base unit: **4 pt** (all spacing is a multiple of this)
- Section gap: **20–24 pt**
- Sub-section gap: **12 pt**
- Paragraph / bullet gap: **4–6 pt**

---

## 2. Typography

### Font Families

| Role                                      | Recommended                                    | Fallback Stack                          |
| ----------------------------------------- | ---------------------------------------------- | --------------------------------------- |
| Headings                                  | Inter, Helvetica Neue, or Source Sans Pro      | `-apple-system, "Segoe UI", sans-serif` |
| Body                                      | Same family as headings (single-family system) | `-apple-system, "Segoe UI", sans-serif` |
| Monospace (optional, for tech stack tags) | JetBrains Mono, IBM Plex Mono                  | `"SF Mono", Consolas, monospace`        |

> **Rule:** Use **one** typeface family for the entire document. Differentiate hierarchy with weight and size, not font switching.

### Type Scale

| Element              | Size     | Weight         | Line Height | Letter Spacing     |
| -------------------- | -------- | -------------- | ----------- | ------------------ |
| Name (H1)            | 24–28 pt | 700 (Bold)     | 1.1         | -0.01em            |
| Tagline / Title      | 11–12 pt | 400 (Regular)  | 1.3         | 0                  |
| Section heading (H2) | 11 pt    | 700 (Bold)     | 1.2         | 0.08em (UPPERCASE) |
| Role / Company (H3)  | 10.5 pt  | 600 (Semibold) | 1.3         | 0                  |
| Date / Location meta | 9.5 pt   | 400 (Regular)  | 1.3         | 0                  |
| Body / Bullets       | 10 pt    | 400 (Regular)  | 1.45        | 0                  |
| Contact line         | 9.5 pt   | 400 (Regular)  | 1.4         | 0                  |
| Footnote / Caption   | 8.5 pt   | 400 (Regular)  | 1.4         | 0                  |

### Casing Rules

- **Name:** Title Case or UPPERCASE (pick one and stay consistent)
- **Section headings:** UPPERCASE with letter-spacing
- **Roles & companies:** Title Case
- **Dates:** `Mon YYYY – Mon YYYY` or `Mon YYYY – Present`

---

## 3. Color Palette

Restrained, print-safe, and ATS-friendly. Default to monochrome with a single accent.

### Primary Palette

| Token       | Hex       | Usage                       |
| ----------- | --------- | --------------------------- |
| `--ink-900` | `#111111` | Name, primary headings      |
| `--ink-700` | `#333333` | Body text, role titles      |
| `--ink-500` | `#666666` | Meta info (dates, location) |
| `--ink-300` | `#BFBFBF` | Dividers, rule lines        |
| `--paper`   | `#FFFFFF` | Page background             |

### Accent (choose one)

| Token               | Hex       | Notes                       |
| ------------------- | --------- | --------------------------- |
| `--accent-navy`     | `#1F3A5F` | Conservative, finance/legal |
| `--accent-teal`     | `#0F766E` | Tech, modern                |
| `--accent-burgundy` | `#7C2D3A` | Editorial, design           |
| `--accent-graphite` | `#2D2D2D` | Pure monochrome variant     |

### Usage Rules

- Accent color used **sparingly** — section headings, name, or a thin divider only.
- Never use accent for body text.
- Maximum 2 colors on the page (ink + one accent). Black-and-white is always valid.
- Maintain **WCAG AA contrast** (≥ 4.5:1) against paper background.

---

## 4. Spacing System

All spacing derived from a 4 pt base unit.

| Token     | Value | Common Use                  |
| --------- | ----- | --------------------------- |
| `space-1` | 4 pt  | Tight inline gaps           |
| `space-2` | 8 pt  | Bullet indent, icon-to-text |
| `space-3` | 12 pt | Sub-section gap             |
| `space-4` | 16 pt | Entry-to-entry gap          |
| `space-5` | 20 pt | Section gap                 |
| `space-6` | 24 pt | Major section gap           |
| `space-8` | 32 pt | Header-to-body gap          |

---

## 5. Dividers & Rules

- **Style:** 0.5 pt solid line, color `--ink-300`
- **Placement:** Below section headings only (optional) — never between every entry
- **Alternative:** Use whitespace and bold typography to separate sections instead of rules
- **Never:** Use boxes, borders around entries, or shaded backgrounds (ATS-hostile)

---

## 6. Bullet & List Style

| Property           | Value                                                    |
| ------------------ | -------------------------------------------------------- |
| Bullet character   | `•` (U+2022) — preferred over `-`, `*`, or custom glyphs |
| Indent             | 12 pt                                                    |
| Hanging indent     | Text aligns flush after bullet                           |
| Bullet-to-text gap | 6 pt                                                     |
| Bullets per role   | 3–5 (max 6)                                              |
| Bullet length      | 1–2 lines; never wrap to 3+                              |

---

## 7. Section Order (Recommended)

1. **Header** — Name, tagline, contact
2. **Summary** — 2–4 lines, optional
3. **Core Skills** — Grouped by category
4. **Professional Experience** — Reverse chronological
5. **Education**
6. **Publications / Projects / Certifications** — As applicable

---

## 8. Header Block

```
[NAME]                                              (24–28 pt, Bold)
[One-line tagline / role positioning]               (11 pt, Regular, ink-500)
[City] · [Phone] · [Email] · [LinkedIn]             (9.5 pt, ink-700)
```

- Contact items separated by middle dot `·` with 6 pt spacing on each side
- Email and LinkedIn may be hyperlinks (color: accent or `--ink-700` underlined)
- No photo (region-dependent; default to no photo for US/UK/IL markets)

---

## 9. Experience Entry Pattern

```
[Role Title] — [Company]                            [Mon YYYY – Mon YYYY]
[One-line context: team size, scope, mandate]       (italic, ink-500, optional)
• Bullet starting with an action verb...
• Bullet emphasizing measurable impact...
Stack: [tech, comma-separated]                      (9.5 pt, ink-500)
```

- Role and date on the same line (flex space-between)
- Tech stack line is optional; use for engineering roles
- Bold the role title, regular weight for company (or vice versa — pick one pattern)

---

## 10. Accessibility & ATS Compliance

- **Single-column layout** preferred for ATS parsing
- **No text in images, icons, or text boxes** — ATS cannot read them
- **No headers/footers** containing essential information
- **Standard section names:** "Experience", "Education", "Skills" (avoid creative renaming)
- **Embed fonts** when exporting to PDF
- **File format:** Export as PDF/A or PDF 1.7 for archival quality
- **File naming:** `Firstname_Lastname_CV.pdf`

---

## 11. Do & Don't

### Do

- Use whitespace generously
- Maintain consistent alignment (left-aligned body, right-aligned dates)
- Stick to one font family
- Use weight contrast (400 vs 700) for hierarchy
- Keep to a single page — **non-negotiable**

### Don't

- Mix more than 2 font families
- Use more than 2 colors
- Justify body text (creates uneven gaps)
- Use decorative icons inline with text
- Add graphs, skill bars, or rating stars (subjective and ATS-hostile)
- Use tables with visible borders for layout

---

## 12. Export Checklist

- [ ] All text renders in selected fonts (fonts embedded)
- [ ] Links are clickable and point to correct URLs
- [ ] Contrast meets WCAG AA
- [ ] No spelling errors (run two passes)
- [ ] Margins consistent on all sides
- [ ] File size < 1 MB
- [ ] Tested by copying text out — order and content remain coherent (ATS test)
- [ ] **Exported PDF is exactly one page — no orphaned content on page 2**

---

## 13. One-Page Constraint

The exported document **must fit on a single page**. This is a hard rule, not a preference.

### Why

- Recruiters spend 6–10 seconds on first pass — a second page is rarely read
- Forces ruthless editing and signals strong prioritization
- Eliminates ATS pagination issues

### How to Fit

Apply in this order, stopping as soon as content fits:

1. **Cut content first** — remove roles older than 10–12 years, drop weak bullets, collapse early-career roles into a single line
2. **Tighten language** — every bullet starts with an action verb; remove filler ("responsible for", "worked on")
3. **Reduce bullets per role** — 5 → 4 → 3 for older roles
4. **Reduce vertical spacing** — section gap 24 → 20 → 18 pt; entry gap 16 → 14 → 12 pt
5. **Reduce margins** — down to 15 mm minimum (never below)
6. **Reduce body size** — 10 pt → 9.5 pt (never below 9 pt)
7. **Reduce line height** — 1.45 → 1.35 (never below 1.3)

### What NOT to Do

- Do **not** shrink font below 9 pt
- Do **not** reduce margins below 15 mm
- Do **not** compress letter-spacing to fit text
- Do **not** spill 2–3 lines onto a second page — either fit fully on page 1, or restructure
- Do **not** use a second page as a "buffer" for nice-to-have content

### Validation

After export, open the PDF and confirm:

- Page count = 1
- No content clipped at the bottom edge
- All text remains legible at 100% zoom
