"""Response models for reject-rule endpoints."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class RejectRuleListItem(BaseModel):
    id: int
    rule_type: str
    property_name: Optional[str] = None
    value: str
    is_enabled: bool
    created_at: Optional[str] = None
    attributed_count: int = 0


class RejectRuleCreated(BaseModel):
    id: int
    rule_type: str
    property_name: Optional[str] = None
    value: str
    is_enabled: bool


class CreateRejectRuleResponse(BaseModel):
    rule: RejectRuleCreated
    affected_count: int


class ToggleRuleResponse(BaseModel):
    rule_id: int
    is_enabled: bool
    affected: Optional[int] = None
    reversed: Optional[int] = None


class DeleteRuleResponse(BaseModel):
    deleted: int
    reversed: Optional[int] = None


class PropertyValuesResponse(BaseModel):
    values: list[str]


class UnrejectJobResponse(BaseModel):
    job_id: int
    is_rejected: bool


class RejectHistoryEntry(BaseModel):
    id: int
    rule_id: Optional[int] = None
    rule_snapshot: Optional[Any] = None
    action: str
    actor: str
    created_at: Optional[str] = None
