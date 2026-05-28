import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Job, JobStatus
from app.repository import JobRepository
from app.schemas.jobs import (
    HeroStats,
    JobDetailResponse,
    JobIntelligenceResponse,
    JobListResponse,
    JobResponse,
    JobScoreResponse,
    JobStatusUpdateResponse,
    ScrapeRunningResponse,
)
from app.services import llm_service as groq_service

router = APIRouter()

PAGE_SIZE = 50


def _fit_label(score):
    if score is None:
        return ""
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Poor"


def _urgency_tier(job) -> Optional[str]:
    if job.date_posted is None:
        return None
    from datetime import date
    age_days = (date.today() - job.date_posted).days
    if age_days < 1:
        return "Fresh"
    if age_days <= 2:
        return "Apply Soon"
    return "Late"


def _nonempty(value: Optional[str]) -> Optional[str]:
    """Return value unless it is falsy or the literal string 'unknown'."""
    if not value or value.strip().lower() == "unknown":
        return None
    return value


def _days_since_posted(job) -> Optional[int]:
    if job.date_posted is None:
        return None
    from datetime import date
    return (date.today() - job.date_posted).days


def _job_to_response_dict(job) -> dict:
    intelligence = {}
    if job.intelligence_json:
        try:
            intelligence = json.loads(job.intelligence_json)
        except (json.JSONDecodeError, ValueError):
            pass
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "apply_url": job.apply_url,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "status": job.status.value if job.status else None,
        "fit_score": job.fit_score,
        "fit_summary": job.fit_summary,
        "date_posted": job.date_posted.isoformat() if job.date_posted else None,
        "user_rating": job.user_rating,
        "is_active": job.is_active,
        "is_rejected": job.is_rejected,
        "applied_at": job.applied_at.isoformat() if job.applied_at else None,
        "scraped_at": job.scraped_at.isoformat() if job.scraped_at else None,
        "sector": (_nonempty(job.company_info.sector) if job.company_info else None),
        "company_type": (_nonempty(job.company_info.company_type) if job.company_info else None),
        "required_skills": intelligence.get("required_skills") or [],
        "tech_stack": intelligence.get("tech_stack") or [],
        "days_since_posted": _days_since_posted(job),
    }


