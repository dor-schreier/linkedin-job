# ruff: noqa: E402 — load_dotenv() must run before module-level imports
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.logging_config import configure_logging
from app.routes.companies import router as companies_router
from app.routes.interviews import router as interviews_router
from app.routes.cv import router as cv_router
from app.routes.cv_upload import router as cv_upload_router
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.profile import router as profile_router
from app.routes.reject import router as reject_router
from app.routes.scrape import router as scrape_router
from app.routes.watch import router as watch_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_file = configure_logging()
    logger.info("Session started — log file: %s", log_file)
    init_db()
    from app.database import SessionLocal
    from app.repository import JobRepository
    from app.services import scheduler as sched_service
    with SessionLocal() as session:
        repo = JobRepository(session)
        cfg = repo.get_scheduler_config()
        if cfg.is_enabled:
            sched_service.start_scheduler(interval_hours=cfg.interval_hours)
    from app.services.llm_service import check_llm_health
    _health = check_llm_health()
    if _health["ok"]:
        logger.info("LLM health OK — provider=%s model=%s", _health["provider"], _health["model"])
    else:
        logger.warning("LLM health check failed — provider=%s model=%s error=%s",
                       _health["provider"], _health["model"], _health["error"])
    yield
    logger.info("Session ending")
    sched_service.stop_scheduler()


app = FastAPI(title="Job Finder", lifespan=lifespan)

if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(profile_router)
app.include_router(cv_upload_router)
app.include_router(cv_router)

# /api/* — all API endpoints; React SPA consumes these
app.include_router(health_router, prefix="/api", tags=["api/health"])
app.include_router(jobs_router, prefix="/api", tags=["api/jobs"])
app.include_router(scrape_router, prefix="/api", tags=["api/scrape"])
app.include_router(watch_router, prefix="/api", tags=["api/watch"])
app.include_router(reject_router, prefix="/api", tags=["api/reject"])
app.include_router(companies_router, prefix="/api", tags=["api/companies"])
app.include_router(interviews_router, prefix="/api", tags=["api/interviews"])

# Serve built React SPA — must come after all API routers
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        static_file = os.path.join(_frontend_dist, full_path)
        if os.path.isfile(static_file):
            return FileResponse(static_file)
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
