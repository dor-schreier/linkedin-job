"""Pydantic schemas for interview endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class InterviewCreate(BaseModel):
    scheduled_at: datetime
    interview_type: str  # first_hr | initial | technical | final_hr
    medium: str          # phone | zoom | in_person
    location: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode='after')
    def require_location_for_in_person(self) -> 'InterviewCreate':
        if self.medium == 'in_person' and not (self.location or '').strip():
            raise ValueError('location is required for in-person interviews')
        return self


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    interview_type: Optional[str] = None
    medium: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode='after')
    def require_location_for_in_person(self) -> 'InterviewUpdate':
        if self.medium == 'in_person' and self.location is not None and not self.location.strip():
            raise ValueError('location is required for in-person interviews')
        return self


class InterviewResponse(BaseModel):
    id: int
    job_id: int
    scheduled_at: datetime
    interview_type: str
    medium: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
