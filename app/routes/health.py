import os
import sqlite3

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session

router = APIRouter()


@router.get("/health", tags=["health"])
def health_json(db: Session = Depends(get_session)):
    from app.services.llm_service import check_llm_health
    db_exists = os.path.exists("data/jobs.db")
    table_count = 0
    wal_mode = False
    if db_exists:
        try:
            conn = sqlite3.connect("data/jobs.db")
            table_count = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            wal_mode = mode == "wal"
        finally:
            conn.close()
    llm = check_llm_health()
    return {
        "status": "ok",
        "db_exists": db_exists,
        "table_count": table_count,
        "wal_mode": wal_mode,
        "llm_ok": llm["ok"],
        "llm_provider": llm["provider"],
        "llm_model": llm["model"],
        "llm_error": llm["error"],
    }
