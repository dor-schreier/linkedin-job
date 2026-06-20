# Frontend

Vite + React + TypeScript frontend for Job Finder.

## Dev setup

```bash
# 1. Start backend
uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8010

# 2. Generate typed API client from live OpenAPI schema (backend must be running)
npm run gen:api

# 3. Start dev server (proxies /api and /cv → :8010)
npm run dev
```

Visit http://localhost:5173

## Prod build

```bash
npm run build          # outputs to frontend/dist/
# uvicorn serves dist/ automatically via spa_fallback route
```

## E2E tests

```bash
npm run test:e2e
```

Playwright starts both uvicorn and vite automatically (via `webServer` in `playwright.config.ts`).
Pass `--reuse-existing-server` if both are already running.
Tests cover four flows: scrape trigger, jobs review, watch rules, and CV export.

## Type checking & linting

```bash
npx tsc --noEmit   # type check (must be clean)
npm run lint       # ESLint (0 errors required)
```

## Design system

### Tokens

All design tokens live in `src/styles/tokens.css`, imported by `src/index.css`.
Tailwind v4 exposes them as utility classes via `@theme`.

Key groups:

- **Surface hierarchy**: `background` → `surface` → `surface-container-{lowest,low,,high,highest}`
- **Text**: `on-surface`, `on-surface-variant`, `outline`
- **Brand**: `primary`, `primary-container`, `primary-dim`
- **Semantic**: `error`, `success`, `warning`, `info`

Rule: never use raw Tailwind palette utilities (`text-green-400`, `bg-red-900`) — use semantic tokens (`text-success`, `bg-error/15`).

### Components

Shared components in `src/components/ui/`:

| Component                    | When to use                                                                                           |
| ---------------------------- | ----------------------------------------------------------------------------------------------------- |
| `Button`                     | All interactive buttons. Variants: `primary`, `secondary`, `ghost`, `danger`. Sizes: `sm`, `md`       |
| `Card`                       | Content containers with optional `title` prop                                                         |
| `Badge`                      | Inline status labels. Colors: `default`, `green`, `red`, `yellow`, `blue`, `primary`                  |
| `Input`                      | Labelled text inputs with optional error display                                                      |
| `EmptyState`                 | Zero-data placeholders with icon, title, description, optional action                                 |
| `LoadingState`               | Spinner + message for async loads                                                                     |
| `ErrorState`                 | Error display with optional retry callback                                                            |
| `ToastProvider` / `useToast` | Transient feedback. Wrap app root in `<ToastProvider>`; call `const toast = useToast()` in components |

### Adding new components

Add to `src/components/ui/`. Use only token-based Tailwind classes. Export directly from the file — no barrel index.

## gen:api

`npm run gen:api` hits `http://localhost:8010/openapi.json` and writes `src/api/schema.d.ts`.
Run whenever the backend schema changes. The file is committed so the build works without a live backend.
