"""Response models for watch rules and notification endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WatchRuleResponse(BaseModel):
    id: int
    rule_type: str
    value: str
    is_active: bool
    created_at: datetime


class WatchMatchRow(BaseModel):
    notification_id: int
    job_id: int
    job_title: str
    company: str
    location: Optional[str] = None
    rule_type: Optional[str] = None
    rule_value: Optional[str] = None
    kind: str = 'watch_match'
    message: Optional[str] = None
    is_read: bool
    created_at: datetime


class WatchMatchesResponse(BaseModel):
    rows: list[WatchMatchRow]


class CreateWatchRuleRequest(BaseModel):
    rule_type: str
    value: str


class NotificationCountResponse(BaseModel):
    count: int


class MarkReadResponse(BaseModel):
    marked: int
