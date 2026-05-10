"""JSON API endpoints for profile, search-config, and profile-optimizer pages."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.schemas.profile import (
    KeywordGapItem,
    KeywordGapsResponse,
    ProfileOptimizerResponse,
    ProfileResponse,
    ProfileSaveRequest,
    RecommendationsResponse,
    SearchConfigPageResponse,
)
from app.services import llm_service as groq_service

router = APIRouter()


@router.get("/api/profile", response_model=ProfileResponse, tags=["profile"])
def api_get_profile(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    if not profile:
        return JSONResponse(ProfileResponse().model_dump(mode="json"))
    return JSONResponse(ProfileResponse(
        linkedin_url=profile.linkedin_url,
        skills=profile.skills,
        current_title=profile.current_title,
        target_title=profile.target_title,
        years_experience=profile.years_experience,
        ai_recommendations=profile.ai_recommendations,
        linkedin_analysis=profile.linkedin_analysis,
        linkedin_analyzed_at=profile.linkedin_analyzed_at,
    ).model_dump(mode="json"))


@router.put("/api/profile", response_model=ProfileResponse, tags=["profile"])
def api_save_profile(body: ProfileSaveRequest, db: Session = Depends(get_session)):
    years_int: Optional[int] = None
    if body.years_experience is not None:
        years_int = body.years_experience
    repo = JobRepository(db)
    profile = repo.upsert_profile(
        linkedin_url=body.linkedin_url or None,
        skills=body.skills or None,
        current_title=body.current_title or None,
        target_title=body.target_title or None,
        years_experience=years_int,
    )
    return JSONResponse(ProfileResponse(
        linkedin_url=profile.linkedin_url,
        skills=profile.skills,
        current_title=profile.current_title,
        target_title=profile.target_title,
        years_experience=profile.years_experience,
        ai_recommendations=profile.ai_recommendations,
        linkedin_analysis=profile.linkedin_analysis,
        linkedin_analyzed_at=profile.linkedin_analyzed_at,
    ).model_dump(mode="json"))


@router.post("/api/profile/analyze", response_model=RecommendationsResponse, tags=["profile"])
def api_analyze_profile(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    if not profile or not any([
        profile.linkedin_url,
        profile.skills,
        profile.current_title,
        profile.target_title,
        profile.years_experience,
    ]):
        raise HTTPException(status_code=422, detail="Save your profile first to get AI recommendations.")
    bullets = groq_service.get_profile_recommendations(profile) or []
    if bullets:
        repo.upsert_profile(ai_recommendations="\n".join(bullets))
    return JSONResponse(RecommendationsResponse(bullets=bullets).model_dump())


@router.get("/api/profile/keyword-gaps", response_model=KeywordGapsResponse, tags=["profile"])
def api_keyword_gaps(db: Session = Depends(get_session)):
    from app.services.analysis_service import compute_keyword_gaps, get_gap_recommendations
    repo = JobRepository(db)
    profile = repo.get_profile()
    jobs = repo.get_jobs_with_intelligence(days=30)
    profile_skills = (profile.skills or "") if profile else ""
    gaps = compute_keyword_gaps(jobs, profile_skills)
    recommendation = get_gap_recommendations(gaps) if gaps else None
    gap_items = [KeywordGapItem(keyword=g["keyword"], count=g["count"]) for g in gaps]
    return JSONResponse(KeywordGapsResponse(
        gaps=gap_items,
        recommendation=recommendation,
        total_jobs=len(jobs),
    ).model_dump())


@router.get("/api/profile-optimizer", response_model=ProfileOptimizerResponse, tags=["profile"])
def api_profile_optimizer(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    analysis = None
    analyzed_at = None
    if profile and profile.linkedin_analysis:
        try:
            analysis = json.loads(profile.linkedin_analysis)
        except (json.JSONDecodeError, ValueError):
            analysis = None
        analyzed_at = profile.linkedin_analyzed_at
    return JSONResponse(ProfileOptimizerResponse(
        linkedin_url=profile.linkedin_url if profile else None,
        analysis=analysis,
        analyzed_at=analyzed_at,
    ).model_dump(mode="json"))


@router.post("/api/profile-optimizer/analyze", response_model=ProfileOptimizerResponse, tags=["profile"])
def api_profile_optimizer_analyze(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    profile = repo.get_profile()
    if not profile or not any([
        profile.linkedin_url,
        profile.skills,
        profile.current_title,
        profile.target_title,
        profile.years_experience,
    ]):
        raise HTTPException(
            status_code=422,
            detail="Save your profile content on the Profile page before analyzing.",
        )
    result = groq_service.get_linkedin_profile_analysis(profile)
    if not result.get("sections"):
        raise HTTPException(status_code=502, detail="Analysis failed. Check your Groq API key and try again.")
    repo.upsert_profile_analysis(json.dumps(result))
    profile = repo.get_profile()
    return JSONResponse(ProfileOptimizerResponse(
        linkedin_url=profile.linkedin_url if profile else None,
        analysis=result,
        analyzed_at=profile.linkedin_analyzed_at if profile else None,
    ).model_dump(mode="json"))


@router.get("/api/search-config", response_model=SearchConfigPageResponse, tags=["search-config"])
def api_search_config(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    cfg = repo.get_active_search_config()
    if not cfg:
        return JSONResponse(SearchConfigPageResponse().model_dump(mode="json"))
    return JSONResponse(SearchConfigPageResponse(
        id=cfg.id,
        keywords=cfg.keywords,
        location=cfg.location,
        experience_level=cfg.experience_level,
        work_mode=cfg.work_mode,
        role_level=cfg.role_level,
        country=cfg.country,
        max_age_hours=cfg.max_age_hours,
        include_remote=bool(cfg.include_remote),
        exclude_keywords=cfg.exclude_keywords,
        blocked_companies=cfg.blocked_companies,
        results_wanted=cfg.results_wanted or 50,
        min_salary=cfg.min_salary,
    ).model_dump(mode="json"))
