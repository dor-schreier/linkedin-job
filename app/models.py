import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
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


class InterviewType(enum.Enum):
    FIRST_HR = "first_hr"
    INITIAL = "initial"
    TECHNICAL = "technical"
    FINAL_HR = "final_hr"


class InterviewMedium(enum.Enum):
    PHONE = "phone"
    ZOOM = "zoom"
    IN_PERSON = "in_person"


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_normalized = Column(String(300), unique=True, nullable=False)
    name_display = Column(String(300), nullable=False)
    sector = Column(String(150), nullable=True)
    subsector = Column(String(150), nullable=True)
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
    job_hash = Column(String(64), unique=True, nullable=False)  # SHA256 dedup key; Comeet rows use SHA256("comeet|{company}/{position-code}/{job-id}"), others use SHA256(title+company+location)
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
    is_target = Column(Boolean, default=False, nullable=False, server_default="0")
    similarity_score = Column(Integer, nullable=True)
    similarity_breakdown_json = Column(Text, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    # Set only when a cleanup check reached a definitive verdict (active/inactive),
    # NOT on blocked/unknown results — so limited batches can skip recently-validated
    # jobs while still retrying blocked ones. Distinct from last_checked_at.
    last_validated_at = Column(DateTime, nullable=True)
    is_rejected = Column(Boolean, default=False, nullable=False, server_default="0")
    rejected_at = Column(DateTime, nullable=True)
    rejected_by_rule_id = Column(Integer, ForeignKey("reject_rules.id", ondelete="SET NULL"), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    company_info = relationship("Company", foreign_keys=[company_id])
    rejected_by_rule = relationship("RejectRule", foreign_keys=[rejected_by_rule_id])
    interviews = relationship("Interview", back_populates="job", cascade="all, delete-orphan", order_by="Interview.scheduled_at")

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
            if value == JobStatus.APPLIED and not self.applied_at:
                from datetime import datetime
                self.applied_at = datetime.utcnow()
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


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    interview_type = Column(SAEnum(InterviewType), nullable=False)
    medium = Column(SAEnum(InterviewMedium), nullable=False)
    location = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    job = relationship("Job", back_populates="interviews", foreign_keys=[job_id])


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

    experiences = relationship("ProfileExperience", cascade="all, delete-orphan", order_by="ProfileExperience.display_order")
    educations = relationship("ProfileEducation", cascade="all, delete-orphan", order_by="ProfileEducation.display_order")


class ProfileExperience(Base):
    __tablename__ = "profile_experiences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("profile.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(300), nullable=True)
    company = Column(String(300), nullable=True)
    location = Column(String(300), nullable=True)
    start_date = Column(String(20), nullable=True)
    end_date = Column(String(20), nullable=True)
    is_current = Column(Boolean, default=False, nullable=False, server_default="0")
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)


class ProfileEducation(Base):
    __tablename__ = "profile_educations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("profile.id", ondelete="CASCADE"), nullable=False)
    school = Column(String(300), nullable=True)
    degree = Column(String(300), nullable=True)
    field_of_study = Column(String(300), nullable=True)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    grade = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)


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
    include_comeet = Column(Boolean, default=False, nullable=False, server_default="0")


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
    watch_rule_id = Column(Integer, nullable=True)  # null for interview reminders
    is_read = Column(Boolean, default=False)
    kind = Column(String(30), default='watch_match', nullable=False)
    interview_id = Column(Integer, nullable=True, index=True)
    message = Column(String(300), nullable=True)
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
    trigger = Column(String(20), nullable=True)  # "scheduled" or "manual"
    linkedin_count = Column(Integer, nullable=True)
    indeed_count = Column(Integer, nullable=True)
    glassdoor_count = Column(Integer, nullable=True)
    comeet_count = Column(Integer, nullable=True)
    filter_blocked = Column(Integer, nullable=True)
    filter_keywords = Column(Integer, nullable=True)
    filter_salary = Column(Integer, nullable=True)
    filter_remote = Column(Integer, nullable=True)
    jobs_scored = Column(Integer, nullable=True)
    score_failed = Column(Integer, nullable=True)


class SchedulerConfig(Base):
    """Single-row table that persists scheduler settings."""
    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interval_hours = Column(Integer, default=6, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    # JSON array of job sources the cleanup run should check (e.g. ["indeed", "comeet"]).
    # NULL means "all sources" (backward-compatible default).
    cleanup_sources = Column(Text, nullable=True)
    # Max number of jobs to check per cleanup run; NULL means "no limit" (all).
    cleanup_limit = Column(Integer, nullable=True)
    # Skip jobs validated within the past N hours during cleanup; NULL/0 = don't skip.
    cleanup_skip_validated_hours = Column(Integer, nullable=True)
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


class TailoredCV(Base):
    """A CV tailored by LLM for one specific job. One row per job_id."""
    __tablename__ = "tailored_cvs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, unique=True, nullable=False)
    cv_json = Column(Text, nullable=False)
    pdf_path = Column(Text, nullable=True)
    docx_path = Column(Text, nullable=True)
    model_used = Column(Text, nullable=True)
    generated_at = Column(DateTime, server_default=func.now(), nullable=False)


class SimilarityWeights(Base):
    """Single-row table storing the spider-chart weights for the similarity engine."""
    __tablename__ = "similarity_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    weight_title = Column(Float, default=1.0, nullable=False, server_default="1.0")
    weight_skills = Column(Float, default=1.0, nullable=False, server_default="1.0")
    weight_seniority = Column(Float, default=1.0, nullable=False, server_default="1.0")
    weight_sector = Column(Float, default=1.0, nullable=False, server_default="1.0")
    is_enabled = Column(Boolean, default=True, nullable=False, server_default="1")
    min_score_threshold = Column(Integer, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UploadedCV(Base):
    """Stores a user-uploaded LinkedIn PDF profile and its parsed JSON. Single-user app — latest row wins."""
    __tablename__ = "uploaded_cvs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    parsed_json = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)
