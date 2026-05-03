"""Response models for job-related endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.schemas_core import FitScoreBreakdown, JobIntelligence


class HeroStats(BaseModel):
    total_jobs: int
    new_since_last_visit: int
    high_match_count: int
    unscored_count: int
    scraper_running: bool
    last_scrape_at: Optional[datetime] = None
    last_scrape_inserted: Optional[int] = None
    last_scrape_skipped: Optional[int] = None


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None
    source: str
    apply_url: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    status: str
    fit_score: Optional[int] = None
    fit_summary: Optional[str] = None
    date_posted: Optional[date] = None
    user_rating: Optional[int] = None
    is_active: bool
    is_rejected: bool
    scraped_at: datetime
    sector: Optional[str] = None
    company_type: Optional[str] = None
    required_skills: list[str] = []
    tech_stack: list[str] = []

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v: object) -> str:
        return v.value if hasattr(v, "value") else str(v)


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    has_more: bool
    stats: HeroStats


class JobDetailResponse(JobResponse):
    description: Optional[str] = None
    company_summary: Optional[str] = None
    intelligence: Optional[JobIntelligence] = None
    breakdown: Optional[FitScoreBreakdown] = None


class JobScoreResponse(BaseModel):
    job_id: int
    fit_score: Optional[int] = None
    fit_summary: Optional[str] = None
    breakdown: Optional[FitScoreBreakdown] = None


class JobIntelligenceResponse(BaseModel):
    job_id: int
    intelligence: Optional[JobIntelligence] = None
    error: Optional[str] = None


class JobStatusUpdateResponse(BaseModel):
    job_id: int
    status: str


class ScrapeRunningResponse(BaseModel):
    running: bool
