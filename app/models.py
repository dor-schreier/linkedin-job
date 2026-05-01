import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.database import Base


class JobStatus(enum.Enum):
    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_normalized = Column(String(300), unique=True, nullable=False)
    name_display = Column(String(300), nullable=False)
    sector = Column(String(150), nullable=True)
    company_type = Column(String(50), nullable=True)  # corporate/startup/scaleup/agency/non-profit/government/unknown
    what_they_do = Column(Text, nullable=True)
    enriched_at = Column(DateTime, server_default=func.now(), nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    location = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String(50), nullable=False)  # linkedin, indeed, glassdoor
    apply_url = Column(String(2000), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(10), nullable=True)
    job_hash = Column(String(64), unique=True, nullable=False)  # SHA256(title+company+location) for dedup
    status = Column(SAEnum(JobStatus), default=JobStatus.NEW, nullable=False)
    fit_score = Column(Integer, nullable=True)  # 0-100, Phase 4
    fit_summary = Column(Text, nullable=True)  # Phase 4
    salary_estimated = Column(Text, nullable=True)  # Phase 4
    date_posted = Column(Date, nullable=True)  # Date job was posted (from JobSpy)
    intelligence_json = Column(Text, nullable=True)  # JD intelligence extraction (JSON)
    score_breakdown_json = Column(Text, nullable=True)  # Enhanced fit score breakdown (JSON)
    user_rating = Column(Integer, nullable=True)  # 1-5, NULL = unrated
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    summary_tech_stack_json = Column(Text, nullable=True)
    summary_qualifications_json = Column(Text, nullable=True)
    summary_experience_needed = Column(String(200), nullable=True)
    summary_general_description = Column(Text, nullable=True)
    summary_generated_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    last_checked_at = Column(DateTime, nullable=True)
    is_rejected = Column(Boolean, default=False, nullable=False, server_default="0")
    rejected_at = Column(DateTime, nullable=True)
    rejected_by_rule_id = Column(Integer, ForeignKey("reject_rules.id", ondelete="SET NULL"), nullable=True)
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    company_info = relationship("Company", foreign_keys=[company_id])
    rejected_by_rule = relationship("RejectRule", foreign_keys=[rejected_by_rule_id])

    @validates('status')
    def _sync_from_status(self, key, value):
        if getattr(self, '_rejection_sync', False):
            return value
        self._rejection_sync = True
        try:
            if value == JobStatus.REJECTED:
                self.is_rejected = True
                self.is_active = False
            elif self.status == JobStatus.REJECTED:
                self.is_rejected = False
                self.is_active = True
        finally:
            self._rejection_sync = False
        return value

    @validates('is_rejected')
    def _sync_from_is_rejected(self, key, value):
        if getattr(self, '_rejection_sync', False):
            return value
        self._rejection_sync = True
        try:
            if value is True:
                self.status = JobStatus.REJECTED
                self.is_active = False
            elif value is False:
                if self.status == JobStatus.REJECTED:
                    self.status = JobStatus.NEW
                self.is_active = True
        finally:
            self._rejection_sync = False
        return value


class RejectRule(Base):
    __tablename__ = "reject_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(50), nullable=False)  # location | property | title_keyword
    property_name = Column(String(100), nullable=True)
    value = Column(String(500), nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="1")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)


class RejectAuditLog(Base):
    __tablename__ = "reject_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False)
    rule_id = Column(Integer, nullable=True)
    rule_snapshot_json = Column(Text, nullable=True)
    action = Column(String(20), nullable=False)  # rejected | unrejected
    actor = Column(String(20), nullable=False)   # system | user
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_url = Column(String(500), nullable=True)
    skills = Column(Text, nullable=True)
    current_title = Column(String(300), nullable=True)
    target_title = Column(String(300), nullable=True)
    years_experience = Column(Integer, nullable=True)
    ai_recommendations = Column(Text, nullable=True)  # Phase 4: persisted Groq recommendations (newline-separated bullets)
    linkedin_analysis = Column(Text, nullable=True)  # JSON blob of last section-by-section LinkedIn profile analysis
    linkedin_analyzed_at = Column(DateTime, nullable=True)  # timestamp of last LinkedIn profile analysis run
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SearchConfig(Base):
    """Search configuration for a scrape run.

    experience_level is retained for backward compatibility but only applied when
    role_level == 'ic_senior' (used as a title prefix in that track). For all other
    role_level values, use ROLE_LEVEL_TERMS in scraper.py to build search terms.
    """
    __tablename__ = "search_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keywords = Column(String(500), nullable=False)
    location = Column(String(300), nullable=True)
    experience_level = Column(String(50), nullable=True)
    work_mode = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Search Config v2 fields
    role_level = Column(String(50), nullable=True)  # ic_senior, team_lead, engineering_manager, director, vp
    include_remote = Column(Boolean, default=False, nullable=False, server_default="0")
    country = Column(String(100), default="israel", nullable=False, server_default="israel")
    max_age_hours = Column(Integer, nullable=True, default=72)
    exclude_keywords = Column(Text, nullable=True)   # CSV string
    blocked_companies = Column(Text, nullable=True)  # CSV string
    results_wanted = Column(Integer, default=50, nullable=False, server_default="50")
    min_salary = Column(Integer, nullable=True)


class WatchRule(Base):
    __tablename__ = "watch_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(50), nullable=False)  # company, keyword, sector
    value = Column(String(300), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False)
    watch_rule_id = Column(Integer, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    config_id = Column(Integer, nullable=True)  # SearchConfig.id, None = all configs
    jobs_found = Column(Integer, nullable=True)
    jobs_new = Column(Integer, nullable=True)
    status = Column(String(20), default="running", nullable=False)  # running, success, error
    error = Column(Text, nullable=True)


class SchedulerConfig(Base):
    """Single-row table that persists scheduler settings."""
    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interval_hours = Column(Integer, default=6, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LinkedInProfileRaw(Base):
    """Stores raw LinkedIn profile data scraped or imported from a ZIP export."""
    __tablename__ = "linkedin_profiles_raw"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_url = Column(String(500), unique=True, nullable=False)
    raw_json = Column(Text, nullable=False)
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)


class CVRecord(Base):
    """Stores generated CV data linked to a LinkedIn profile."""
    __tablename__ = "cv_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_url = Column(String(500), nullable=False, index=True)
    cv_json = Column(Text, nullable=False)
    template_name = Column(String(100), nullable=False, server_default="default")
    generated_at = Column(DateTime, server_default=func.now(), nullable=False)
