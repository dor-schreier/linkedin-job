"""Scrape routes — search config, background task trigger, status polling, scheduler."""
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.scraper import run_scrape
from app.schemas.scheduler import (
    CleanupResult,
    CleanupStateResponse,
    SchedulerPageResponse,
    SchedulerStatusResponse,
    ScrapeLastResult,
    ScrapeLogResponse,
    ScrapePageResponse,
    ScrapeProgress,
    ScrapeStateResponse,
    SearchConfigResponse,
    TaskStartedResponse,
)

router = APIRouter()

_scrape_lock = threading.Lock()
_scrape_stop_event = threading.Event()
_scrape_status: dict = {"running": False, "last_result": None, "error": None, "stop_requested": False, "progress": None}


def _run_scrape_task(config, sites=None) -> None:
    def _progress_cb(state: dict) -> None:
        _scrape_status["progress"] = state

    with _scrape_lock:
        try:
            result = run_scrape(config=config, sites=sites, stop_event=_scrape_stop_event, progress_callback=_progress_cb)
            if "error" in result:
                _scrape_status["error"] = result["error"]
                _scrape_status["last_result"] = None
            else:
                _scrape_status["last_result"] = result
        except Exception as e:
            _scrape_status["error"] = str(e)
        finally:
            _scrape_status["running"] = False
            _scrape_status["stop_requested"] = False
            _scrape_status["progress"] = None
            _scrape_stop_event.clear()


@router.get("/scrape", response_model=ScrapePageResponse, tags=["scrape"])
def scrape_page(session: Session = Depends(get_session)):
    repo = JobRepository(session)
    latest_config = repo.get_active_search_config()
    cfg_model = None
    if latest_config:
        cfg_model = SearchConfigResponse(
            id=latest_config.id,
            keywords=latest_config.keywords,
            location=latest_config.location,
            experience_level=latest_config.experience_level,
            work_mode=latest_config.work_mode,
            role_level=latest_config.role_level,
            country=latest_config.country,
            max_age_hours=latest_config.max_age_hours,
            include_remote=bool(latest_config.include_remote),
            include_comeet=bool(getattr(latest_config, "include_comeet", False)),
            exclude_keywords=latest_config.exclude_keywords,
            blocked_companies=latest_config.blocked_companies,
            results_wanted=latest_config.results_wanted or 50,
            min_salary=latest_config.min_salary,
        )
    lr = _scrape_status.get("last_result")
    last_result_model = None
    if lr:
        last_result_model = ScrapeLastResult(
            inserted=lr.get("inserted", 0),
            skipped=lr.get("skipped", 0),
            total_scraped=lr.get("total_scraped", 0),
        )
    progress_data = _scrape_status.get("progress")
    progress_model = ScrapeProgress(**progress_data) if progress_data else None
    return JSONResponse(ScrapePageResponse(
        latest_config=cfg_model,
        status=ScrapeStateResponse(
            running=bool(_scrape_status["running"]),
            error=_scrape_status.get("error"),
            last_result=last_result_model,
            stop_requested=bool(_scrape_status.get("stop_requested")),
            progress=progress_model,
        ),
    ).model_dump(mode="json"))


class ScrapeRunBody(BaseModel):
    config_id: Optional[int] = None
    sites: Optional[list[str]] = None


@router.post("/scrape/run", response_model=TaskStartedResponse, tags=["scrape"])
def scrape_run(
    background_tasks: BackgroundTasks,
    body: Optional[ScrapeRunBody] = None,
    session: Session = Depends(get_session),
):
    body = body or ScrapeRunBody()
    repo = JobRepository(session)

    if body.config_id is not None:
        configs = repo.list_search_configs(active_only=True)
        config = next((c for c in configs if c.id == body.config_id), None)
    else:
        config = repo.get_active_search_config()

    if config is None:
        return JSONResponse(
            TaskStartedResponse(started=False, message="No search config found. Save a config first.").model_dump(),
            status_code=400,
        )

    session.expunge(config)

    if _scrape_status.get("running"):
        return JSONResponse(
            TaskStartedResponse(started=False, message="A scrape is already running.").model_dump(),
            status_code=409,
        )

    _scrape_status["running"] = True
    _scrape_status["error"] = None
    _scrape_status["stop_requested"] = False
    _scrape_status["progress"] = None
    _scrape_stop_event.clear()
    background_tasks.add_task(_run_scrape_task, config, body.sites)
    return JSONResponse(TaskStartedResponse(started=True, message="Scrape started.").model_dump())


