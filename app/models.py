import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base


class JobStatus(enum.Enum):
    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"


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
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_url = Column(String(500), nullable=True)
    skills = Column(Text, nullable=True)
    current_title = Column(String(300), nullable=True)
    target_title = Column(String(300), nullable=True)
    years_experience = Column(Integer, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keywords = Column(String(500), nullable=False)
    location = Column(String(300), nullable=True)
    experience_level = Column(String(50), nullable=True)
    work_mode = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


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
