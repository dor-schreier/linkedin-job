from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Company, CVRecord, Job, JobStatus, LinkedInProfileRaw, Notification, Profile, RejectAuditLog, RejectRule, SchedulerConfig, ScrapeLog, SearchConfig, WatchRule


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
        location: Optional[str] = None,
        salary_min_filter: Optional[float] = None,
        fresh_only: bool = False,
        sort: Optional[str] = None,
        sector: Optional[str] = None,
        company_type: Optional[str] = None,
        source: Optional[str] = None,
        rated_only: bool = False,
        hide_rated: bool = False,
        show_inactive: bool = False,
        include_rejected: bool = False,
        search_text: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        q = self.session.query(Job)
        if not show_inactive:
            q = q.filter(Job.is_active == True)  # noqa: E712
        if not include_rejected:
            q = q.filter(Job.is_rejected == False)  # noqa: E712
        if rated_only:
            q = q.filter(Job.user_rating.isnot(None))
        elif status:
            q = q.filter(Job.status == status)
        else:
            q = q.filter(Job.status != JobStatus.REJECTED)
        if company:
            q = q.filter(Job.company.ilike(f"%{company}%"))
        if location:
            q = q.filter(Job.location == location)
        if salary_min_filter is not None:
            q = q.filter(Job.salary_min >= salary_min_filter)
        if source:
            q = q.filter(Job.source == source)
        if hide_rated:
            q = q.filter(Job.user_rating.is_(None))
        if search_text:
            q = q.filter(or_(
                Job.title.ilike(f"%{search_text}%"),
                Job.company.ilike(f"%{search_text}%"),
                Job.location.ilike(f"%{search_text}%"),
            ))
        if fresh_only:
            from datetime import timedelta
            cutoff = date.today() - timedelta(days=3)
            q = q.filter(Job.date_posted >= cutoff)
        if sector or company_type:
            q = q.join(Company, Job.company_id == Company.id)
            if sector:
                q = q.filter(Company.sector == sector)
            if company_type:
                q = q.filter(Company.company_type == company_type)
        if sort == "freshest":
            q = q.order_by(Job.date_posted.desc().nullslast(), Job.scraped_at.desc())
        elif sort == "fit_desc":
            q = q.order_by(Job.fit_score.desc().nullslast(), Job.scraped_at.desc())
        elif sort == "fit_asc":
            q = q.order_by(Job.fit_score.asc().nullslast(), Job.scraped_at.desc())
        elif sort == "rating_desc":
            q = q.order_by(Job.user_rating.desc().nullslast(), Job.scraped_at.desc())
        elif sort == "date_posted_asc":
            q = q.order_by(Job.date_posted.asc().nullslast(), Job.scraped_at.asc())
        else:
            q = q.order_by(Job.scraped_at.desc())
        return q.offset(offset).limit(limit).all()

    def count_jobs_filtered(
        self,
        status: Optional[JobStatus] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        salary_min_filter: Optional[float] = None,
        fresh_only: bool = False,
        sector: Optional[str] = None,
        company_type: Optional[str] = None,
        source: Optional[str] = None,
        rated_only: bool = False,
        hide_rated: bool = False,
        show_inactive: bool = False,
        include_rejected: bool = False,
        search_text: Optional[str] = None,
    ) -> int:
        q = self.session.query(Job)
        if not show_inactive:
            q = q.filter(Job.is_active == True)  # noqa: E712
        if not include_rejected:
            q = q.filter(Job.is_rejected == False)  # noqa: E712
        if rated_only:
            q = q.filter(Job.user_rating.isnot(None))
        elif status:
            q = q.filter(Job.status == status)
        else:
            q = q.filter(Job.status != JobStatus.REJECTED)
        if hide_rated:
            q = q.filter(Job.user_rating.is_(None))
        if company:
            q = q.filter(Job.company.ilike(f"%{company}%"))
        if location:
            q = q.filter(Job.location == location)
        if salary_min_filter is not None:
            q = q.filter(Job.salary_min >= salary_min_filter)
        if source:
            q = q.filter(Job.source == source)
        if search_text:
            q = q.filter(or_(
                Job.title.ilike(f"%{search_text}%"),
                Job.company.ilike(f"%{search_text}%"),
                Job.location.ilike(f"%{search_text}%"),
            ))
        if fresh_only:
            from datetime import timedelta
            cutoff = date.today() - timedelta(days=3)
            q = q.filter(Job.date_posted >= cutoff)
        if sector or company_type:
            q = q.join(Company, Job.company_id == Company.id)
            if sector:
                q = q.filter(Company.sector == sector)
            if company_type:
                q = q.filter(Company.company_type == company_type)
        return q.count()

    def get_distinct_sources(self) -> list[str]:
        rows = (
            self.session.query(Job.source)
            .filter(
                Job.source.isnot(None),
                Job.source != "",
                Job.is_active == True,  # noqa: E712
            )
            .distinct()
            .order_by(Job.source)
            .all()
        )
        return [r[0] for r in rows]

    def get_distinct_companies(self) -> list[str]:
        rows = (
            self.session.query(Job.company)
            .filter(
                Job.company.isnot(None),
                Job.company != "",
                Job.is_active == True,  # noqa: E712
            )
            .distinct()
            .order_by(Job.company)
            .all()
        )
        return [r[0] for r in rows]

    def get_distinct_sectors(self) -> list[str]:
        rows = (
            self.session.query(Company.sector)
            .join(Job, Job.company_id == Company.id)
            .filter(
                Company.sector.isnot(None),
                Company.sector != "",
                Job.is_active == True,  # noqa: E712
            )
            .distinct()
            .order_by(Company.sector)
            .all()
        )
        return [r[0] for r in rows]

    def get_distinct_company_types(self) -> list[str]:
        rows = (
            self.session.query(Company.company_type)
            .join(Job, Job.company_id == Company.id)
            .filter(
                Company.company_type.isnot(None),
                Company.company_type != "",
                Job.is_active == True,  # noqa: E712
            )
            .distinct()
            .order_by(Company.company_type)
            .all()
        )
        return [r[0] for r in rows]

    def get_distinct_locations(self) -> list[str]:
        rows = (
            self.session.query(Job.location)
            .filter(
                Job.location.isnot(None),
                Job.location != "",
                Job.is_active == True,  # noqa: E712
                Job.status != JobStatus.REJECTED,
            )
            .distinct()
            .order_by(Job.location)
            .all()
        )
        return [r[0] for r in rows]

    def update_job_rating(self, job_id: int, rating: Optional[int]) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.user_rating = rating
            self.session.commit()
            self.session.refresh(job)
        return job

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

    def update_job_score_breakdown(
        self,
        job_id: int,
        score_breakdown_json: str,
        fit_score: int,
        fit_summary: str,
    ) -> Optional[Job]:
        """Persist enhanced fit score breakdown and update fit_score/fit_summary atomically."""
        job = self.session.get(Job, job_id)
        if job:
            job.score_breakdown_json = score_breakdown_json
            job.fit_score = fit_score
            job.fit_summary = fit_summary
            self.session.commit()
            self.session.refresh(job)
        return job

    def get_job(self, job_id: int) -> Optional[Job]:
        return self.session.get(Job, job_id)

    def count_jobs(self) -> int:
        return self.session.query(Job).filter(Job.is_active == True).count()  # noqa: E712

    def list_active_jobs_for_cleanup(self) -> list[Job]:
        """Return all active jobs that have an apply_url to check."""
        return (
            self.session.query(Job)
            .filter(Job.is_active == True, Job.apply_url.isnot(None))  # noqa: E712
            .order_by(Job.last_checked_at.asc().nullsfirst())
            .all()
        )

    def mark_job_inactive(self, job_id: int, checked_at=None) -> Optional[Job]:
        from datetime import datetime, timezone
        job = self.session.get(Job, job_id)
        if job:
            job.is_active = False
            job.last_checked_at = checked_at or datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(job)
        return job

    def update_job_checked_at(self, job_id: int, checked_at=None) -> Optional[Job]:
        from datetime import datetime, timezone
        job = self.session.get(Job, job_id)
        if job:
            job.last_checked_at = checked_at or datetime.now(timezone.utc)
            self.session.commit()
        return job

    def get_jobs_with_intelligence(self, days: int = 30) -> list[Job]:
        """Return jobs with intelligence_json set, scraped within the last `days` days."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.session.query(Job)
            .filter(Job.intelligence_json.isnot(None))
            .filter(Job.scraped_at >= cutoff)
            .order_by(Job.scraped_at.desc())
            .all()
        )

    def update_job_summary(
        self,
        job_id: int,
        tech_stack_json: str,
        qualifications_json: str,
        experience_needed: Optional[str],
        general_description: Optional[str],
    ) -> Optional[Job]:
        from datetime import datetime, timezone
        job = self.session.get(Job, job_id)
        if job:
            job.summary_tech_stack_json = tech_stack_json
            job.summary_qualifications_json = qualifications_json
            job.summary_experience_needed = experience_needed
            job.summary_general_description = general_description
            job.summary_generated_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(job)
        return job

    def update_job_company_id(self, job_id: int, company_id: int) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.company_id = company_id
            self.session.commit()
            self.session.refresh(job)
        return job

    # --- Companies ---

    def get_company_by_normalized_name(self, name_normalized: str) -> Optional[Company]:
        return self.session.query(Company).filter(Company.name_normalized == name_normalized).first()

    def upsert_company(
        self,
        name_normalized: str,
        name_display: str,
        sector: Optional[str] = None,
        company_type: Optional[str] = None,
        what_they_do: Optional[str] = None,
    ) -> Company:
        company = self.session.query(Company).filter(Company.name_normalized == name_normalized).first()
        if company:
            if sector is not None:
                company.sector = sector
            if company_type is not None:
                company.company_type = company_type
            if what_they_do is not None:
                company.what_they_do = what_they_do
        else:
            company = Company(
                name_normalized=name_normalized,
                name_display=name_display,
                sector=sector,
                company_type=company_type,
                what_they_do=what_they_do,
            )
            self.session.add(company)
        self.session.commit()
        self.session.refresh(company)
        return company

    # --- Profile ---

    def get_profile(self) -> Optional[Profile]:
        return self.session.query(Profile).first()

    def upsert_profile_analysis(self, analysis_json: str) -> Optional[Profile]:
        """Save linkedin analysis JSON and set analyzed_at timestamp."""
        from datetime import datetime, timezone
        profile = self.session.query(Profile).first()
        if profile:
            profile.linkedin_analysis = analysis_json
            profile.linkedin_analyzed_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(profile)
        return profile

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

    def toggle_watch_rule(self, rule_id: int) -> WatchRule | None:
        rule = self.session.get(WatchRule, rule_id)
        if rule:
            rule.is_active = not rule.is_active
            self.session.commit()
            self.session.refresh(rule)
        return rule

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

    def add_notification_no_commit(self, job_id: int, watch_rule_id: int) -> Notification:
        """Add a notification without committing. Caller must commit after batch."""
        notif = Notification(job_id=job_id, watch_rule_id=watch_rule_id)
        self.session.add(notif)
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

    # --- ScrapeLog ---

    def create_scrape_log(self, config_id: Optional[int] = None) -> ScrapeLog:
        log = ScrapeLog(started_at=datetime.now(timezone.utc), status="running", config_id=config_id)
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def finish_scrape_log(self, log_id: int, jobs_found: int, jobs_new: int, error: Optional[str] = None) -> None:
        log = self.session.get(ScrapeLog, log_id)
        if log:
            log.finished_at = datetime.now(timezone.utc)
            log.jobs_found = jobs_found
            log.jobs_new = jobs_new
            log.status = "error" if error else "success"
            log.error = error
            self.session.commit()

    def list_scrape_logs(self, limit: int = 20) -> list[ScrapeLog]:
        return (
            self.session.query(ScrapeLog)
            .order_by(ScrapeLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def get_latest_scrape_log(self) -> Optional[ScrapeLog]:
        return (
            self.session.query(ScrapeLog)
            .order_by(ScrapeLog.started_at.desc())
            .first()
        )

    # --- SchedulerConfig ---

    def get_scheduler_config(self) -> SchedulerConfig:
        cfg = self.session.query(SchedulerConfig).first()
        if not cfg:
            cfg = SchedulerConfig(interval_hours=6, is_enabled=True)
            self.session.add(cfg)
            self.session.commit()
            self.session.refresh(cfg)
        return cfg

    def update_scheduler_config(self, interval_hours: Optional[int] = None, is_enabled: Optional[bool] = None) -> SchedulerConfig:
        cfg = self.get_scheduler_config()
        if interval_hours is not None:
            cfg.interval_hours = interval_hours
        if is_enabled is not None:
            cfg.is_enabled = is_enabled
        self.session.commit()
        self.session.refresh(cfg)
        return cfg

    def notification_exists(self, job_id: int, watch_rule_id: int) -> bool:
        return (
            self.session.query(Notification)
            .filter(Notification.job_id == job_id, Notification.watch_rule_id == watch_rule_id)
            .first()
            is not None
        )

    # --- LinkedIn Profile Raw ---

    def upsert_profile_raw(self, profile_url: str, data_dict: dict) -> LinkedInProfileRaw:
        import json
        raw = self.session.query(LinkedInProfileRaw).filter(LinkedInProfileRaw.profile_url == profile_url).first()
        if raw:
            raw.raw_json = json.dumps(data_dict)
            raw.scraped_at = datetime.now(timezone.utc)
        else:
            raw = LinkedInProfileRaw(profile_url=profile_url, raw_json=json.dumps(data_dict))
            self.session.add(raw)
        self.session.commit()
        self.session.refresh(raw)
        return raw

    def get_profile_raw(self, profile_url: str) -> Optional[LinkedInProfileRaw]:
        return self.session.query(LinkedInProfileRaw).filter(LinkedInProfileRaw.profile_url == profile_url).first()

    # --- CV Records ---

    def save_cv(self, profile_url: str, cv_dict: dict, template_name: str = "default") -> CVRecord:
        import json
        record = CVRecord(profile_url=profile_url, cv_json=json.dumps(cv_dict), template_name=template_name)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_latest_cv(self, profile_url: str) -> Optional[CVRecord]:
        return (
            self.session.query(CVRecord)
            .filter(CVRecord.profile_url == profile_url)
            .order_by(CVRecord.generated_at.desc())
            .first()
        )

    def list_cvs(self) -> list[CVRecord]:
        return (
            self.session.query(CVRecord)
            .order_by(CVRecord.generated_at.desc())
            .all()
        )

    # --- Reject Rules ---

    def list_reject_rules(self) -> list[RejectRule]:
        return self.session.query(RejectRule).order_by(RejectRule.id.asc()).all()

    def get_reject_rule(self, rule_id: int) -> Optional[RejectRule]:
        return self.session.get(RejectRule, rule_id)

    def find_reject_rule(self, rule_type: str, property_name: Optional[str], value: str) -> Optional[RejectRule]:
        q = self.session.query(RejectRule).filter(
            RejectRule.rule_type == rule_type,
            RejectRule.value == value,
        )
        if property_name is None:
            q = q.filter(RejectRule.property_name.is_(None))
        else:
            q = q.filter(RejectRule.property_name == property_name)
        return q.first()

    def add_reject_rule(self, rule_type: str, value: str, property_name: Optional[str] = None) -> RejectRule:
        existing = self.find_reject_rule(rule_type, property_name, value)
        if existing:
            return existing
        rule = RejectRule(rule_type=rule_type, property_name=property_name, value=value, is_enabled=True)
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def toggle_reject_rule(self, rule_id: int) -> Optional[RejectRule]:
        rule = self.session.get(RejectRule, rule_id)
        if rule:
            rule.is_enabled = not rule.is_enabled
            self.session.commit()
            self.session.refresh(rule)
        return rule

    def delete_reject_rule(self, rule_id: int) -> bool:
        rule = self.session.get(RejectRule, rule_id)
        if rule:
            self.session.delete(rule)
            self.session.commit()
            return True
        return False

    def count_jobs_attributed_to_rule(self, rule_id: int) -> int:
        return (
            self.session.query(Job)
            .filter(Job.rejected_by_rule_id == rule_id, Job.is_rejected == True)  # noqa: E712
            .count()
        )

    def list_reject_audit_for_job(self, job_id: int) -> list[RejectAuditLog]:
        return (
            self.session.query(RejectAuditLog)
            .filter(RejectAuditLog.job_id == job_id)
            .order_by(RejectAuditLog.created_at.asc())
            .all()
        )

    def get_distinct_property_values(self, property_name: str) -> list[str]:
        if property_name == "company":
            col = Job.company
            rows = (
                self.session.query(col)
                .filter(col.isnot(None), col != "")
                .distinct()
                .order_by(col)
                .all()
            )
            return [r[0] for r in rows]
        if property_name == "source":
            col = Job.source
            rows = (
                self.session.query(col)
                .filter(col.isnot(None), col != "")
                .distinct()
                .order_by(col)
                .all()
            )
            return [r[0] for r in rows]
        if property_name == "sector":
            return self.get_distinct_sectors()
        if property_name == "company_type":
            return self.get_distinct_company_types()
        return []

    def get_all_distinct_locations(self) -> list[str]:
        rows = (
            self.session.query(Job.location)
            .filter(Job.location.isnot(None), Job.location != "")
            .distinct()
            .order_by(Job.location)
            .all()
        )
        return [r[0] for r in rows]

    def list_rejected_jobs(self, limit: int = 200) -> list[Job]:
        return (
            self.session.query(Job)
            .filter(Job.is_rejected == True)  # noqa: E712
            .order_by(Job.rejected_at.desc().nullslast())
            .limit(limit)
            .all()
        )