@router.post("/scrape/stop", response_model=TaskStartedResponse, tags=["scrape"])
def scrape_stop():
    if not _scrape_status.get("running"):
        return JSONResponse(
            TaskStartedResponse(started=False, message="No scrape is running.").model_dump(),
            status_code=409,
        )
    _scrape_stop_event.set()
    _scrape_status["stop_requested"] = True
    return JSONResponse(
        TaskStartedResponse(
            started=True,
            message="Stop requested — scrape will halt after the current job finishes.",
        ).model_dump()
    )


class SaveConfigBody(BaseModel):
    keywords: Optional[str] = None
    location: Optional[str] = None
    experience_level: Optional[str] = None
    work_mode: Optional[str] = None
    role_level: Optional[str] = None
    country: Optional[str] = "israel"
    max_age_hours: Optional[int] = 72
    include_remote: bool = False
    include_comeet: bool = False
    exclude_keywords: Optional[str] = None
    blocked_companies: Optional[str] = None
    results_wanted: int = 50
    min_salary: Optional[int] = None


@router.post("/scrape/save-config", response_model=TaskStartedResponse, tags=["scrape"])
def scrape_save_config(body: SaveConfigBody, session: Session = Depends(get_session)):
    repo = JobRepository(session)
    repo.upsert_search_config(
        keywords=body.keywords or "",
        location=body.location or "",
        experience_level=body.experience_level or None,
        work_mode=body.work_mode or None,
        role_level=body.role_level or None,
        country=body.country or "israel",
        max_age_hours=body.max_age_hours,
        include_remote=body.include_remote,
        include_comeet=body.include_comeet,
        exclude_keywords=body.exclude_keywords,
        blocked_companies=body.blocked_companies,
        results_wanted=body.results_wanted,
        min_salary=body.min_salary,
        is_active=True,
    )
    return JSONResponse(TaskStartedResponse(started=True, message="Config saved.").model_dump())


@router.get("/scrape/status", response_model=ScrapeStateResponse, tags=["scrape"])
def scrape_status():
    lr = _scrape_status.get("last_result")
    last_result_model = None
    if lr:
        last_result_model = ScrapeLastResult(
            inserted=lr.get("inserted", 0),
            skipped=lr.get("skipped", 0),
            total_scraped=lr.get("total_scraped", 0),
        )
    progress_data = _scrape_status.get("progress")
    progress_model = ScrapeProgress(**progress_data) if progress_data else None
    return JSONResponse(ScrapeStateResponse(
        running=bool(_scrape_status["running"]),
        error=_scrape_status.get("error"),
        last_result=last_result_model,
        stop_requested=bool(_scrape_status.get("stop_requested")),
        progress=progress_model,
    ).model_dump(mode="json"))


# ── Scheduler endpoints ──────────────────────────────────────────────────────

@router.get("/scheduler", response_model=SchedulerPageResponse, tags=["scheduler"])
def scheduler_page(session: Session = Depends(get_session)):
    from app.services import scheduler as sched_service
    from app.services.cleanup_service import get_cleanup_status
    repo = JobRepository(session)
    cfg = repo.get_scheduler_config()
    logs = repo.list_scrape_logs(limit=10)
    next_run = sched_service.get_next_run_time()
    cleanup_status = get_cleanup_status()
    log_models = [
        ScrapeLogResponse(
            id=log.id,
            started_at=log.started_at,
            finished_at=log.finished_at,
            jobs_found=log.jobs_found,
            jobs_new=log.jobs_new,
            status=log.status,
            error=log.error,
        )
        for log in logs
    ]
    cr = cleanup_status.get("last_result")
    cleanup_result_model = None
    if cr:
        cleanup_result_model = CleanupResult(
            checked=cr.get("checked", 0),
            marked_inactive=cr.get("marked_inactive", 0),
            errors=cr.get("errors", 0),
            duration_ms=cr.get("duration_ms", 0),
        )
    return JSONResponse(SchedulerPageResponse(
        config=SchedulerStatusResponse(
            is_enabled=cfg.is_enabled,
            interval_hours=cfg.interval_hours,
            is_running=sched_service.is_running(),
            next_run=next_run,
        ),
        scrape_logs=log_models,
        cleanup_last_run_at=cleanup_status.get("last_run_at"),
        cleanup_last_result=cleanup_result_model,
    ).model_dump(mode="json"))


