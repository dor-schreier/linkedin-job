from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from app.database import init_db
from app.routes.cv import router as cv_router
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.pages import router as pages_router
from app.routes.scrape import router as scrape_router
from app.routes.watch import router as watch_router
from app.routes.reject import router as reject_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start APScheduler using persisted config
    from app.database import SessionLocal
    from app.repository import JobRepository
    from app.services import scheduler as sched_service
    with SessionLocal() as session:
        repo = JobRepository(session)
        cfg = repo.get_scheduler_config()
        if cfg.is_enabled:
            sched_service.start_scheduler(interval_hours=cfg.interval_hours)
    # Verify LLM connectivity at startup (non-blocking)
    from app.services.llm_service import check_llm_health
    import logging as _logging
    _log = _logging.getLogger(__name__)
    _health = check_llm_health()
    if _health["ok"]:
        _log.info("LLM health OK — provider=%s model=%s", _health["provider"], _health["model"])
    else:
        _log.warning("LLM health check failed — provider=%s model=%s error=%s",
                     _health["provider"], _health["model"], _health["error"])
    yield
    sched_service.stop_scheduler()


app = FastAPI(title="Job Finder", lifespan=lifespan)
app.include_router(health_router)
app.include_router(scrape_router)
app.include_router(jobs_router)
app.include_router(pages_router)
app.include_router(watch_router)
app.include_router(cv_router)
app.include_router(reject_router)
