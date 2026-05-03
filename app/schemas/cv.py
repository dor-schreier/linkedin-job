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
