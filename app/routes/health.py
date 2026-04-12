import os
import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_session
from app.routes.pages import _ctx

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def health(request: Request, db: Session = Depends(get_session)):
    db_exists = os.path.exists("data/jobs.db")
    table_count = 0
    wal_mode = False
    if db_exists:
        try:
            conn = sqlite3.connect("data/jobs.db")
            tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            table_count = tables
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            wal_mode = mode == "wal"
        finally:
            conn.close()
    return templates.TemplateResponse(request, "health.html", _ctx(db, "health", {
        "status": "ok",
        "db_exists": db_exists,
        "table_count": table_count,
        "wal_mode": wal_mode,
    }))
