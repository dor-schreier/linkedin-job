"""Reject-by service — rule matching, retroactive scan, prospective evaluation."""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Company, Job, ManualOverride, RejectAuditLog, RejectRule


SUPPORTED_PROPERTIES = ["company", "source", "sector", "company_type"]


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _rule_snapshot(rule: RejectRule) -> str:
    return json.dumps({
        "rule_type": rule.rule_type,
        "property_name": rule.property_name,
        "value": rule.value,
    })


def _job_field_for_property(session: Session, job: Job, property_name: str) -> Optional[str]:
    if property_name in ("company", "source"):
        return getattr(job, property_name, None)
    if property_name in ("sector", "company_type"):
        if not job.company_id:
            return None
        co = session.get(Company, job.company_id)
        return getattr(co, property_name, None) if co else None
    return None


def _title_keyword_regex(keyword: str) -> re.Pattern:
    escaped = re.escape(keyword.strip())
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def rule_matches_job(session: Session, rule: RejectRule, job: Job) -> bool:
    if not rule.is_enabled:
        return False
    if rule.rule_type == "location":
        return _norm(job.location) == _norm(rule.value)
    if rule.rule_type == "property":
        if not rule.property_name:
            return False
        field_val = _job_field_for_property(session, job, rule.property_name)
        return _norm(field_val) == _norm(rule.value)
    if rule.rule_type == "title_keyword":
        if not job.title:
            return False
        return _title_keyword_regex(rule.value).search(job.title) is not None
    return False


def find_first_matching_rule(session: Session, job: Job, rules: Optional[list[RejectRule]] = None) -> Optional[RejectRule]:
    if rules is None:
        rules = (
            session.query(RejectRule)
            .filter(RejectRule.is_enabled == True)  # noqa: E712
            .order_by(RejectRule.id.asc())
            .all()
        )
    for r in rules:
        if rule_matches_job(session, r, job):
            return r
    return None


def is_manually_overridden(session: Session, job_id: int) -> bool:
    return session.query(ManualOverride).filter(ManualOverride.job_id == job_id).first() is not None


def evaluate_job_on_insert(session: Session, job: Job) -> Optional[RejectRule]:
    """Evaluate rules against a newly inserted job. Set rejection state and audit log.
    Returns the matching rule (if any). Caller is responsible for the surrounding commit."""
    if is_manually_overridden(session, job.id):
        return None
    rule = find_first_matching_rule(session, job)
    if rule is None:
        return None
    job.is_rejected = True
    job.rejected_at = datetime.now(timezone.utc)
    job.rejected_by_rule_id = rule.id
    session.add(RejectAuditLog(
        job_id=job.id,
        rule_id=rule.id,
        rule_snapshot_json=_rule_snapshot(rule),
        action="rejected",
        actor="system",
    ))
    session.commit()
    return rule


def apply_rule_retroactive(session: Session, rule: RejectRule) -> int:
    """Scan all non-rejected, non-overridden jobs and reject those matching this rule.
    Returns count of jobs flipped to rejected."""
    if not rule.is_enabled:
        return 0
    overridden_ids = {row[0] for row in session.query(ManualOverride.job_id).all()}
    candidates = (
        session.query(Job)
        .filter(Job.is_rejected == False)  # noqa: E712
        .all()
    )
    affected = 0
    now = datetime.now(timezone.utc)
    for job in candidates:
        if job.id in overridden_ids:
            continue
        if rule_matches_job(session, rule, job):
            job.is_rejected = True
            job.rejected_at = now
            job.rejected_by_rule_id = rule.id
            session.add(RejectAuditLog(
                job_id=job.id,
                rule_id=rule.id,
                rule_snapshot_json=_rule_snapshot(rule),
                action="rejected",
                actor="system",
            ))
            affected += 1
    session.commit()
    return affected


def reverse_rule_evaluation(session: Session, rule: RejectRule) -> dict:
    """Called when a rule is disabled or deleted. For each job currently attributed to
    the rule, re-evaluate against remaining enabled rules. Repoint or unreject as needed.
    Returns counts: {repointed, unrejected}."""
    other_rules = (
        session.query(RejectRule)
        .filter(RejectRule.is_enabled == True, RejectRule.id != rule.id)  # noqa: E712
        .order_by(RejectRule.id.asc())
        .all()
    )
    attributed_jobs = (
        session.query(Job)
        .filter(Job.rejected_by_rule_id == rule.id)
        .all()
    )
    repointed = 0
    unrejected = 0
    for job in attributed_jobs:
        match = find_first_matching_rule(session, job, rules=other_rules)
        if match is not None:
            job.rejected_by_rule_id = match.id
            repointed += 1
        else:
            job.is_rejected = False
            job.rejected_at = None
            job.rejected_by_rule_id = None
            session.add(RejectAuditLog(
                job_id=job.id,
                rule_id=rule.id,
                rule_snapshot_json=_rule_snapshot(rule),
                action="unrejected",
                actor="system",
            ))
            unrejected += 1
    session.commit()
    return {"repointed": repointed, "unrejected": unrejected}


def manual_unreject(session: Session, job_id: int) -> Optional[Job]:
    job = session.get(Job, job_id)
    if not job:
        return None
    rule_id = job.rejected_by_rule_id
    snapshot = None
    if rule_id:
        rule = session.get(RejectRule, rule_id)
        if rule:
            snapshot = _rule_snapshot(rule)
    job.is_rejected = False
    job.rejected_at = None
    job.rejected_by_rule_id = None
    session.add(RejectAuditLog(
        job_id=job.id,
        rule_id=rule_id,
        rule_snapshot_json=snapshot,
        action="unrejected",
        actor="user",
    ))
    if not is_manually_overridden(session, job_id):
        session.add(ManualOverride(job_id=job_id))
    session.commit()
    return job