@router.get("/jobs", response_model=JobListResponse, tags=["jobs"])
def jobs_list(
    request: Request,
    status: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    salary_min: Optional[str] = None,
    sort: Optional[str] = None,
    fresh_only: Optional[str] = None,
    hide_rated: Optional[str] = None,
    sector: Optional[str] = None,
    company_type: Optional[str] = None,
    source: Optional[str] = None,
    show_inactive: Optional[str] = None,
    include_rejected: Optional[str] = None,
    q: Optional[str] = None,
    title_include: Optional[str] = None,
    title_exclude: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_session),
):
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")

    repo = JobRepository(db)

    rated_only = False
    status_enum: Optional[JobStatus] = None
    if status:
        if status.lower() == "rated":
            rated_only = True
        else:
            try:
                status_enum = JobStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid status: {status}")

    salary_min_f: Optional[float] = None
    if salary_min:
        try:
            salary_min_f = float(salary_min)
        except ValueError:
            raise HTTPException(status_code=422, detail="salary_min must be numeric")

    company_list = [c.strip() for c in company.split(",") if c.strip()] if company else None
    location_list = [l.strip() for l in location.split(",") if l.strip()] if location else None
    sector_list = [s.strip() for s in sector.split(",") if s.strip()] if sector else None
    title_include_list = [t.strip() for t in title_include.split(",") if t.strip()] if title_include else None
    title_exclude_list = [t.strip() for t in title_exclude.split(",") if t.strip()] if title_exclude else None

    fresh_only_bool = fresh_only == "1"
    hide_rated_bool = hide_rated == "1"
    show_inactive_bool = show_inactive == "1"
    include_rejected_bool = include_rejected == "1"
    sort_val = sort if sort in ("freshest", "fit_desc", "fit_asc", "rating_desc", "date_posted_asc") else None

    offset = (page - 1) * PAGE_SIZE
    jobs = repo.list_jobs(
        status=status_enum,
        company=company_list,
        location=location_list,
        salary_min_filter=salary_min_f,
        fresh_only=fresh_only_bool,
        sort=sort_val,
        sector=sector_list,
        company_type=company_type or None,
        source=source or None,
        rated_only=rated_only,
        hide_rated=hide_rated_bool,
        show_inactive=show_inactive_bool,
        include_rejected=include_rejected_bool,
        search_text=q or None,
        title_include=title_include_list,
        title_exclude=title_exclude_list,
        limit=PAGE_SIZE,
        offset=offset,
    )
    total = repo.count_jobs_filtered(
        status=status_enum,
        company=company_list,
        location=location_list,
        salary_min_filter=salary_min_f,
        fresh_only=fresh_only_bool,
        sector=sector_list,
        company_type=company_type or None,
        source=source or None,
        rated_only=rated_only,
        hide_rated=hide_rated_bool,
        show_inactive=show_inactive_bool,
        include_rejected=include_rejected_bool,
        search_text=q or None,
        title_include=title_include_list,
        title_exclude=title_exclude_list,
    )
    has_more = (offset + PAGE_SIZE) < total

    now = datetime.now(timezone.utc)
    last_visit_ts: Optional[datetime] = None
    last_visit_raw = request.cookies.get("last_visit")
    if last_visit_raw:
        try:
            last_visit_ts = datetime.fromisoformat(last_visit_raw)
            if last_visit_ts.tzinfo is None:
                last_visit_ts = last_visit_ts.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    total_jobs = repo.count_active_jobs()
    high_match_count = repo.count_high_match_jobs(min_score=90)
    unscored_count = repo.count_unscored_jobs()
    new_since_last_visit = repo.count_new_since(last_visit_ts) if last_visit_ts else total_jobs

    from app.routes.scrape import _scrape_status
    scraper_running = _scrape_status.get("running", False)
    last_result = _scrape_status.get("last_result")

    latest_log = repo.get_latest_scrape_log()
    last_scrape_at = None
    if latest_log:
        last_scrape_at = latest_log.finished_at or latest_log.started_at

    stats = {
        "total_jobs": total_jobs,
        "new_since_last_visit": new_since_last_visit,
        "high_match_count": high_match_count,
        "unscored_count": unscored_count,
        "scraper_running": scraper_running,
        "last_scrape_at": last_scrape_at,
        "last_scrape_inserted": last_result.get("inserted") if last_result else None,
        "last_scrape_skipped": last_result.get("skipped") if last_result else None,
    }

    response = JSONResponse(JobListResponse(
        jobs=[JobResponse(**_job_to_response_dict(j)) for j in jobs],
        total=total,
        page=page,
        has_more=has_more,
        stats=HeroStats(**stats),
    ).model_dump(mode="json"))
    response.set_cookie("last_visit", now.isoformat(), max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


@router.post("/jobs/{job_id}/score", response_model=JobScoreResponse, tags=["jobs"])
def score_job(job_id: int, db: Session = Depends(get_session)):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = repo.get_profile()
    if not profile or not any([
        profile.linkedin_url,
        profile.skills,
        profile.current_title,
        profile.target_title,
        profile.years_experience,
    ]):
        raise HTTPException(status_code=422, detail="Save your profile first to score jobs.")

    jd_intelligence = None
    if job.intelligence_json:
        try:
            jd_intelligence = json.loads(job.intelligence_json)
        except (json.JSONDecodeError, ValueError):
            pass

    breakdown = groq_service.get_enhanced_fit_score(job, profile, jd_intelligence=jd_intelligence)
    if breakdown is not None:
        job_summary_data = breakdown.get("job_summary")
        score_to_store = {k: v for k, v in breakdown.items() if k != "job_summary"}
        repo.update_job_score_breakdown(
            job_id=job.id,
            score_breakdown_json=json.dumps(score_to_store),
            fit_score=int(breakdown["overall_score"]),
            fit_summary=breakdown["summary"],
        )
        if job_summary_data:
            repo.update_job_summary(
                job_id=job.id,
                tech_stack_json=json.dumps(job_summary_data.get("tech_stack", [])),
                qualifications_json=json.dumps(job_summary_data.get("qualifications", [])),
                experience_needed=job_summary_data.get("experience_needed"),
                general_description=job_summary_data.get("general_description"),
            )
    else:
        result = groq_service.get_fit_score_and_salary(job, profile)
        if result.get("fit_score") is not None:
            repo.update_job_scores(
                job_id=job.id,
                fit_score=int(result["fit_score"]),
                fit_summary=result.get("fit_summary") or "",
                salary_estimated=result.get("salary_estimated"),
            )

    job = repo.get_job(job_id)
    breakdown_data = None
    if job.score_breakdown_json:
        try:
            breakdown_data = json.loads(job.score_breakdown_json)
        except (json.JSONDecodeError, ValueError):
            pass

    from app.schemas_core import FitScoreBreakdown
    bd_model = FitScoreBreakdown(**breakdown_data) if breakdown_data else None
    return JSONResponse(JobScoreResponse(
        job_id=job_id,
        fit_score=job.fit_score,
        fit_summary=job.fit_summary,
        breakdown=bd_model,
    ).model_dump(mode="json"))


@router.get("/jobs/scrape-status", response_model=ScrapeRunningResponse, tags=["jobs"])
def jobs_scrape_status():
    from app.routes.scrape import _scrape_status
    return JSONResponse({"running": bool(_scrape_status.get("running", False))})


@router.get("/jobs/tracker", tags=["jobs"])
def get_tracker_jobs(db: Session = Depends(get_session)):
    """Return all jobs in tracker statuses (saved/applied/interviewing/offer/rejected) with next interview."""
    repo = JobRepository(db)
    pairs = repo.list_jobs_for_tracker()

    def _iv_dict(iv):
        return {
            "id": iv.id,
            "scheduled_at": iv.scheduled_at.isoformat(),
            "interview_type": iv.interview_type.value if hasattr(iv.interview_type, 'value') else iv.interview_type,
            "medium": iv.medium.value if hasattr(iv.medium, 'value') else iv.medium,
            "location": iv.location,
            "notes": iv.notes,
        }

    result = []
    for job, iv in pairs:
        d = _job_to_response_dict(job)
        d['next_interview'] = _iv_dict(iv) if iv else None
        result.append(d)
    return JSONResponse(result)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse, tags=["jobs"])
