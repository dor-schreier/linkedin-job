"""Reject rules CRUD + manual unreject endpoints + settings page."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_session
from app.repository import JobRepository
from app.routes.pages import _ctx
from app.services import reject_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["fromjson"] = json.loads

ALLOWED_RULE_TYPES = {"location", "property", "title_keyword"}


@router.get("/settings/reject-rules", response_class=HTMLResponse)
def reject_rules_page(request: Request, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rules = repo.list_reject_rules()
    rule_counts = {r.id: repo.count_jobs_attributed_to_rule(r.id) for r in rules}
    locations = repo.get_all_distinct_locations()
    rejected_jobs = repo.list_rejected_jobs(limit=200)
    return templates.TemplateResponse(
        request,
        "reject_rules.html",
        _ctx(db, "reject-rules", {
            "rules": rules,
            "rule_counts": rule_counts,
            "locations": locations,
            "supported_properties": reject_service.SUPPORTED_PROPERTIES,
            "rejected_jobs": rejected_jobs,
        }),
    )


@router.get("/api/reject-rules")
def api_list_reject_rules(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rules = repo.list_reject_rules()
    out = []
    for r in rules:
        out.append({
            "id": r.id,
            "rule_type": r.rule_type,
            "property_name": r.property_name,
            "value": r.value,
            "is_enabled": r.is_enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "attributed_count": repo.count_jobs_attributed_to_rule(r.id),
        })
    return JSONResponse(out)


class CreateRuleBody(BaseModel):
    rule_type: str
    property_name: Optional[str] = None
    value: str


@router.post("/api/reject-rules")
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
    return JSONResponse({
        "rule": {
            "id": rule.id,
            "rule_type": rule.rule_type,
            "property_name": rule.property_name,
            "value": rule.value,
            "is_enabled": rule.is_enabled,
        },
        "affected_count": affected,
    })


@router.patch("/api/reject-rules/{rule_id}")
def api_toggle_reject_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    was_enabled = rule.is_enabled
    rule = repo.toggle_reject_rule(rule_id)
    if was_enabled and not rule.is_enabled:
        result = reject_service.reverse_rule_evaluation(db, rule)
    elif not was_enabled and rule.is_enabled:
        affected = reject_service.apply_rule_retroactive(db, rule)
        result = {"affected": affected}
    else:
        result = {}
    return JSONResponse({"rule_id": rule.id, "is_enabled": rule.is_enabled, **result})


@router.delete("/api/reject-rules/{rule_id}")
def api_delete_reject_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    result = reject_service.reverse_rule_evaluation(db, rule)
    repo.delete_reject_rule(rule_id)
    return JSONResponse({"deleted": rule_id, **result})


@router.get("/api/reject-rules/property-values")
def api_property_values(property: str, db: Session = Depends(get_session)):
    if property not in reject_service.SUPPORTED_PROPERTIES:
        raise HTTPException(status_code=422, detail=f"Unsupported property: {property}")
    repo = JobRepository(db)
    return JSONResponse({"values": repo.get_distinct_property_values(property)})


@router.get("/api/reject-rules/locations")
def api_reject_locations(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    return JSONResponse({"values": repo.get_all_distinct_locations()})


@router.post("/api/jobs/{job_id}/unreject")
def api_unreject_job(job_id: int, db: Session = Depends(get_session)):
    job = reject_service.manual_unreject(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({"job_id": job.id, "is_rejected": job.is_rejected})


@router.get("/api/jobs/{job_id}/reject-history")
def api_job_reject_history(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rows = repo.list_reject_audit_for_job(job_id)
    return JSONResponse([
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "rule_snapshot": json.loads(r.rule_snapshot_json) if r.rule_snapshot_json else None,
            "action": r.action,
            "actor": r.actor,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ])


# --- Form-based endpoints used by the settings page (HTMX-friendly redirects) ---

@router.post("/settings/reject-rules/create")
def form_create_rule(
    rule_type: str = Form(...),
    value: str = Form(...),
    property_name: Optional[str] = Form(None),
    db: Session = Depends(get_session),
):
    if rule_type not in ALLOWED_RULE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid rule_type: {rule_type}")
    repo = JobRepository(db)
    values = [v.strip() for v in value.split("\n") if v.strip()] if rule_type != "title_keyword" else [value.strip()]
    prop = property_name if rule_type == "property" else None
    if rule_type == "property" and (not prop or prop not in reject_service.SUPPORTED_PROPERTIES):
        raise HTTPException(status_code=422, detail="property_name required")
    for v in values:
        rule = repo.add_reject_rule(rule_type=rule_type, value=v, property_name=prop)
        reject_service.apply_rule_retroactive(db, rule)
    return RedirectResponse("/settings/reject-rules", status_code=303)


@router.post("/settings/reject-rules/{rule_id}/toggle")
def form_toggle_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    was_enabled = rule.is_enabled
    rule = repo.toggle_reject_rule(rule_id)
    if was_enabled and not rule.is_enabled:
        reject_service.reverse_rule_evaluation(db, rule)
    elif not was_enabled and rule.is_enabled:
        reject_service.apply_rule_retroactive(db, rule)
    return RedirectResponse("/settings/reject-rules", status_code=303)


@router.post("/settings/reject-rules/{rule_id}/delete")
def form_delete_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.get_reject_rule(rule_id)
    if not rule:
        return RedirectResponse("/settings/reject-rules", status_code=303)
    reject_service.reverse_rule_evaluation(db, rule)
    repo.delete_reject_rule(rule_id)
    return RedirectResponse("/settings/reject-rules", status_code=303)


@router.post("/settings/reject-rules/jobs/{job_id}/unreject")
def form_unreject_job(job_id: int, db: Session = Depends(get_session)):
    reject_service.manual_unreject(db, job_id)
    return RedirectResponse("/settings/reject-rules", status_code=303)
