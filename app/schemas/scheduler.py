"""Response models for scheduler, scrape-state, and cleanup endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ScrapeLogResponse(BaseModel):
    id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    jobs_found: Optional[int] = None
    jobs_new: Optional[int] = None
    status: str
    error: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    is_enabled: bool
    interval_hours: int
    is_running: bool
    next_run: Optional[datetime] = None


class ScrapeLastResult(BaseModel):
    inserted: int
    skipped: int
    total_scraped: int


class CleanupResult(BaseModel):
    checked: int
    marked_inactive: int
    errors: int
    duration_ms: int


class ScrapeStateResponse(BaseModel):
    running: bool
    error: Optional[str] = None
    last_result: Optional[ScrapeLastResult] = None


class CleanupStateResponse(BaseModel):
    running: bool
    last_run_at: Optional[datetime] = None
    last_result: Optional[CleanupResult] = None


class SchedulerPageResponse(BaseModel):
    config: SchedulerStatusResponse
    scrape_logs: list[ScrapeLogResponse]
    cleanup_last_run_at: Optional[datetime] = None
    cleanup_last_result: Optional[CleanupResult] = None


class TaskStartedResponse(BaseModel):
    started: bool
    message: str


class SearchConfigResponse(BaseModel):
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


class ScrapePageResponse(BaseModel):
    latest_config: Optional[SearchConfigResponse] = None
    status: ScrapeStateResponse
