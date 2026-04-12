"""Watch-rule matching service. Runs after a scrape inserts new jobs."""
import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Job, WatchRule
from app.repository import JobRepository

logger = logging.getLogger(__name__)


def _matches(rule: WatchRule, job: Job) -> bool:
    """Case-insensitive match. company=exact on Job.company; keyword=substring on Job.title;
    sector=substring on Job.description (no sector column exists in schema)."""
    if not rule.value:
        return False
    needle = rule.value.strip().lower()
    if rule.rule_type == "company":
        return (job.company or "").strip().lower() == needle
    if rule.rule_type == "keyword":
        return needle in (job.title or "").lower()
    if rule.rule_type == "sector":
        return needle in (job.description or "").lower()
    return False


def match_new_jobs_to_watch_rules(session: Session, new_job_ids: list[int]) -> int:
    """For every (active watch rule, job in new_job_ids) pair that matches,
    create a Notification. Skips pairs where a Notification already exists.
    Returns number of notifications created."""
    if not new_job_ids:
        return 0
    repo = JobRepository(session)
    rules = repo.list_watch_rules(active_only=True)
    if not rules:
        return 0
    jobs = repo.get_jobs_by_ids(new_job_ids)
    created = 0
    for job in jobs:
        for rule in rules:
            if not _matches(rule, job):
                continue
            if repo.notification_exists(job.id, rule.id):
                continue
            repo.add_notification(job_id=job.id, watch_rule_id=rule.id)
            created += 1
    logger.info("Watch matching: %d notifications created for %d new jobs against %d rules",
                created, len(jobs), len(rules))
    return created
