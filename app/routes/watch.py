"""Watch rules CRUD + notifications endpoints (JSON API)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.schemas.watch import (
    CreateWatchRuleRequest,
    MarkReadResponse,
    NotificationCountResponse,
    WatchMatchRow,
    WatchMatchesResponse,
    WatchRuleResponse,
)

router = APIRouter()

ALLOWED_RULE_TYPES = {"company", "keyword", "sector"}


@router.get("/watch-rules", response_model=list[WatchRuleResponse], tags=["watch-rules"])
def list_watch_rules(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rules = repo.list_watch_rules(active_only=False)
    return JSONResponse([
        WatchRuleResponse(
            id=r.id,
            rule_type=r.rule_type,
            value=r.value,
            is_active=r.is_active,
            created_at=r.created_at,
        ).model_dump(mode="json")
        for r in rules
    ])


@router.post("/watch-rules", response_model=WatchRuleResponse, tags=["watch-rules"])
def create_watch_rule(body: CreateWatchRuleRequest, db: Session = Depends(get_session)):
    if body.rule_type not in ALLOWED_RULE_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid rule_type: {body.rule_type}")
    value = body.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="value required")
    repo = JobRepository(db)
    rule = repo.add_watch_rule(rule_type=body.rule_type, value=value, is_active=True)
    return JSONResponse(WatchRuleResponse(
        id=rule.id, rule_type=rule.rule_type, value=rule.value,
        is_active=rule.is_active, created_at=rule.created_at,
    ).model_dump(mode="json"), status_code=201)


@router.patch("/watch-rules/{rule_id}", response_model=WatchRuleResponse, tags=["watch-rules"])
def toggle_watch_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    rule = repo.toggle_watch_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return JSONResponse(WatchRuleResponse(
        id=rule.id, rule_type=rule.rule_type, value=rule.value,
        is_active=rule.is_active, created_at=rule.created_at,
    ).model_dump(mode="json"))


@router.delete("/watch-rules/{rule_id}", status_code=204, tags=["watch-rules"])
def delete_watch_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    repo.delete_watch_rule(rule_id)
    return Response(status_code=204)


@router.get("/watch-matches", response_model=WatchMatchesResponse, tags=["watch-rules"])
def list_watch_matches(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    unread = repo.list_unread_notifications_with_jobs()
    unread_ids = [n.id for n, _j, _r in unread]
    if unread_ids:
        repo.mark_notifications_read()
    rows_raw = repo.list_all_notifications_with_jobs(limit=200)
    rows = [
        WatchMatchRow(
            notification_id=notif.id,
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            rule_type=rule.rule_type if rule else None,
            rule_value=rule.value if rule else None,
            kind=getattr(notif, 'kind', 'watch_match') or 'watch_match',
            message=getattr(notif, 'message', None),
            is_read=notif.is_read,
            created_at=notif.created_at,
        )
        for notif, job, rule in rows_raw
    ]
    return JSONResponse(WatchMatchesResponse(rows=rows).model_dump(mode="json"))


@router.post("/notifications/mark-read", response_model=MarkReadResponse, tags=["notifications"])
def mark_notifications_read(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    count = repo.mark_notifications_read()
    return JSONResponse(MarkReadResponse(marked=count).model_dump())


@router.get("/notifications/unread-count", response_model=NotificationCountResponse, tags=["notifications"])
def unread_count(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    return JSONResponse(NotificationCountResponse(count=repo.count_unread_notifications()).model_dump())
