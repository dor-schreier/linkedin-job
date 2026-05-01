"""APScheduler service — recurring scrape jobs using AsyncIOScheduler."""
import logging
import threading
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_scrape_lock = threading.Lock()

JOB_ID = "scheduled_scrape"
CLEANUP_JOB_ID = "scheduled_cleanup"


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _run_scheduled_scrape() -> None:
    """Synchronous function called by APScheduler — runs all active SearchConfigs."""
    if not _scrape_lock.acquire(blocking=False):
        logger.info("Scheduled scrape skipped — previous scrape still running")
        return

    try:
        from app.database import SessionLocal
        from app.repository import JobRepository
        from app.scraper import run_scrape

        with SessionLocal() as session:
            repo = JobRepository(session)
            configs = repo.list_search_configs(active_only=True)

        if not configs:
            logger.info("Scheduled scrape: no active search configs, skipping")
            return

        logger.info("Scheduled scrape starting: %d config(s)", len(configs))

        for i, config in enumerate(configs):
            if i > 0:
                import time
                time.sleep(10)  # stagger configs to respect LinkedIn rate limits

            with SessionLocal() as session:
                repo = JobRepository(session)
                log = repo.create_scrape_log(config_id=config.id)
                log_id = log.id

            logger.info(
                "Scheduled scrape config %d/%d: keywords=%r location=%r",
                i + 1, len(configs), config.keywords, config.location,
            )

            result = run_scrape(config=config)

            with SessionLocal() as session:
                repo = JobRepository(session)
                if "error" in result:
                    repo.finish_scrape_log(log_id, jobs_found=0, jobs_new=0, error=result["error"])
                    logger.error("Scheduled scrape config %d failed: %s", config.id, result["error"])
                else:
                    repo.finish_scrape_log(
                        log_id,
                        jobs_found=result.get("total_scraped", 0),
                        jobs_new=result.get("inserted", 0),
                    )
                    logger.info(
                        "Scheduled scrape config %d done: found=%d new=%d",
                        config.id,
                        result.get("total_scraped", 0),
                        result.get("inserted", 0),
                    )

    except Exception as e:
        logger.error("Scheduled scrape error: %s", e, exc_info=True)
    finally:
        _scrape_lock.release()


def _run_scheduled_cleanup() -> None:
    """Called by APScheduler daily — runs the URL-check cleanup."""
    from app.services.cleanup_service import _cleanup_lock, _run_cleanup_task
    if not _cleanup_lock.acquire(blocking=False):
        logger.info("Scheduled cleanup skipped — previous cleanup still running")
        return
    _run_cleanup_task()


def start_scheduler(interval_hours: int = 6) -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        return
    scheduler.add_job(
        _run_scheduled_scrape,
        trigger=IntervalTrigger(hours=interval_hours),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _run_scheduled_cleanup,
        trigger=IntervalTrigger(hours=24),
        id=CLEANUP_JOB_ID,
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started: interval=%dh", interval_hours)


def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def reschedule(interval_hours: int) -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        return
    scheduler.reschedule_job(
        JOB_ID,
        trigger=IntervalTrigger(hours=interval_hours),
    )
    logger.info("Scheduler rescheduled: interval=%dh", interval_hours)


def get_next_run_time():
    scheduler = get_scheduler()
    if not scheduler.running:
        return None
    job = scheduler.get_job(JOB_ID)
    return job.next_run_time if job else None


def is_running() -> bool:
    scheduler = get_scheduler()
    return scheduler.running


def run_now() -> bool:
    """Trigger an immediate scrape in a background thread. Returns False if already running."""
    if not _scrape_lock.acquire(blocking=False):
        return False
    _scrape_lock.release()

    import threading
    t = threading.Thread(target=_run_scheduled_scrape, daemon=True)
    t.start()
    return True
