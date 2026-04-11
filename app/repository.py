from typing import Optional

from sqlalchemy.orm import Session

from app.models import Job, JobStatus, Notification, Profile, SearchConfig, WatchRule


class JobRepository:
    """Encapsulates all database access. No raw SQL should exist outside this class."""

    def __init__(self, session: Session):
        self.session = session

    # --- Jobs ---

    def add_job(self, **kwargs) -> Job:
        """Insert a job. Caller must provide job_hash. Returns the created Job."""
        job = Job(**kwargs)
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job_by_hash(self, job_hash: str) -> Optional[Job]:
        return self.session.query(Job).filter(Job.job_hash == job_hash).first()

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        q = self.session.query(Job)
        if status:
            q = q.filter(Job.status == status)
        return q.order_by(Job.scraped_at.desc()).offset(offset).limit(limit).all()

    def update_job_status(self, job_id: int, status: JobStatus) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.status = status
            self.session.commit()
            self.session.refresh(job)
        return job

    def count_jobs(self) -> int:
        return self.session.query(Job).count()

    # --- Profile ---

    def get_profile(self) -> Optional[Profile]:
        return self.session.query(Profile).first()

    def upsert_profile(self, **kwargs) -> Profile:
        profile = self.session.query(Profile).first()
        if profile:
            for k, v in kwargs.items():
                setattr(profile, k, v)
        else:
            profile = Profile(**kwargs)
            self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    # --- Search Configs ---

    def add_search_config(self, **kwargs) -> SearchConfig:
        config = SearchConfig(**kwargs)
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config

    def list_search_configs(self, active_only: bool = True) -> list[SearchConfig]:
        q = self.session.query(SearchConfig)
        if active_only:
            q = q.filter(SearchConfig.is_active == True)  # noqa: E712
        return q.all()

    # --- Watch Rules ---

    def add_watch_rule(self, **kwargs) -> WatchRule:
        rule = WatchRule(**kwargs)
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def list_watch_rules(self, active_only: bool = True) -> list[WatchRule]:
        q = self.session.query(WatchRule)
        if active_only:
            q = q.filter(WatchRule.is_active == True)  # noqa: E712
        return q.all()

    def delete_watch_rule(self, rule_id: int) -> bool:
        rule = self.session.get(WatchRule, rule_id)
        if rule:
            self.session.delete(rule)
            self.session.commit()
            return True
        return False

    # --- Notifications ---

    def add_notification(self, job_id: int, watch_rule_id: int) -> Notification:
        notif = Notification(job_id=job_id, watch_rule_id=watch_rule_id)
        self.session.add(notif)
        self.session.commit()
        self.session.refresh(notif)
        return notif

    def count_unread_notifications(self) -> int:
        return (
            self.session.query(Notification)
            .filter(Notification.is_read == False)  # noqa: E712
            .count()
        )

    def mark_notifications_read(self) -> int:
        count = (
            self.session.query(Notification)
            .filter(Notification.is_read == False)  # noqa: E712
            .update({"is_read": True})
        )
        self.session.commit()
        return count
