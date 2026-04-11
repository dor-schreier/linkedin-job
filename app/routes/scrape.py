"""Scrape routes — search config form, background task trigger, HTMX status polling."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.scraper import run_scrape

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Module-level scrape state — single background task at a time
_scrape_status: dict = {"running": False, "last_result": None, "error": None}


def _run_scrape_task(keywords: str, location: str, experience_level: Optional[str]) -> None:
    """Background task: runs the scrape and updates _scrape_status."""
    global _scrape_status
    _scrape_status["running"] = True
    _scrape_status["error"] = None
    try:
        result = run_scrape(keywords=keywords, location=location, experience_level=experience_level)
        if "error" in result:
            _scrape_status["error"] = result["error"]
            _scrape_status["last_result"] = None
        else:
            _scrape_status["last_result"] = result
    except Exception as e:
        _scrape_status["error"] = str(e)
    finally:
        _scrape_status["running"] = False


@router.get("/scrape", response_class=HTMLResponse)
def scrape_page(request: Request, session: Session = Depends(get_session)):
    repo = JobRepository(session)
    configs = repo.list_search_configs(active_only=True)
    latest_config = configs[-1] if configs else None
    return templates.TemplateResponse(
        request,
        "scrape.html",
        {"request": request, "latest_config": latest_config, "status": _scrape_status},
    )


@router.post("/scrape/run", response_class=HTMLResponse)
def scrape_run(
    background_tasks: BackgroundTasks,
    keywords: str = Form(...),
    location: str = Form(...),
    experience_level: str = Form(""),
    work_mode: str = Form(""),
    session: Session = Depends(get_session),
):
    repo = JobRepository(session)
    repo.add_search_config(
        keywords=keywords,
        location=location,
        experience_level=experience_level or None,
        work_mode=work_mode or None,
        is_active=True,
    )

    if _scrape_status["running"]:
        return HTMLResponse(
            '<div id="scrape-result" class="text-yellow-600">A scrape is already running.</div>'
        )

    background_tasks.add_task(_run_scrape_task, keywords, location, experience_level or None)
    return HTMLResponse(
        '<div id="scrape-result" hx-get="/scrape/status" hx-trigger="every 2s" hx-swap="outerHTML"'
        ' class="text-blue-600">Scrape started...</div>'
    )


@router.get("/scrape/status", response_class=HTMLResponse)
def scrape_status():
    if _scrape_status["running"]:
        return HTMLResponse(
            '<div id="scrape-result" hx-get="/scrape/status" hx-trigger="every 2s" hx-swap="outerHTML"'
            ' class="text-blue-600 animate-pulse">Scraping in progress...</div>'
        )
    if _scrape_status["error"]:
        error = _scrape_status["error"]
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
