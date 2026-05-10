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
        "scraped_at": job.scraped_at.isoformat() if job.scraped_at else None,
        "sector": job.company_info.sector if job.company_info else None,
        "company_type": job.company_info.company_type if job.company_info else None,
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
