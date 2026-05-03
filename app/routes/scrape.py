"""Scrape routes — search config, background task trigger, status polling, scheduler."""
import threading
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form
from fastapi.responses import JSONResponse
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
    ScrapeStateResponse,
    SearchConfigResponse,
    TaskStartedResponse,
)

router = APIRouter()

_scrape_lock = threading.Lock()
_scrape_status: dict = {"running": False, "last_result": None, "error": None}


def _run_scrape_task(config) -> None:
    try:
        result = run_scrape(config=config)
        if "error" in result:
            _scrape_status["error"] = result["error"]
            _scrape_status["last_result"] = None
        else:
            _scrape_status["last_result"] = result
    except Exception as e:
        _scrape_status["error"] = str(e)
    finally:
        _scrape_status["running"] = False
        _scrape_lock.release()


@router.get("/scrape", response_model=ScrapePageResponse, tags=["scrape"])
def scrape_page(session: Session = Depends(get_session)):
    repo = JobRepository(session)
    configs = repo.list_search_configs(active_only=True)
    latest_config = configs[-1] if configs else None
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
    return JSONResponse(ScrapePageResponse(
        latest_config=cfg_model,
        status=ScrapeStateResponse(
            running=bool(_scrape_status["running"]),
            error=_scrape_status.get("error"),
            last_result=last_result_model,
        ),
    ).model_dump(mode="json"))


@router.post("/scrape/run", response_model=TaskStartedResponse, tags=["scrape"])
def scrape_run(
    background_tasks: BackgroundTasks,
    keywords: Annotated[str, Form(min_length=1, max_length=200)],
    location: Annotated[str, Form(min_length=1, max_length=200)],
    experience_level: str = Form(""),
    work_mode: str = Form(""),
    role_level: str = Form(""),
    country: str = Form("israel"),
    max_age_hours: str = Form("72"),
    include_remote: str = Form(""),
    exclude_keywords: str = Form(""),
    blocked_companies: str = Form(""),
    results_wanted: str = Form("50"),
    min_salary: str = Form(""),
    session: Session = Depends(get_session),
):
    def _parse_csv(val: str) -> Optional[str]:
        tokens = [t.strip() for t in val.split(",") if t.strip()]
        return ", ".join(tokens) if tokens else None

    def _parse_int(val: str, default: int) -> int:
        try:
            return int(val) if val.strip() else default
        except ValueError:
            return default

    repo = JobRepository(session)
    config = repo.add_search_config(
        keywords=keywords,
        location=location,
        experience_level=experience_level or None,
        work_mode=work_mode or None,
        role_level=role_level or None,
        country=country or "israel",
        max_age_hours=_parse_int(max_age_hours, 72) if max_age_hours.strip() else None,
        include_remote=bool(include_remote),
        exclude_keywords=_parse_csv(exclude_keywords),
        blocked_companies=_parse_csv(blocked_companies),
        results_wanted=_parse_int(results_wanted, 50),
        min_salary=_parse_int(min_salary, 0) if min_salary.strip() else None,
        is_active=True,
    )
    session.expunge(config)

    if not _scrape_lock.acquire(blocking=False):
        return JSONResponse(
            TaskStartedResponse(started=False, message="A scrape is already running.").model_dump(),
            status_code=409,
        )

    _scrape_status["running"] = True
    _scrape_status["error"] = None
    background_tasks.add_task(_run_scrape_task, config)
    return JSONResponse(TaskStartedResponse(started=True, message="Scrape started.").model_dump())


@router.post("/scrape/save-config", response_model=TaskStartedResponse, tags=["scrape"])
def scrape_save_config(
    keywords: Annotated[str, Form(min_length=1, max_length=200)],
    location: Annotated[str, Form(min_length=1, max_length=200)],
    experience_level: str = Form(""),
    work_mode: str = Form(""),
    role_level: str = Form(""),
    country: str = Form("israel"),
    max_age_hours: str = Form("72"),
    include_remote: str = Form(""),
    exclude_keywords: str = Form(""),
    blocked_companies: str = Form(""),
    results_wanted: str = Form("50"),
    min_salary: str = Form(""),
    session: Session = Depends(get_session),
):
    def _parse_csv(val: str) -> Optional[str]:
        tokens = [t.strip() for t in val.split(",") if t.strip()]
        return ", ".join(tokens) if tokens else None

    def _parse_int(val: str, default: int) -> int:
        try:
            return int(val) if val.strip() else default
        except ValueError:
            return default

    repo = JobRepository(session)
    repo.add_search_config(
        keywords=keywords,
        location=location,
        experience_level=experience_level or None,
        work_mode=work_mode or None,
        role_level=role_level or None,
        country=country or "israel",
        max_age_hours=_parse_int(max_age_hours, 72) if max_age_hours.strip() else None,
        include_remote=bool(include_remote),
        exclude_keywords=_parse_csv(exclude_keywords),
        blocked_companies=_parse_csv(blocked_companies),
        results_wanted=_parse_int(results_wanted, 50),
        min_salary=_parse_int(min_salary, 0) if min_salary.strip() else None,
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
    return JSONResponse(ScrapeStateResponse(
        running=bool(_scrape_status["running"]),
        error=_scrape_status.get("error"),
        last_result=last_result_model,
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
    from fastapi import HTTPException
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
