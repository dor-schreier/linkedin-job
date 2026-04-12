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
        company: Optional[str] = None,
        salary_min_filter: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        q = self.session.query(Job)
        if status:
            q = q.filter(Job.status == status)
        if company:
            q = q.filter(Job.company.ilike(f"%{company}%"))
        if salary_min_filter is not None:
            q = q.filter(Job.salary_min >= salary_min_filter)
        return q.order_by(Job.scraped_at.desc()).offset(offset).limit(limit).all()

    def count_jobs_filtered(
        self,
        status: Optional[JobStatus] = None,
        company: Optional[str] = None,
        salary_min_filter: Optional[float] = None,
    ) -> int:
        q = self.session.query(Job)
        if status:
            q = q.filter(Job.status == status)
        if company:
            q = q.filter(Job.company.ilike(f"%{company}%"))
        if salary_min_filter is not None:
            q = q.filter(Job.salary_min >= salary_min_filter)
        return q.count()

    def update_job_status(self, job_id: int, status: JobStatus) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.status = status
            self.session.commit()
            self.session.refresh(job)
        return job

    def update_job_scores(
        self,
        job_id: int,
        fit_score: int,
        fit_summary: str,
        salary_estimated: Optional[str] = None,
    ) -> Optional[Job]:
        """Persist Groq scoring output. salary_estimated=None leaves existing value untouched."""
        job = self.session.get(Job, job_id)
        if job:
            job.fit_score = fit_score
            job.fit_summary = fit_summary
            if salary_estimated is not None:
                job.salary_estimated = salary_estimated
            self.session.commit()
            self.session.refresh(job)
        return job

    def get_job(self, job_id: int) -> Optional[Job]:
        return self.session.get(Job, job_id)

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

    def get_jobs_by_ids(self, job_ids: list[int]) -> list[Job]:
        if not job_ids:
            return []
        return self.session.query(Job).filter(Job.id.in_(job_ids)).all()

    def list_unread_notifications_with_jobs(self) -> list[tuple[Notification, Job, WatchRule]]:
        return (
            self.session.query(Notification, Job, WatchRule)
            .join(Job, Notification.job_id == Job.id)
            .join(WatchRule, Notification.watch_rule_id == WatchRule.id)
            .filter(Notification.is_read == False)  # noqa: E712
            .order_by(Notification.created_at.desc())
            .all()
        )

    def list_all_notifications_with_jobs(self, limit: int = 200) -> list[tuple[Notification, Job, WatchRule]]:
        return (
            self.session.query(Notification, Job, WatchRule)
            .join(Job, Notification.job_id == Job.id)
            .join(WatchRule, Notification.watch_rule_id == WatchRule.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    def notification_exists(self, job_id: int, watch_rule_id: int) -> bool:
        return (
            self.session.query(Notification)
            .filter(Notification.job_id == job_id, Notification.watch_rule_id == watch_rule_id)
            .first()
            is not None
        )
