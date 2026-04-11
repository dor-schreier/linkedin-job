from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/search-config", response_class=HTMLResponse)
def search_config(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    configs = repo.list_search_configs(active_only=True)
    latest_config = configs[-1] if configs else None
    from app.routes.scrape import _scrape_status
    return templates.TemplateResponse(
        "search_config.html",
        {"request": request, "latest_config": latest_config, "status": _scrape_status},
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})


@router.get("/watch-rules", response_class=HTMLResponse)
def watch_rules_page(request: Request):
    return templates.TemplateResponse("watch_rules.html", {"request": request})
