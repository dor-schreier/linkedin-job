# 06 · App-Readiness Changes

Code-level work required before the app can run on ECS. Everything here is in this repo (FastAPI + SQLAlchemy + APScheduler + Jinja2/HTMX), not in the cloud.

## 1. SQLite → Postgres

### Dependencies

Add to `requirements.txt`:

```
psycopg[binary]>=3.1
```

### Connection string

`app/database.py` currently defaults to SQLite. Replace the default and read from env:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
```

Local dev keeps SQLite (`sqlite:///./data/jobs.db`); production gets `postgresql+psycopg://...` from the SSM-backed `DATABASE_URL` env var.

### SQLite-specific code to audit

- `connect_args={"check_same_thread": False}` — only applies to SQLite. Guard with a conditional:
  ```python
  connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
  ```
- Any `pragma`/`PRAGMA` statements — Postgres ignores them; remove or guard.
- SQLAlchemy `DateTime` columns are fine in both backends.
- `ALTER TABLE ... ADD COLUMN` migrations in `app/database.py`: Postgres supports them natively. The try/except idempotency wrapper still works; just confirm column types map (`TEXT`, `INTEGER`, `BOOLEAN`, `DATETIME` → all valid in Postgres).
- `is_rejected` boolean default: in SQLite this is `0/1`, in Postgres it's `TRUE/FALSE`. SQLAlchemy handles the difference if the column type is `Boolean`.
- Full-text search / `LIKE`: case sensitivity differs. Use `ILIKE` or `lower()` for Postgres.

### Data migration

For a one-time export of the existing `data/jobs.db`:

```bash
# Local
sqlite3 data/jobs.db .dump > dump.sql
# Strip SQLite-isms (sed out PRAGMA, BEGIN TRANSACTION, AUTOINCREMENT)
# Connect to RDS via a temporary bastion or local port-forward, then:
psql $DATABASE_URL < dump.sql
```

Or write a small `scripts/sqlite_to_postgres.py` that uses SQLAlchemy to read every row and insert into the new DB.

## 2. Containerization

### `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq5 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Optional: skip Playwright install in the API image. The default
# GOOGLE_SEARCH_BACKEND=ddgs doesn't need it.
# If you must include it, expect the image to balloon past 1 GB.

COPY app/ ./app/
COPY scripts/ ./scripts/

EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://localhost:8010/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

### `.dockerignore`

```
.venv
data/
*.db
*.sqlite*
tests/
cv_output/
.git
.github
frontend/node_modules
research/
.env
.env.*
```

Keep `frontend/dist` (if you build the frontend) but drop `node_modules`.

### Frontend build

If the React app needs to be served by FastAPI, build it in a multi-stage:

```dockerfile
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM base AS final
COPY --from=web /web/dist /app/app/static/dist
```

Or serve from CloudFront and skip bundling into the API image.

## 3. Health endpoint

Add to `app/main.py` (or a route file):

```python
from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal

router = APIRouter()

@router.get("/health")
def health():
    try:
        with SessionLocal() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}, 503
```

Wire it before any auth middleware so Cognito doesn't gate it.

## 4. Cognito OIDC integration

Use `authlib`:

```
authlib>=1.3
itsdangerous>=2.2
```

```python
# app/auth.py
import os
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware

oauth = OAuth()
oauth.register(
    name="cognito",
    client_id=os.environ["COGNITO_CLIENT_ID"],
    client_secret=os.environ["COGNITO_CLIENT_SECRET"],
    server_metadata_url=(
        f"https://cognito-idp.{os.environ['COGNITO_REGION']}.amazonaws.com/"
        f"{os.environ['COGNITO_USER_POOL']}/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)
```

```python
# app/main.py (excerpt)
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])

@app.get("/login")
async def login(request: Request):
    return await oauth.cognito.authorize_redirect(request, request.url_for("auth_callback"))

@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    token = await oauth.cognito.authorize_access_token(request)
    request.session["user"] = token["userinfo"]
    return RedirectResponse("/")

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/")
```

Add a dependency that rejects un-authenticated requests on protected routes:

```python
def current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
```

Apply it via `Depends(current_user)` on routers that need auth. Leave `/health` and `/auth/*` unprotected.

## 5. Config / env vars

Centralize in `app/config.py` (Pydantic settings is ideal):

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    ollama_url: str | None = None
    cognito_region: str
    cognito_user_pool: str
    cognito_client_id: str
    cognito_client_secret: str
    cognito_domain: str
    session_secret: str

    class Config:
        env_file = ".env"   # local only; ignored in container
```

Pass all of these via ECS task definition env vars + secrets.

## 6. Scheduler

Two options (already discussed in [03](03-deployment-plan.md), Phase 9):

### Option A — keep APScheduler

Ensure the service stays at `desired_count = 1`. Document this loudly. The scheduler runs in-process and the threading lock prevents concurrent scrapes.

### Option B — external scheduler

1. Add a top-level script `scripts/run_scrape.py` (one already exists) that executes a single scrape and exits.
2. Build the same image; the entrypoint is parameterized by the container command.
3. Create a second ECS task definition with `command = ["python", "scripts/run_scrape.py", ...]`.
4. EventBridge Scheduler triggers `ecs:RunTask` against that task definition every 6 hours.
5. In the API container, set `DISABLE_SCHEDULER=1` and short-circuit `app/services/scheduler.py`.

Pick B if you ever want to scale the API to >1 task.

## 7. Logging

CloudWatch ingests stdout/stderr via the `awslogs` driver. Switch the Python logger to JSON format for searchability:

```python
import logging, json, sys
class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
```

## 8. Image-size mitigations

The current scrape stack pulls in:

- `jobspy` and its transitive scrapers
- `playwright` (huge, ~1.5 GB with browsers installed)
- LLM SDKs

For the API image, pin `GOOGLE_SEARCH_BACKEND=ddgs` and **do not** run `playwright install`. The image stays around 250 MB.

If you ever need Playwright server-side, build a _second_ image for the scrape worker only (Option B above). The API image stays small.

## 9. CSRF / sessions

`SessionMiddleware` uses signed cookies. Set:

- `https_only=True` once you have HTTPS.
- A long-random `SESSION_SECRET` (rotate yearly via SSM).
- `same_site="lax"`.

## 10. Local-to-cloud parity checklist

- [ ] `DATABASE_URL` configurable.
- [ ] Postgres schema migrations idempotent.
- [ ] Dockerfile builds clean (`docker build .`).
- [ ] Container runs locally against local Postgres (`docker compose up`).
- [ ] `/health` returns 200 after DB ready.
- [ ] Cognito hosted UI flow works end-to-end with a local tunnel (e.g., `cloudflared`) before going live.
- [ ] `LLM_PROVIDER=groq` works without local Ollama.
- [ ] Image pushed to ECR.
- [ ] Secrets in SSM, not in env files in the image.
- [ ] `data/jobs.db` migrated to RDS (or accept fresh DB).
