"""Response models for CV endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas_core import CVData


class CVListItem(BaseModel):
    id: int
    profile_url: str
    template_name: str
    generated_at: datetime


class CVExportResponse(BaseModel):
    cv_data: CVData
    profile_url: str


class TailoredCVResponse(BaseModel):
    job_id: int
    generated_at: datetime
    pdf_url: str
    docx_url: str
    model_used: str | None = None
    cv: CVData
