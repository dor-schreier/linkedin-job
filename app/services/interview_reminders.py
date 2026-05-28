"""Interview reminder service — enqueues Notification rows before scheduled interviews."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

REMINDER_WINDOWS = {
    'interview_reminder_3d': (2.5, 3.0),
    'interview_reminder_1d': (0.5, 1.0),
}


def enqueue_due_reminders(session: Session) -> int:
    from app.models import Interview, Notification

    now = datetime.utcnow()
    total = 0

    for kind, (lo_days, hi_days) in REMINDER_WINDOWS.items():
        lo = now + timedelta(days=lo_days)
        hi = now + timedelta(days=hi_days)

        interviews = (
            session.query(Interview)
            .filter(Interview.scheduled_at >= lo, Interview.scheduled_at <= hi)
            .all()
        )

        for interview in interviews:
            existing = (
                session.query(Notification)
                .filter(
                    Notification.interview_id == interview.id,
                    Notification.kind == kind,
                )
                .first()
            )
            if existing:
                continue

            hours_out = round((interview.scheduled_at - now).total_seconds() / 3600)
            iv_type = interview.interview_type.value if hasattr(interview.interview_type, 'value') else interview.interview_type
            label = iv_type.replace('_', ' ').title()
            message = f"Interview reminder: {label} in ~{hours_out}h"

            notif = Notification(
                job_id=interview.job_id,
                watch_rule_id=None,
                interview_id=interview.id,
                kind=kind,
                message=message,
                is_read=False,
            )
            session.add(notif)
            total += 1

    if total:
        session.commit()
        logger.info("Enqueued %d interview reminders", total)

    return total
