"""Cleanup service: re-checks job URLs and marks posts inactive when gone."""
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_cleanup_lock = threading.Lock()
_cleanup_status: dict = {
    "running": False,
    "last_run_at": None,
    "last_result": None,
}

_INACTIVE_PHRASES = [
    "no longer accepting applications",
    "this job is no longer available",
    "job has been removed",
    "posting has been removed",
    "job is closed",
    "position has been filled",
]


def check_job_active(apply_url: str) -> str:
    """Fetch apply_url and return 'active', 'inactive', or 'unknown' (network/rate-limit errors)."""
    if not apply_url:
        return "unknown"
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            resp = client.get(
                apply_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobChecker/1.0)"},
            )
        if resp.status_code in (404, 410):
            return "inactive"
        if resp.status_code >= 500:
            return "unknown"
        body = resp.text.lower()
        for phrase in _INACTIVE_PHRASES:
            if phrase in body:
                return "inactive"
        return "active"
    except Exception as exc:
        logger.debug("check_job_active error for %s: %s", apply_url, exc)
        return "unknown"


def run_cleanup() -> dict:
    """Check all active jobs; mark inactive ones. Returns {checked, marked_inactive, errors, duration_ms}."""
    from app.database import SessionLocal
    from app.repository import JobRepository

    start = time.monotonic()
    checked = 0
    marked_inactive = 0
    errors = 0

    with SessionLocal() as session:
        repo = JobRepository(session)
        jobs = repo.list_active_jobs_for_cleanup()

    logger.info("Cleanup starting: %d active jobs to check", len(jobs))

    for i, job in enumerate(jobs):
        if i > 0 and i % 20 == 0:
            logger.info("Cleanup progress: %d/%d checked", i, len(jobs))

        result = check_job_active(job.apply_url)
        now = datetime.now(timezone.utc)
        checked += 1

        with SessionLocal() as session:
            repo = JobRepository(session)
            if result == "inactive":
                repo.mark_job_inactive(job.id, checked_at=now)
                marked_inactive += 1
                logger.info("Marked inactive: job_id=%d", job.id)
            elif result == "unknown":
                errors += 1
                repo.update_job_checked_at(job.id, checked_at=now)
            else:
                repo.update_job_checked_at(job.id, checked_at=now)

        if i < len(jobs) - 1:
            time.sleep(1.0)

    duration_ms = int((time.monotonic() - start) * 1000)
    summary = {
        "checked": checked,
        "marked_inactive": marked_inactive,
        "errors": errors,
        "duration_ms": duration_ms,
    }
    logger.info("Cleanup done: %s", summary)
    return summary


def _run_cleanup_task() -> None:
    """Internal: acquire lock, run cleanup, update status, release lock."""
    try:
        _cleanup_status["running"] = True
        result = run_cleanup()
        _cleanup_status["last_result"] = result
        _cleanup_status["last_run_at"] = datetime.now(timezone.utc)
    except Exception as exc:
        logger.error("Cleanup error: %s", exc, exc_info=True)
        _cleanup_status["last_result"] = None
    finally:
        _cleanup_status["running"] = False
        _cleanup_lock.release()


def run_cleanup_now() -> bool:
    """Trigger cleanup in a background thread. Returns False if already running."""
    if not _cleanup_lock.acquire(blocking=False):
        return False
    t = threading.Thread(target=_run_cleanup_task, daemon=True)
    t.start()
    return True


def get_cleanup_status() -> dict:
    return dict(_cleanup_status)
