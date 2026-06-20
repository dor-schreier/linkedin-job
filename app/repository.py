import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

VALID_JOB_MAX_AGE_DAYS: int = int(os.environ.get("VALID_JOB_MAX_AGE_DAYS", 60))

from app.models import Company, CVRecord, Interview, Job, JobStatus, LinkedInProfileRaw, Notification, Profile, ProfileEducation, ProfileExperience, RejectAuditLog, RejectRule, SchedulerConfig, ScrapeLog, SearchConfig, SimilarityWeights, TailoredCV, UploadedCV, WatchRule


class JobRepository:
    """Encapsulates all database access. No raw SQL should exist outside this class."""

    def __init__(self, session: Session):
        self.session = session

    # --- Jobs ---

    def _valid_posting_filters(self) -> list:
        """Return SQLAlchemy filter clauses that define a 'valid' posting.

        Valid = apply_url present, and age within VALID_JOB_MAX_AGE_DAYS
        (using COALESCE(date_posted, scraped_at) since date_posted is often null).
        """
        cutoff = datetime.utcnow() - timedelta(days=VALID_JOB_MAX_AGE_DAYS)
        return [
            Job.apply_url.isnot(None),
            Job.apply_url != "",
            func.coalesce(Job.date_posted, Job.scraped_at) >= cutoff,
        ]

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
        company: Optional[list[str]] = None,
        location: Optional[list[str]] = None,
        salary_min_filter: Optional[float] = None,
        fresh_only: bool = False,
        sort: Optional[str] = None,
        sector: Optional[list[str]] = None,
        company_type: Optional[str] = None,
        source: Optional[str] = None,
        rated_only: bool = False,
        hide_rated: bool = False,
        show_inactive: bool = False,
        include_rejected: bool = False,
        search_text: Optional[str] = None,
        title_include: Optional[list[str]] = None,
        title_exclude: Optional[list[str]] = None,
        min_similarity: Optional[int] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        valid_only: bool = False,
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
        elif not include_rejected:
            q = q.filter(Job.status != JobStatus.REJECTED)
        if company:
            q = q.filter(Job.company.in_(company))
        if location:
            q = q.filter(Job.location.in_(location))
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
        if title_include:
            for kw in title_include:
                q = q.filter(Job.title.ilike(f"%{kw}%"))
        if title_exclude:
            for kw in title_exclude:
                q = q.filter(~Job.title.ilike(f"%{kw}%"))
        if fresh_only:
            from datetime import timedelta
            cutoff = date.today() - timedelta(days=3)
            q = q.filter(Job.date_posted >= cutoff)
        if sector or company_type:
            q = q.join(Company, Job.company_id == Company.id)
            if sector:
                q = q.filter(Company.sector.in_(sector))
            if company_type:
                q = q.filter(Company.company_type == company_type)
        if min_similarity is not None:
            q = q.filter(Job.similarity_score >= min_similarity)
        if min_score is not None:
            q = q.filter(Job.fit_score >= min_score)
        if max_score is not None:
            q = q.filter(Job.fit_score <= max_score)
        if valid_only:
            q = q.filter(*self._valid_posting_filters())
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
        elif sort == "scraped_desc":
            q = q.order_by(Job.scraped_at.desc())
        elif sort == "scraped_asc":
            q = q.order_by(Job.scraped_at.asc())
        elif sort == "similarity_desc":
            q = q.order_by(Job.similarity_score.desc().nullslast(), Job.scraped_at.desc())
        else:
            q = q.order_by(Job.scraped_at.desc())
        return q.offset(offset).limit(limit).all()

    def count_jobs_filtered(
        self,
        status: Optional[JobStatus] = None,
        company: Optional[list[str]] = None,
        location: Optional[list[str]] = None,
        salary_min_filter: Optional[float] = None,
        fresh_only: bool = False,
        sector: Optional[list[str]] = None,
        company_type: Optional[str] = None,
        source: Optional[str] = None,
        rated_only: bool = False,
        hide_rated: bool = False,
        show_inactive: bool = False,
        include_rejected: bool = False,
        search_text: Optional[str] = None,
        title_include: Optional[list[str]] = None,
        title_exclude: Optional[list[str]] = None,
        min_similarity: Optional[int] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
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
        elif not include_rejected:
            q = q.filter(Job.status != JobStatus.REJECTED)
        if hide_rated:
            q = q.filter(Job.user_rating.is_(None))
        if company:
            q = q.filter(Job.company.in_(company))
        if location:
            q = q.filter(Job.location.in_(location))
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
        if title_include:
            for kw in title_include:
                q = q.filter(Job.title.ilike(f"%{kw}%"))
        if title_exclude:
            for kw in title_exclude:
                q = q.filter(~Job.title.ilike(f"%{kw}%"))
        if fresh_only:
            from datetime import timedelta
            cutoff = date.today() - timedelta(days=3)
            q = q.filter(Job.date_posted >= cutoff)
        if sector or company_type:
            q = q.join(Company, Job.company_id == Company.id)
            if sector:
                q = q.filter(Company.sector.in_(sector))
            if company_type:
                q = q.filter(Company.company_type == company_type)
        if min_similarity is not None:
            q = q.filter(Job.similarity_score >= min_similarity)
        if min_score is not None:
            q = q.filter(Job.fit_score >= min_score)
        if max_score is not None:
            q = q.filter(Job.fit_score <= max_score)
        return q.count()

    def count_active_jobs(self) -> int:
        return (
            self.session.query(Job)
            .filter(Job.is_active.is_(True), Job.is_rejected.is_(False), Job.status != JobStatus.REJECTED)
            .count()
        )

    def count_high_match_jobs(self, min_score: int = 90) -> int:
        return (
            self.session.query(Job)
            .filter(Job.is_active.is_(True), Job.is_rejected.is_(False), Job.status != JobStatus.REJECTED, Job.fit_score >= min_score)
            .count()
        )

    def count_unscored_jobs(self) -> int:
        return (
            self.session.query(Job)
            .filter(Job.is_active.is_(True), Job.is_rejected.is_(False), Job.status != JobStatus.REJECTED, Job.fit_score.is_(None))
            .count()
        )

    def count_new_since(self, since: datetime) -> int:
        return (
            self.session.query(Job)
            .filter(Job.is_active.is_(True), Job.is_rejected.is_(False), Job.status != JobStatus.REJECTED, Job.scraped_at > since)
            .count()
        )

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

    def get_distinct_subsectors(self) -> list[str]:
        rows = (
            self.session.query(Company.subsector)
            .filter(
                Company.subsector.isnot(None),
                Company.subsector != "",
            )
            .distinct()
            .order_by(Company.subsector)
            .all()
        )
        return [r[0] for r in rows]

    def update_company_sector(
        self,
        company_id: int,
        sector: Optional[str],
        subsector: Optional[str],
    ) -> Optional[Company]:
        company = self.session.query(Company).filter(Company.id == company_id).first()
        if company is None:
            return None
        company.sector = sector if sector else None
        company.subsector = subsector if subsector else None
        self.session.commit()
        self.session.refresh(company)
        return company

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

    def list_active_jobs_for_cleanup(
        self,
        sources: Optional[list[str]] = None,
        limit: Optional[int] = None,
        skip_validated_hours: Optional[int] = None,
    ) -> list[Job]:
        """Return active jobs with an apply_url to check, oldest scraped first.

        If `sources` is given, only jobs from those sources are returned
        (None means all sources). If `skip_validated_hours` is given (>0), jobs
        whose `last_validated_at` falls within that window are excluded (jobs
        never validated are always included). If `limit` is given (>0), at most
        that many jobs are returned — the oldest by `scraped_at`.
        """
        from datetime import datetime, timedelta, timezone
        query = (
            self.session.query(Job)
            .filter(Job.is_active == True, Job.apply_url.isnot(None))  # noqa: E712
        )
        if sources is not None:
            query = query.filter(Job.source.in_(sources))
        if skip_validated_hours is not None and skip_validated_hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=skip_validated_hours)
            query = query.filter(
                or_(Job.last_validated_at.is_(None), Job.last_validated_at < cutoff)
            )
        query = query.order_by(Job.scraped_at.asc())
        if limit is not None and limit > 0:
            query = query.limit(limit)
        return query.all()

    def list_job_sources(self) -> list[str]:
        """Return the distinct sources present among active jobs, sorted."""
        rows = (
            self.session.query(Job.source)
            .filter(Job.is_active == True, Job.source.isnot(None))  # noqa: E712
            .distinct()
            .all()
        )
        return sorted(r[0] for r in rows if r[0])

    def mark_job_inactive(self, job_id: int, checked_at=None) -> Optional[Job]:
        from datetime import datetime, timezone
        job = self.session.get(Job, job_id)
        if job:
            now = checked_at or datetime.now(timezone.utc)
            job.is_active = False
            job.last_checked_at = now
            # Inactive is a definitive verdict — record validation.
            job.last_validated_at = now
            self.session.commit()
            self.session.refresh(job)
        return job

    def update_job_checked_at(self, job_id: int, checked_at=None, validated: bool = False) -> Optional[Job]:
        """Record a cleanup check. If `validated`, the verdict was definitive
        (job confirmed active) and last_validated_at is stamped too; blocked/
        unknown checks pass validated=False so the job is retried next batch."""
        from datetime import datetime, timezone
        job = self.session.get(Job, job_id)
        if job:
            now = checked_at or datetime.now(timezone.utc)
            job.last_checked_at = now
            if validated:
                job.last_validated_at = now
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
        subsector: Optional[str] = None,
        company_type: Optional[str] = None,
        what_they_do: Optional[str] = None,
    ) -> Company:
        company = self.session.query(Company).filter(Company.name_normalized == name_normalized).first()
        if company:
            if sector is not None:
                company.sector = sector
            if subsector is not None:
                company.subsector = subsector
            if company_type is not None:
                company.company_type = company_type
            if what_they_do is not None:
                company.what_they_do = what_they_do
            company.enriched_at = datetime.utcnow()
        else:
            company = Company(
                name_normalized=name_normalized,
                name_display=name_display,
                sector=sector,
                subsector=subsector,
                company_type=company_type,
                what_they_do=what_they_do,
                enriched_at=datetime.utcnow(),
            )
            self.session.add(company)
        self.session.commit()
        self.session.refresh(company)
        return company

    def get_companies_with_active_jobs(self) -> list[dict]:
        """Return flat company records with per-location valid job counts.

        Includes companies whose jobs have no linked Company row (metadata nulled).
        Valid = is_active True, is_rejected False, apply_url present, not stale.
        """
        rows = (
            self.session.query(
                Job.company,
                Job.company_id,
                Job.location,
                Job.scraped_at,
                Company.name_display,
                Company.sector,
                Company.subsector,
                Company.company_type,
                Company.what_they_do,
            )
            .outerjoin(Company, Job.company_id == Company.id)
            .filter(
                Job.is_active == True,    # noqa: E712
                Job.is_rejected == False,  # noqa: E712
                *self._valid_posting_filters(),
            )
            .all()
        )

        # Aggregate per-company: key is company_id if set, else job.company string
        companies: dict[str, dict] = {}
        for row in rows:
            key = str(row.company_id) if row.company_id else f"__str__{row.company}"
            if key not in companies:
                companies[key] = {
                    "name_display": row.name_display or row.company,
                    "company": row.company,
                    "company_id": row.company_id,
                    "sector": row.sector,
                    "subsector": row.subsector,
                    "company_type": row.company_type,
                    "what_they_do": row.what_they_do,
                    "total_active_jobs": 0,
                    "locations": {},
                    "last_scraped_at": None,
                }
            companies[key]["total_active_jobs"] += 1
            loc = row.location or "Unknown / Unspecified"
            companies[key]["locations"][loc] = companies[key]["locations"].get(loc, 0) + 1
            if row.scraped_at is not None:
                prev = companies[key]["last_scraped_at"]
                if prev is None or row.scraped_at > prev:
                    companies[key]["last_scraped_at"] = row.scraped_at

        result = []
        for c in companies.values():
            result.append({
                "name_display": c["name_display"],
                "company": c["company"],
                "company_id": c["company_id"],
                "sector": c["sector"],
                "subsector": c["subsector"],
                "company_type": c["company_type"],
                "what_they_do": c["what_they_do"],
                "total_active_jobs": c["total_active_jobs"],
                "last_scraped_at": c["last_scraped_at"].isoformat() if c["last_scraped_at"] else None,
                "location_breakdown": [
                    {"location": loc, "count": cnt}
                    for loc, cnt in c["locations"].items()
                ],
            })

        return sorted(result, key=lambda x: x["name_display"].lower())

    def get_companies_for_reenrichment(self, limit: int = 20) -> list[Company]:
        """Return Company records ordered by enriched_at ascending (NULLs first), up to limit."""
        return (
            self.session.query(Company)
            .order_by(Company.enriched_at.asc().nullsfirst())
            .limit(limit)
            .all()
        )

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

    def upsert_profile(self, experiences=None, educations=None, **kwargs) -> Profile:
        profile = self.session.query(Profile).first()
        if profile:
            for k, v in kwargs.items():
                setattr(profile, k, v)
        else:
            profile = Profile(**kwargs)
            self.session.add(profile)
            self.session.flush()
        if experiences is not None:
            self.session.query(ProfileExperience).filter(ProfileExperience.profile_id == profile.id).delete()
            for i, exp in enumerate(experiences):
                self.session.add(ProfileExperience(profile_id=profile.id, display_order=i, **exp))
        if educations is not None:
            self.session.query(ProfileEducation).filter(ProfileEducation.profile_id == profile.id).delete()
            for i, edu in enumerate(educations):
                self.session.add(ProfileEducation(profile_id=profile.id, display_order=i, **edu))
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

    def upsert_search_config(self, **kwargs) -> SearchConfig:
        """Update the single active config in-place, or create one if none exists."""
        config = self.session.query(SearchConfig).filter(SearchConfig.is_active == True).order_by(SearchConfig.id.desc()).first()  # noqa: E712
        if config:
            for k, v in kwargs.items():
                setattr(config, k, v)
        else:
            config = SearchConfig(**kwargs)
            self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config

    def get_active_search_config(self) -> Optional[SearchConfig]:
        return self.session.query(SearchConfig).filter(SearchConfig.is_active == True).order_by(SearchConfig.id.desc()).first()  # noqa: E712

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

    def list_unread_notifications_with_jobs(self):
        return (
            self.session.query(Notification, Job, WatchRule)
            .join(Job, Notification.job_id == Job.id)
            .outerjoin(WatchRule, Notification.watch_rule_id == WatchRule.id)
            .filter(Notification.is_read == False)  # noqa: E712
            .order_by(Notification.created_at.desc())
            .all()
        )

    def list_all_notifications_with_jobs(self, limit: int = 200):
        return (
            self.session.query(Notification, Job, WatchRule)
            .join(Job, Notification.job_id == Job.id)
            .outerjoin(WatchRule, Notification.watch_rule_id == WatchRule.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    # --- Interviews ---

    def list_interviews_for_job(self, job_id: int) -> list[Interview]:
        return (
            self.session.query(Interview)
            .filter(Interview.job_id == job_id)
            .order_by(Interview.scheduled_at.asc())
            .all()
        )

    def get_interview(self, interview_id: int) -> Optional[Interview]:
        return self.session.get(Interview, interview_id)

    def create_interview(self, job_id: int, scheduled_at, interview_type, medium, location=None, notes=None) -> Interview:
        interview = Interview(
            job_id=job_id,
            scheduled_at=scheduled_at,
            interview_type=interview_type,
            medium=medium,
            location=location,
            notes=notes,
        )
        self.session.add(interview)
        self.session.commit()
        self.session.refresh(interview)
        return interview

    def update_interview(self, interview_id: int, **kwargs) -> Optional[Interview]:
        interview = self.session.get(Interview, interview_id)
        if interview:
            for k, v in kwargs.items():
                if v is not None or k in ('location', 'notes'):
                    setattr(interview, k, v)
            self.session.commit()
            self.session.refresh(interview)
        return interview

    def delete_interview(self, interview_id: int) -> bool:
        interview = self.session.get(Interview, interview_id)
        if interview:
            # Mark open reminders as read so the badge clears
            self.session.query(Notification).filter(
                Notification.interview_id == interview_id,
                Notification.is_read == False,  # noqa: E712
            ).update({"is_read": True})
            self.session.delete(interview)
            self.session.commit()
            return True
        return False

    def list_jobs_for_tracker(self):
        """Return list of (Job, next_upcoming_Interview|None) for all tracker statuses.

        Rejected jobs are only included when they have at least one interview on record.
        """
        from datetime import datetime
        from sqlalchemy import exists
        TRACKER_STATUSES = [
            JobStatus.SAVED, JobStatus.APPLIED, JobStatus.INTERVIEWING,
            JobStatus.OFFER,
        ]
        active_jobs = (
            self.session.query(Job)
            .filter(Job.status.in_(TRACKER_STATUSES))
            .order_by(Job.scraped_at.desc())
            .all()
        )
        rejected_with_interviews = (
            self.session.query(Job)
            .filter(
                Job.status == JobStatus.REJECTED,
                exists().where(Interview.job_id == Job.id),
            )
            .order_by(Job.scraped_at.desc())
            .all()
        )
        jobs = active_jobs + rejected_with_interviews
        if not jobs:
            return []
        now = datetime.utcnow()
        job_ids = [j.id for j in jobs]
        upcoming = (
            self.session.query(Interview)
            .filter(Interview.job_id.in_(job_ids), Interview.scheduled_at > now)
            .order_by(Interview.scheduled_at.asc())
            .all()
        )
        next_by_job: dict[int, Interview] = {}
        for iv in upcoming:
            if iv.job_id not in next_by_job:
                next_by_job[iv.job_id] = iv
        return [(job, next_by_job.get(job.id)) for job in jobs]

    def interview_reminder_exists(self, interview_id: int, kind: str) -> bool:
        return (
            self.session.query(Notification)
            .filter(
                Notification.interview_id == interview_id,
                Notification.kind == kind,
            )
            .first()
        ) is not None

    # --- ScrapeLog ---

    def create_scrape_log(self, config_id: Optional[int] = None, trigger: Optional[str] = None) -> ScrapeLog:
        log = ScrapeLog(started_at=datetime.now(timezone.utc), status="running", config_id=config_id, trigger=trigger)
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def finish_scrape_log(
        self,
        log_id: int,
        jobs_found: int,
        jobs_new: int,
        error: Optional[str] = None,
        linkedin_count: Optional[int] = None,
        indeed_count: Optional[int] = None,
        glassdoor_count: Optional[int] = None,
        comeet_count: Optional[int] = None,
        filter_blocked: Optional[int] = None,
        filter_keywords: Optional[int] = None,
        filter_salary: Optional[int] = None,
        filter_remote: Optional[int] = None,
        jobs_scored: Optional[int] = None,
        score_failed: Optional[int] = None,
    ) -> None:
        log = self.session.get(ScrapeLog, log_id)
        if log:
            log.finished_at = datetime.now(timezone.utc)
            log.jobs_found = jobs_found
            log.jobs_new = jobs_new
            log.status = "error" if error else "success"
            log.error = error
            log.linkedin_count = linkedin_count
            log.indeed_count = indeed_count
            log.glassdoor_count = glassdoor_count
            log.comeet_count = comeet_count
            log.filter_blocked = filter_blocked
            log.filter_keywords = filter_keywords
            log.filter_salary = filter_salary
            log.filter_remote = filter_remote
            log.jobs_scored = jobs_scored
            log.score_failed = score_failed
            self.session.commit()

    def list_scrape_logs(self, limit: int = 20) -> list[ScrapeLog]:
        return (
            self.session.query(ScrapeLog)
            .order_by(ScrapeLog.started_at.desc())
            .limit(limit)
            .all()
        )

    def list_scrape_logs_paginated(self, page: int = 1, page_size: int = 25) -> tuple[list[ScrapeLog], int]:
        q = self.session.query(ScrapeLog).order_by(ScrapeLog.started_at.desc())
        total = q.count()
        items = q.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

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

    def update_scheduler_config(
        self,
        interval_hours: Optional[int] = None,
        is_enabled: Optional[bool] = None,
        cleanup_sources: Optional[list[str]] = None,
        cleanup_limit: Optional[int] = None,
        cleanup_skip_validated_hours: Optional[int] = None,
    ) -> SchedulerConfig:
        cfg = self.get_scheduler_config()
        if interval_hours is not None:
            cfg.interval_hours = interval_hours
        if is_enabled is not None:
            cfg.is_enabled = is_enabled
        if cleanup_sources is not None:
            # Empty list is stored as "[]" (check nothing); NULL keeps "all sources".
            cfg.cleanup_sources = json.dumps(cleanup_sources)
        if cleanup_limit is not None:
            # 0 (or negative) clears the limit back to "no limit" (NULL).
            cfg.cleanup_limit = cleanup_limit if cleanup_limit > 0 else None
        if cleanup_skip_validated_hours is not None:
            # 0 (or negative) clears the skip window back to "don't skip" (NULL).
            cfg.cleanup_skip_validated_hours = (
                cleanup_skip_validated_hours if cleanup_skip_validated_hours > 0 else None
            )
        self.session.commit()
        self.session.refresh(cfg)
        return cfg

    def get_cleanup_sources(self) -> Optional[list[str]]:
        """Parse the persisted cleanup source list. None means all sources."""
        cfg = self.get_scheduler_config()
        if not cfg.cleanup_sources:
            return None
        try:
            value = json.loads(cfg.cleanup_sources)
            return value if isinstance(value, list) else None
        except (ValueError, TypeError):
            return None

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

    # --- Uploaded CV ---

    def save_uploaded_cv(self, file_path: str, original_filename: str, parsed_json: str) -> UploadedCV:
        record = UploadedCV(file_path=file_path, original_filename=original_filename, parsed_json=parsed_json)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get_latest_uploaded_cv(self) -> Optional[UploadedCV]:
        return (
            self.session.query(UploadedCV)
            .order_by(UploadedCV.uploaded_at.desc())
            .first()
        )

    def get_all_uploaded_cvs(self) -> list[UploadedCV]:
        return (
            self.session.query(UploadedCV)
            .order_by(UploadedCV.uploaded_at.asc())
            .all()
        )

    def get_uploaded_cv_by_id(self, record_id: int) -> Optional[UploadedCV]:
        return self.session.get(UploadedCV, record_id)

    def delete_all_uploaded_cvs(self) -> int:
        records = self.session.query(UploadedCV).all()
        count = len(records)
        for record in records:
            self.session.delete(record)
        self.session.commit()
        return count

    def delete_uploaded_cv_by_id(self, record_id: int) -> bool:
        record = self.session.get(UploadedCV, record_id)
        if record:
            self.session.delete(record)
            self.session.commit()
            return True
        return False

    # --- Tailored CV ---

    def get_tailored_cv(self, job_id: int) -> Optional[TailoredCV]:
        return self.session.query(TailoredCV).filter(TailoredCV.job_id == job_id).first()

    def upsert_tailored_cv(
        self,
        job_id: int,
        cv_json: str,
        pdf_path: Optional[str],
        docx_path: Optional[str],
        model_used: Optional[str],
    ) -> TailoredCV:
        record = self.session.query(TailoredCV).filter(TailoredCV.job_id == job_id).first()
        if record:
            record.cv_json = cv_json
            record.pdf_path = pdf_path
            record.docx_path = docx_path
            record.model_used = model_used
            record.generated_at = datetime.now(timezone.utc)
        else:
            record = TailoredCV(
                job_id=job_id,
                cv_json=cv_json,
                pdf_path=pdf_path,
                docx_path=docx_path,
                model_used=model_used,
            )
            self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    # --- Similarity ---

    def set_job_target(self, job_id: int, value: bool) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.is_target = value
            self.session.commit()
            self.session.refresh(job)
        return job

    def list_target_jobs(self) -> list[Job]:
        return self.session.query(Job).filter(Job.is_target == True).all()  # noqa: E712

    def get_similarity_weights(self) -> SimilarityWeights:
        weights = self.session.query(SimilarityWeights).first()
        if not weights:
            weights = SimilarityWeights()
            self.session.add(weights)
            self.session.commit()
            self.session.refresh(weights)
        return weights

    def update_similarity_weights(self, **fields) -> SimilarityWeights:
        weights = self.get_similarity_weights()
        for k, v in fields.items():
            setattr(weights, k, v)
        self.session.commit()
        self.session.refresh(weights)
        return weights

    def set_job_similarity(self, job_id: int, score: int, breakdown: str) -> Optional[Job]:
        job = self.session.get(Job, job_id)
        if job:
            job.similarity_score = score
            job.similarity_breakdown_json = breakdown
            self.session.commit()
        return job

    def delete_tailored_cv(self, job_id: int) -> bool:
        record = self.session.query(TailoredCV).filter(TailoredCV.job_id == job_id).first()
        if not record:
            return False
        import os
        for path in (record.pdf_path, record.docx_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        self.session.delete(record)
        self.session.commit()
        return True
