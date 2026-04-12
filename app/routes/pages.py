from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_session
from app.repository import JobRepository
from app.services import groq_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/search-config", response_class=HTMLResponse)
def search_config(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    configs = repo.list_search_configs(active_only=True)
    latest_config = configs[-1] if configs else None
    from app.routes.scrape import _scrape_status
    return templates.TemplateResponse(
        request,
        "search_config.html",
        {"latest_config": latest_config, "status": _scrape_status},
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    bullets = _split_bullets(profile.ai_recommendations) if profile and profile.ai_recommendations else []
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"profile": profile, "bullets": bullets},
    )


@router.post("/profile")
def profile_save(
    linkedin_url: str = Form(""),
    skills: str = Form(""),
    current_title: str = Form(""),
    target_title: str = Form(""),
    years_experience: Optional[str] = Form(None),
    db: Session = Depends(get_session),
):
    years_int: Optional[int] = None
    if years_experience:
        try:
            years_int = int(years_experience)
        except ValueError:
            years_int = None
    repo = JobRepository(db)
    repo.upsert_profile(
        linkedin_url=linkedin_url or None,
        skills=skills or None,
        current_title=current_title or None,
        target_title=target_title or None,
        years_experience=years_int,
    )
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/analyze", response_class=HTMLResponse)
def profile_analyze(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    if not profile or not any([
        profile.linkedin_url,
        profile.skills,
        profile.current_title,
        profile.target_title,
        profile.years_experience,
    ]):
        return HTMLResponse(
            '<p class="text-sm text-gray-500">Save your profile first to get AI recommendations.</p>'
        )
    bullets = groq_service.get_profile_recommendations(profile)
    if bullets:
        repo.upsert_profile(ai_recommendations="\n".join(bullets))
        profile = repo.get_profile()
    return templates.TemplateResponse(
        request,
        "partials/ai_insights.html",
        {"bullets": bullets or _split_bullets(profile.ai_recommendations)},
    )


@router.get("/watch-rules", response_class=HTMLResponse)
def watch_rules_page(request: Request):
    return templates.TemplateResponse(request, "watch_rules.html")


def _split_bullets(text: Optional[str]) -> list:
    if not text:
        return []
    return [line.lstrip("- ").strip() for line in text.splitlines() if line.strip()]
