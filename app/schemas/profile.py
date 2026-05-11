"""Response/request models for profile and optimizer endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    linkedin_url: Optional[str] = None
    skills: Optional[str] = None
    current_title: Optional[str] = None
    target_title: Optional[str] = None
    years_experience: Optional[int] = None
    ai_recommendations: Optional[str] = None
    linkedin_analysis: Optional[str] = None
    linkedin_analyzed_at: Optional[datetime] = None


class ProfileSaveRequest(BaseModel):
    linkedin_url: Optional[str] = None
    skills: Optional[str] = None
    current_title: Optional[str] = None
    target_title: Optional[str] = None
    years_experience: Optional[int] = None


class KeywordGapItem(BaseModel):
    keyword: str
    count: int


class KeywordGapsResponse(BaseModel):
    gaps: list[KeywordGapItem]
    recommendation: Optional[str] = None
    total_jobs: int


class RecommendationsResponse(BaseModel):
    bullets: list[str]


class ProfileOptimizerResponse(BaseModel):
    linkedin_url: Optional[str] = None
    analysis: Optional[dict[str, Any]] = None
    analyzed_at: Optional[datetime] = None


class SearchConfigPageResponse(BaseModel):
    id: Optional[int] = None
    keywords: Optional[str] = None
    location: Optional[str] = None
    experience_level: Optional[str] = None
    work_mode: Optional[str] = None
    role_level: Optional[str] = None
    country: Optional[str] = None
    max_age_hours: Optional[int] = None
    include_remote: bool = False
    include_comeet: bool = False
    exclude_keywords: Optional[str] = None
    blocked_companies: Optional[str] = None
    results_wanted: int = 50
    min_salary: Optional[int] = None