def job_detail(job_id: int, db: Session = Depends(get_session)):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    intelligence = None
    if job.intelligence_json:
        try:
            intelligence = json.loads(job.intelligence_json)
        except (json.JSONDecodeError, ValueError):
            pass
    breakdown = None
    if job.score_breakdown_json:
        try:
            breakdown = json.loads(job.score_breakdown_json)
        except (json.JSONDecodeError, ValueError):
            pass

    from app.schemas_core import FitScoreBreakdown, JobIntelligence
    intel_model = None
    if intelligence:
        try:
            intel_model = JobIntelligence(**intelligence)
        except Exception:
            pass
    bd_model = None
    if breakdown:
        try:
            bd_model = FitScoreBreakdown(**breakdown)
        except Exception:
            pass
    company_summary = job.company_info.what_they_do if job.company_info else None
    detail = {**_job_to_response_dict(job), "description": job.description, "company_summary": company_summary}
    return JSONResponse(JobDetailResponse(
        **detail,
        intelligence=intel_model,
        breakdown=bd_model,
    ).model_dump(mode="json"))


@router.post("/jobs/{job_id}/reextract", response_model=JobIntelligenceResponse, tags=["jobs"])
def reextract_job_intelligence(job_id: int, db: Session = Depends(get_session)):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = groq_service.extract_job_intelligence(job)
    error = None
    if result is not None:
        job.intelligence_json = json.dumps(result)
        db.commit()
    else:
        error = "Extraction failed. Check your Groq API key or try again."

    from app.schemas_core import JobIntelligence
    intel_model = None
    if result:
        try:
            intel_model = JobIntelligence(**result)
        except Exception:
            pass
    return JSONResponse(JobIntelligenceResponse(
        job_id=job_id, intelligence=intel_model, error=error,
    ).model_dump(mode="json"))


_AUTH_SIGNALS = ["sign in to", "log in to", "create an account", "authwall", "join now"]
_CLOSED_SIGNALS = ["no longer accepting applications", "this job is no longer available", "כבר לא מקבלים מועמדים"]


