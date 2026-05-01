"""CV export & generation router."""
from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal, get_session
from app.repository import JobRepository
from app.schemas import CVData, LinkedInProfile
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cv"])
templates = Jinja2Templates(directory="app/templates")


def _get_repo(session: Session = Depends(get_session)) -> JobRepository:
    return JobRepository(session)


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/cv/export", response_class=HTMLResponse)
def cv_export_page(request: Request):
    with SessionLocal() as session:
        repo = JobRepository(session)
        cvs = repo.list_cvs()
        unread = repo.count_unread_notifications()
    return templates.TemplateResponse(
        request,
        "cv_export.html",
        {"cvs": cvs, "active": "cv-export", "unread_count": unread},
    )


@router.get("/cv/view", response_class=HTMLResponse)
def cv_view_page(request: Request, profile_url: str):
    profile_url = unquote(profile_url)
    with SessionLocal() as session:
        repo = JobRepository(session)
        record = repo.get_latest_cv(profile_url)
        unread = repo.count_unread_notifications()
    if not record:
        raise HTTPException(status_code=404, detail="CV not found")
    cv = CVData(**json.loads(record.cv_json))
    return templates.TemplateResponse(
        request,
        "cv_view.html",
        {"cv": cv, "profile_url": profile_url, "active": "cv-export", "unread_count": unread},
    )


# ── Export (scrape + build + save) ────────────────────────────────────────────

@router.post("/cv/export")
def cv_export(
    request: Request,
    source: str = Form("scrape"),
    profile_url: str = Form(""),
    rewrite_bullets: Optional[str] = Form(None),
):
    """Scrape a LinkedIn profile, build CV data, persist it, redirect to view page."""
    do_rewrite = rewrite_bullets is not None  # checkbox is present = checked

    if not profile_url:
        with SessionLocal() as session:
            repo = JobRepository(session)
            cvs = repo.list_cvs()
            unread = repo.count_unread_notifications()
        return templates.TemplateResponse(
            request,
            "cv_export.html",
            {"cvs": cvs, "active": "cv-export",
             "unread_count": unread, "error": "Profile URL is required."},
            status_code=422,
        )

    try:
        from app.scraper import scrape_linkedin_profile, LinkedInAuthError
        profile = scrape_linkedin_profile(profile_url)
    except Exception as exc:
        logger.error("LinkedIn scrape failed for %s: %s", profile_url, exc)
        with SessionLocal() as session:
            repo = JobRepository(session)
            cvs = repo.list_cvs()
            unread = repo.count_unread_notifications()
        return templates.TemplateResponse(
            request,
            "cv_export.html",
            {"cvs": cvs, "active": "cv-export",
             "unread_count": unread, "error": str(exc)},
            status_code=422,
        )

    return _build_and_save_cv(profile, do_rewrite)


@router.post("/cv/import-zip", response_class=HTMLResponse)
async def cv_import_zip(request: Request, zip_file: UploadFile = File(...)):
    """Import a LinkedIn data-export ZIP and generate a CV from the CSVs inside."""
    import io
    import zipfile
    from scripts.import_linkedin_zip import parse_linkedin_zip

    content = await zip_file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
        profile = parse_linkedin_zip(zf)
    except Exception as exc:
        logger.error("ZIP import failed: %s", exc)
        with SessionLocal() as session:
            repo = JobRepository(session)
            cvs = repo.list_cvs()
            unread = repo.count_unread_notifications()
        return templates.TemplateResponse(
            request,
            "cv_export.html",
            {"cvs": cvs, "active": "cv-export",
             "unread_count": unread, "error": f"ZIP import error: {exc}"},
            status_code=422,
        )

    return _build_and_save_cv(profile, rewrite_bullets=True)


def _build_and_save_cv(profile: LinkedInProfile, rewrite_bullets: bool = True) -> RedirectResponse:
    from app.services.cv_builder import build_cv_from_profile

    cv = build_cv_from_profile(profile, rewrite_bullets=rewrite_bullets)

    with SessionLocal() as session:
        repo = JobRepository(session)
        repo.upsert_profile_raw(profile.profile_url, profile.model_dump())
        repo.save_cv(profile.profile_url, cv.model_dump())

    from urllib.parse import quote
    return RedirectResponse(url=f"/cv/view?profile_url={quote(profile.profile_url, safe='')}", status_code=303)


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/cv/api/export")
def api_cv_export(
    profile_url: str,
    rewrite_bullets: bool = True,
):
    """API: scrape + build + save, returns CVData JSON."""
    from app.scraper import scrape_linkedin_profile
    from app.services.cv_builder import build_cv_from_profile

    profile = scrape_linkedin_profile(profile_url)
    cv = build_cv_from_profile(profile, rewrite_bullets=rewrite_bullets)

    with SessionLocal() as session:
        repo = JobRepository(session)
        repo.upsert_profile_raw(profile.profile_url, profile.model_dump())
        repo.save_cv(profile.profile_url, cv.model_dump())

    return cv.model_dump()


@router.get("/cv/api/{profile_url:path}/json")
def api_cv_json(profile_url: str):
    """API: return latest saved CVData as JSON."""
    with SessionLocal() as session:
        repo = JobRepository(session)
        record = repo.get_latest_cv(profile_url)
    if not record:
        raise HTTPException(status_code=404, detail="CV not found for this profile URL")
    return JSONResponse(content=json.loads(record.cv_json))


@router.get("/cv/download/pdf")
def cv_download_pdf(profile_url: str):
    """Return the latest CV as a downloadable PDF."""
    profile_url = unquote(profile_url)
    with SessionLocal() as session:
        repo = JobRepository(session)
        record = repo.get_latest_cv(profile_url)
    if not record:
        raise HTTPException(status_code=404, detail="CV not found")

    cv = CVData(**json.loads(record.cv_json))
    from app.services.cv_renderer import render_cv_pdf
    pdf_bytes = render_cv_pdf(cv)

    safe_name = cv.full_name.replace(" ", "_") or "cv"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_CV.pdf"'},
    )


@router.get("/cv/download/json")
def cv_download_json(profile_url: str):
    """Return the latest CV as a downloadable JSON file."""
    profile_url = unquote(profile_url)
    with SessionLocal() as session:
        repo = JobRepository(session)
        record = repo.get_latest_cv(profile_url)
    if not record:
        raise HTTPException(status_code=404, detail="CV not found")

    cv = CVData(**json.loads(record.cv_json))
    from app.services.cv_renderer import render_cv_json
    data = render_cv_json(cv)

    safe_name = cv.full_name.replace(" ", "_") or "cv"
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_CV.json"'},
    )


@router.get("/cv/list")
def cv_list():
    """API: list all saved CVs."""
    with SessionLocal() as session:
        repo = JobRepository(session)
        records = repo.list_cvs()
    return [
        {
            "id": r.id,
            "profile_url": r.profile_url,
            "template_name": r.template_name,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in records
    ]