@router.post("/scheduler/toggle", response_model=SchedulerStatusResponse, tags=["scheduler"])
def scheduler_toggle(session: Session = Depends(get_session)):
    from app.services import scheduler as sched_service
    repo = JobRepository(session)
    cfg = repo.get_scheduler_config()
    if sched_service.is_running():
        sched_service.stop_scheduler()
        repo.update_scheduler_config(is_enabled=False)
    else:
        repo.update_scheduler_config(is_enabled=True)
        cfg = repo.get_scheduler_config()
        sched_service.start_scheduler(interval_hours=cfg.interval_hours)
    cfg = repo.get_scheduler_config()
    next_run = sched_service.get_next_run_time()
    return JSONResponse(SchedulerStatusResponse(
        is_enabled=cfg.is_enabled,
        interval_hours=cfg.interval_hours,
        is_running=sched_service.is_running(),
        next_run=next_run,
    ).model_dump(mode="json"))


@router.post("/scheduler/run-now", response_model=TaskStartedResponse, tags=["scheduler"])
def scheduler_run_now():
    from app.services import scheduler as sched_service
    started = sched_service.run_now()
    msg = "A scrape is already running." if not started else "Manual scrape started — check logs shortly."
    return JSONResponse(TaskStartedResponse(started=started, message=msg).model_dump())


@router.post("/cleanup/run", response_model=TaskStartedResponse, tags=["scheduler"])
def cleanup_run_now():
    from app.services.cleanup_service import run_cleanup_now
    started = run_cleanup_now()
    msg = "Cleanup is already running." if not started else "Cleanup started."
    return JSONResponse(TaskStartedResponse(started=started, message=msg).model_dump())


@router.get("/cleanup/status", response_model=CleanupStateResponse, tags=["scheduler"])
def cleanup_status_poll():
    from app.services.cleanup_service import get_cleanup_status
    status = get_cleanup_status()
    cr = status.get("last_result")
    cleanup_result_model = None
    if cr:
        cleanup_result_model = CleanupResult(
            checked=cr.get("checked", 0),
            marked_inactive=cr.get("marked_inactive", 0),
            errors=cr.get("errors", 0),
            duration_ms=cr.get("duration_ms", 0),
        )
    return JSONResponse(CleanupStateResponse(
        running=bool(status["running"]),
        last_run_at=status.get("last_run_at"),
        last_result=cleanup_result_model,
    ).model_dump(mode="json"))


@router.post("/scheduler/config", response_model=SchedulerStatusResponse, tags=["scheduler"])
def scheduler_update_config(
    interval_hours: int = Form(...),
    session: Session = Depends(get_session),
):
    from app.services import scheduler as sched_service
    if interval_hours < 1 or interval_hours > 168:
        raise HTTPException(status_code=422, detail="Interval must be 1–168 hours.")
    repo = JobRepository(session)
    repo.update_scheduler_config(interval_hours=interval_hours)
    if sched_service.is_running():
        sched_service.reschedule(interval_hours)
    cfg = repo.get_scheduler_config()
    next_run = sched_service.get_next_run_time()
    return JSONResponse(SchedulerStatusResponse(
        is_enabled=cfg.is_enabled,
        interval_hours=cfg.interval_hours,
        is_running=sched_service.is_running(),
        next_run=next_run,
    ).model_dump(mode="json"))