def _extract_page(html: str) -> tuple[Optional[str], bool]:
    """Parse HTML and return (description_text, is_active).

    is_active is False when the page signals the job is closed.
    description_text is None when the page looks like an auth wall or has no content.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    full_text_lower = soup.get_text(separator=" ", strip=True).lower()

    is_active = not any(sig in full_text_lower for sig in _CLOSED_SIGNALS)

    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for selector in ["#job-details", ".jobs-description__content", ".jobs-description",
                     "[class*='jobDescriptionContent']", "[class*='job-description']",
                     "article", "main"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text[:6000], is_active
    text = soup.get_text(separator="\n", strip=True)
    if len(text) < 200 or any(kw in text.lower() for kw in _AUTH_SIGNALS):
        return None, is_active
    return text[:6000], is_active


def _fetch_via_requests(url: str, timeout_s: int) -> tuple[Optional[str], Optional[bool]]:
    """Returns (text, is_active) or (None, None) on failure."""
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)
        if resp.status_code != 200:
            return None, None
        return _extract_page(resp.text)
    except Exception:
        return None, None


def _fetch_via_playwright_linkedin(url: str) -> tuple[Optional[str], Optional[bool]]:
    """Fetch a LinkedIn job page using Playwright + li_at session cookie."""
    import os
    import time
    import logging
    session_cookie = os.getenv("LINKEDIN_SESSION_COOKIE", "")
    logger = logging.getLogger(__name__)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            if session_cookie:
                context.add_cookies([{
                    "name": "li_at",
                    "value": session_cookie,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }])
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            if "authwall" in page.url or "login" in page.url:
                browser.close()
                logger.warning("LinkedIn refresh blocked — set LINKEDIN_SESSION_COOKIE in .env")
                return None, None
            html = page.content()
            browser.close()
        return _extract_page(html)
    except Exception as e:
        logger.warning("Playwright LinkedIn fetch failed: %s", e)
        return None, None


def _fetch_description_from_url(url: str, timeout_s: int = 15) -> tuple[Optional[str], Optional[bool]]:
    """Fetch job description from apply_url. Returns (text, is_active).

    LinkedIn is always fetched via Playwright (JS-rendered; plain requests returns a stub
    that lacks both the description and the 'no longer accepting' signal).
    """
    if "linkedin.com" in url:
        return _fetch_via_playwright_linkedin(url)
    return _fetch_via_requests(url, timeout_s)


@router.post("/jobs/{job_id}/refresh", tags=["jobs"])
def refresh_job(job_id: int, db: Session = Depends(get_session)):
    """Re-fetch description from apply_url, then re-extract intelligence and re-score."""
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    errors: list[str] = []
    description_updated = False
    intelligence_updated = False
    score_updated = False

    if job.apply_url:
        new_desc, is_active = _fetch_description_from_url(job.apply_url)
        if new_desc:
            job.description = new_desc
            description_updated = True
        if is_active is False and job.is_active:
            job.is_active = False
        if new_desc or is_active is False:
            db.commit()

    intel_result = groq_service.extract_job_intelligence(job)
    if intel_result is not None:
        job.intelligence_json = json.dumps(intel_result)
        db.commit()
        intelligence_updated = True
    else:
        errors.append("Intelligence extraction failed")

    profile = repo.get_profile()
    if profile:
        breakdown = groq_service.get_enhanced_fit_score(job, profile, jd_intelligence=intel_result)
        if breakdown is not None:
            job_summary = breakdown.get("job_summary")
            score_to_store = {k: v for k, v in breakdown.items() if k != "job_summary"}
            repo.update_job_score_breakdown(
                job_id=job.id,
                score_breakdown_json=json.dumps(score_to_store),
                fit_score=int(breakdown["overall_score"]),
                fit_summary=breakdown["summary"],
            )
            if job_summary:
                repo.update_job_summary(
                    job_id=job.id,
                    tech_stack_json=json.dumps(job_summary.get("tech_stack", [])),
                    qualifications_json=json.dumps(job_summary.get("qualifications", [])),
                    experience_needed=job_summary.get("experience_needed"),
                    general_description=job_summary.get("general_description"),
                )
            score_updated = True
        else:
            errors.append("Scoring failed")

    return JSONResponse({
        "job_id": job_id,
        "description_updated": description_updated,
        "intelligence_updated": intelligence_updated,
        "score_updated": score_updated,
        "error": "; ".join(errors) if errors else None,
    })


class RateJobRequest(BaseModel):
    rating: Optional[int] = None


@router.patch("/jobs/{job_id}/rate", status_code=204, tags=["jobs"])
def rate_job(job_id: int, body: RateJobRequest, db: Session = Depends(get_session)):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    if body.rating is not None and body.rating not in range(1, 6):
        raise HTTPException(status_code=422, detail="rating must be 1-5 or null")
    repo = JobRepository(db)
    job = repo.update_job_rating(job_id, body.rating)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return Response(status_code=204)


class JobStatusPatchRequest(BaseModel):
    status: str


@router.patch("/jobs/{job_id}/status", response_model=JobStatusUpdateResponse, tags=["jobs"])
def patch_job_status(job_id: int, body: JobStatusPatchRequest, db: Session = Depends(get_session)):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    try:
        status_enum = JobStatus(body.status.lower())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status value: {body.status}")
    repo = JobRepository(db)
    job = repo.update_job_status(job_id, status_enum)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(JobStatusUpdateResponse(job_id=job_id, status=body.status).model_dump())


@router.post("/jobs/{job_id}/status", response_model=JobStatusUpdateResponse, tags=["jobs"])
def update_job_status(
    job_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_session),
):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    try:
        status_enum = JobStatus(status.lower())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status value: {status}")
    repo = JobRepository(db)
    job = repo.update_job_status(job_id, status_enum)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(JobStatusUpdateResponse(job_id=job_id, status=status).model_dump())
