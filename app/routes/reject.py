"""Reject rules CRUD + manual unreject endpoints (JSON API only)."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.schemas.reject import (
    CreateRejectRuleResponse,
    DeleteRuleResponse,
    PropertyValuesResponse,
    RejectHistoryEntry,
    RejectRuleCreated,
    RejectRuleListItem,
    ToggleRuleResponse,
    UnrejectJobResponse,
)
from app.services import reject_service

router = APIRouter()

ALLOWED_RULE_TYPES = {"location", "property", "title_keyword"}


@router.get("/reject-rules", response_model=list[RejectRuleListItem], tags=["reject-rules"])
def api_list_reject_rules(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rules = repo.list_reject_rules()
    return JSONResponse([
        RejectRuleListItem(
            id=r.id,
            rule_type=r.rule_type,
            property_name=r.property_name,
            value=r.value,
            is_enabled=r.is_enabled,
            created_at=r.created_at.isoformat() if r.created_at else None,
            attributed_count=repo.count_jobs_attributed_to_rule(r.id),
        ).model_dump()
        for r in rules
    ])


class CreateRuleBody(BaseModel):
    rule_type: str
    property_name: Optional[str] = None
    value: str


@router.post("/reject-rules", response_model=CreateRejectRuleResponse, tags=["reject-rules"])
def api_create_reject_rule(body: CreateRuleBody, db: Session = Depends(get_session)):
    if body.rule_type not in ALLOWED_RULE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid rule_type: {body.rule_type}")
    value = (body.value or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="value required")
    prop = body.property_name
    if body.rule_type == "property":
        if not prop or prop not in reject_service.SUPPORTED_PROPERTIES:
            raise HTTPException(status_code=422, detail=f"property_name must be one of {reject_service.SUPPORTED_PROPERTIES}")
    else:
        prop = None
    repo = JobRepository(db)
    rule = repo.add_reject_rule(rule_type=body.rule_type, value=value, property_name=prop)
    affected = reject_service.apply_rule_retroactive(db, rule)
    return JSONResponse(CreateRejectRuleResponse(
        rule=RejectRuleCreated(
            id=rule.id,
            rule_type=rule.rule_type,
            property_name=rule.property_name,
            value=rule.value,
            is_enabled=rule.is_enabled,
        ),
        affected_count=affected,
    ).model_dump())


@router.patch("/reject-rules/{rule_id}", response_model=ToggleRuleResponse, tags=["reject-rules"])
def api_toggle_reject_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    was_enabled = rule.is_enabled
    rule = repo.toggle_reject_rule(rule_id)
    affected: Optional[int] = None
    reversed_count: Optional[int] = None
    if was_enabled and not rule.is_enabled:
        result = reject_service.reverse_rule_evaluation(db, rule)
        reversed_count = result.get("reversed")
    elif not was_enabled and rule.is_enabled:
        affected = reject_service.apply_rule_retroactive(db, rule)
    return JSONResponse(ToggleRuleResponse(
        rule_id=rule.id,
        is_enabled=rule.is_enabled,
        affected=affected,
        reversed=reversed_count,
    ).model_dump())


@router.delete("/reject-rules/{rule_id}", response_model=DeleteRuleResponse, tags=["reject-rules"])
def api_delete_reject_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    result = reject_service.reverse_rule_evaluation(db, rule)
    repo.delete_reject_rule(rule_id)
    return JSONResponse(DeleteRuleResponse(
        deleted=rule_id,
        reversed=result.get("reversed"),
    ).model_dump())


@router.get("/reject-rules/property-values", response_model=PropertyValuesResponse, tags=["reject-rules"])
def api_property_values(property: str, db: Session = Depends(get_session)):
    if property not in reject_service.SUPPORTED_PROPERTIES:
        raise HTTPException(status_code=422, detail=f"Unsupported property: {property}")
    repo = JobRepository(db)
    return JSONResponse(PropertyValuesResponse(values=repo.get_distinct_property_values(property)).model_dump())


@router.get("/reject-rules/locations", response_model=PropertyValuesResponse, tags=["reject-rules"])
def api_reject_locations(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    return JSONResponse(PropertyValuesResponse(values=repo.get_all_distinct_locations()).model_dump())


@router.post("/jobs/{job_id}/unreject", response_model=UnrejectJobResponse, tags=["reject-rules"])
def api_unreject_job(job_id: int, db: Session = Depends(get_session)):
    job = reject_service.manual_unreject(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(UnrejectJobResponse(job_id=job.id, is_rejected=job.is_rejected).model_dump())


@router.get("/jobs/{job_id}/reject-history", response_model=list[RejectHistoryEntry], tags=["reject-rules"])
def api_job_reject_history(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rows = repo.list_reject_audit_for_job(job_id)
    return JSONResponse([
        RejectHistoryEntry(
            id=r.id,
            rule_id=r.rule_id,
            rule_snapshot=json.loads(r.rule_snapshot_json) if r.rule_snapshot_json else None,
            action=r.action,
            actor=r.actor,
            created_at=r.created_at.isoformat() if r.created_at else None,
        ).model_dump()
        for r in rows
    ])
