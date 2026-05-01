"""Scrape routes — search config form, background task trigger, HTMX status polling."""
import html as html_lib
import threading
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.routes.pages import _ctx
from app.scraper import run_scrape

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Module-level scrape state — single background task at a time
_scrape_lock = threading.Lock()
_scrape_status: dict = {"running": False, "last_result": None, "error": None}


def _run_scrape_task(config) -> None:
    """Background task: runs the scrape and updates _scrape_status."""
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


@router.get("/scrape", response_class=HTMLResponse)
def scrape_page(request: Request, session: Session = Depends(get_session)):
    repo = JobRepository(session)
    configs = repo.list_search_configs(active_only=True)
    latest_config = configs[-1] if configs else None
    return templates.TemplateResponse(
        request,
        "scrape.html",
        _ctx(session, "scrape", {"latest_config": latest_config, "status": _scrape_status}),
    )


@router.post("/scrape/run", response_class=HTMLResponse)
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
        """Trim whitespace from each CSV token; return None if empty."""
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
    # Detach from session so background task can safely read scalar attributes
    session.expunge(config)

    if not _scrape_lock.acquire(blocking=False):
        return HTMLResponse(
            '<div id="scrape-result" class="text-yellow-600">A scrape is already running.</div>'
        )

    _scrape_status["running"] = True
    _scrape_status["error"] = None
    background_tasks.add_task(_run_scrape_task, config)
    return HTMLResponse(
        '<div id="scrape-result" hx-get="/scrape/status" hx-trigger="every 2s" hx-swap="outerHTML"'
        ' class="text-blue-600">Scrape started...</div>'
    )


@router.post("/scrape/save-config", response_class=HTMLResponse)
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
    return HTMLResponse(
        '<div id="scrape-result" class="text-green-600">Config saved.</div>'
    )


@router.get("/scrape/status", response_class=HTMLResponse)
def scrape_status():
    if _scrape_status["running"]:
        return HTMLResponse(
            '<div id="scrape-result" hx-get="/scrape/status" hx-trigger="every 2s" hx-swap="outerHTML"'
            ' class="text-blue-600 animate-pulse">Scraping in progress...</div>'
        )
    if _scrape_status["error"]:
        error = html_lib.escape(_scrape_status["error"])
        return HTMLResponse(
            f'<div id="scrape-result" class="text-red-600">Error: {error}</div>'
        )
    if _scrape_status["last_result"]:
        r = _scrape_status["last_result"]
        inserted = r.get("inserted", 0)
        skipped = r.get("skipped", 0)
        total_scraped = r.get("total_scraped", 0)
        return HTMLResponse(
            f'<div id="scrape-result" class="text-green-600">'
            f"Done! Inserted {inserted}, skipped {skipped} (from {total_scraped} scraped)"
            f"</div>"
        )
    return HTMLResponse(
        '<div id="scrape-result" class="text-gray-500">No scrape run yet.</div>'
    )


# ── Scheduler endpoints ──────────────────────────────────────────────────────

@router.get("/scheduler", response_class=HTMLResponse)
def scheduler_page(request: Request, session: Session = Depends(get_session)):
    from app.repository import JobRepository
    from app.services import scheduler as sched_service
    from app.services.cleanup_service import get_cleanup_status
    repo = JobRepository(session)
    cfg = repo.get_scheduler_config()
    logs = repo.list_scrape_logs(limit=10)
    next_run = sched_service.get_next_run_time()
    cleanup_status = get_cleanup_status()
    return templates.TemplateResponse(
        request,
        "scheduler.html",
        _ctx(session, "scheduler", {
            "scheduler_cfg": cfg,
            "scheduler_running": sched_service.is_running(),
            "next_run": next_run,
            "scrape_logs": logs,
            "cleanup_last_run_at": cleanup_status.get("last_run_at"),
            "cleanup_last_result": cleanup_status.get("last_result"),
        }),
    )


@router.post("/scheduler/toggle", response_class=HTMLResponse)
def scheduler_toggle(request: Request, session: Session = Depends(get_session)):
    from app.repository import JobRepository
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
    return templates.TemplateResponse(
        request,
        "partials/scheduler_status.html",
        {"scheduler_cfg": cfg, "scheduler_running": sched_service.is_running(), "next_run": next_run},
    )


@router.post("/scheduler/run-now", response_class=HTMLResponse)
def scheduler_run_now(request: Request, session: Session = Depends(get_session)):
    from app.services import scheduler as sched_service
    started = sched_service.run_now()
    if not started:
        return HTMLResponse(
            '<p class="text-yellow-400 text-sm">A scrape is already running.</p>'
        )
    return HTMLResponse(
        '<p class="text-green-400 text-sm">Manual scrape started — check logs shortly.</p>'
    )


@router.post("/cleanup/run", response_class=HTMLResponse)
def cleanup_run_now(request: Request):
    from app.services.cleanup_service import run_cleanup_now
    started = run_cleanup_now()
    if not started:
        return HTMLResponse('<p class="text-yellow-400 text-sm">Cleanup is already running.</p>')
    return HTMLResponse(
        '<span id="cleanup-result" hx-get="/cleanup/status" hx-trigger="every 3s" hx-swap="outerHTML"'
        ' class="text-primary text-sm animate-pulse">Cleanup started…</span>'
    )


@router.get("/cleanup/status", response_class=HTMLResponse)
def cleanup_status_poll(request: Request):
    from app.services.cleanup_service import get_cleanup_status
    status = get_cleanup_status()
    if status["running"]:
        return HTMLResponse(
            '<span id="cleanup-result" hx-get="/cleanup/status" hx-trigger="every 3s" hx-swap="outerHTML"'
            ' class="text-primary text-sm animate-pulse">Cleanup running…</span>'
        )
    result = status.get("last_result")
    last_run = status.get("last_run_at")
    if result:
        dur_s = result["duration_ms"] // 1000
        msg = (
            f'Checked {result["checked"]} · '
            f'Marked inactive {result["marked_inactive"]} · '
            f'Errors {result["errors"]} · '
            f'{dur_s}s'
        )
        return HTMLResponse(f'<span id="cleanup-result" class="text-green-400 text-sm">{msg}</span>')
    return HTMLResponse('<span id="cleanup-result" class="text-outline text-sm">No cleanup run yet.</span>')


@router.post("/scheduler/config", response_class=HTMLResponse)
def scheduler_update_config(
    request: Request,
    interval_hours: int = Form(...),
    session: Session = Depends(get_session),
):
    from app.repository import JobRepository
    from app.services import scheduler as sched_service
    if interval_hours < 1 or interval_hours > 168:
        return HTMLResponse('<p class="text-error text-sm">Interval must be 1–168 hours.</p>')
    repo = JobRepository(session)
    repo.update_scheduler_config(interval_hours=interval_hours)
    if sched_service.is_running():
        sched_service.reschedule(interval_hours)
    cfg = repo.get_scheduler_config()
    next_run = sched_service.get_next_run_time()
    return templates.TemplateResponse(
        request,
        "partials/scheduler_status.html",
        {"scheduler_cfg": cfg, "scheduler_running": sched_service.is_running(), "next_run": next_run},
    )
