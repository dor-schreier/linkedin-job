"""Watch rules CRUD + notifications read/count endpoints."""
import html as html_lib
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_session
from app.repository import JobRepository

router = APIRouter()

ALLOWED_RULE_TYPES = {"company", "keyword", "sector"}


@router.post("/watch-rules/create")
def create_watch_rule(
    rule_type: Annotated[str, Form(...)],
    value: Annotated[str, Form(min_length=1, max_length=300)],
    db: Session = Depends(get_session),
):
    if rule_type not in ALLOWED_RULE_TYPES:
        return HTMLResponse(
            f'<div class="text-red-600">Invalid rule_type: {html_lib.escape(rule_type)}</div>',
            status_code=400,
        )
    repo = JobRepository(db)
    repo.add_watch_rule(rule_type=rule_type, value=value.strip(), is_active=True)
    return RedirectResponse("/watch-rules", status_code=303)


@router.post("/watch-rules/{rule_id}/toggle")
def toggle_watch_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    repo.toggle_watch_rule(rule_id)
    return RedirectResponse("/watch-rules", status_code=303)


@router.post("/watch-rules/{rule_id}/delete")
def delete_watch_rule(rule_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    repo.delete_watch_rule(rule_id)
    return RedirectResponse("/watch-rules", status_code=303)


@router.post("/notifications/mark-read")
def mark_notifications_read(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    count = repo.mark_notifications_read()
    return JSONResponse({"marked": count})


@router.get("/api/notifications/unread-count")
def unread_count(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    return JSONResponse({"count": repo.count_unread_notifications()})
