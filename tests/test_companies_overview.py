"""Tests for GET /api/companies/overview and the underlying repository method."""
import hashlib
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models  # registers tables on Base.metadata
from app.models import Company, Job, JobStatus
from app.repository import JobRepository, VALID_JOB_MAX_AGE_DAYS


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _job_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _make_company(session, name: str, sector=None, company_type=None, what_they_do=None) -> Company:
    c = Company(
        name_normalized=name.lower(),
        name_display=name,
        sector=sector,
        company_type=company_type,
        what_they_do=what_they_do,
    )
    session.add(c)
    session.flush()
    return c


def _make_job(
    session,
    company: str,
    company_id=None,
    location=None,
    is_active=True,
    is_rejected=False,
    status=JobStatus.NEW,
    seed=None,
    apply_url="https://example.com/apply",
    date_posted=None,
    scraped_at=None,
) -> Job:
    j = Job(
        title="Engineer",
        company=company,
        company_id=company_id,
        location=location,
        source="linkedin",
        job_hash=_job_hash(seed or f"{company}{location}{id(object())}"),
        status=status,
        is_rejected=is_rejected,
        apply_url=apply_url,
        date_posted=date_posted,
    )
    # Set is_active after construction — the model's @validates('is_rejected')
    # validator overwrites is_active when is_rejected=False, so we patch it here.
    j.is_active = is_active
    if scraped_at is not None:
        j.scraped_at = scraped_at
    session.add(j)
    session.flush()
    return j


# ── only active jobs counted ───────────────────────────────────────────────────

def test_only_active_jobs_counted(session):
    co = _make_company(session, "Acme")
    _make_job(session, "Acme", company_id=co.id, location="TLV", seed="a1")
    _make_job(session, "Acme", company_id=co.id, location="TLV", is_active=False, seed="a2")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    assert result[0]["name_display"] == "Acme"
    assert result[0]["total_active_jobs"] == 1


# ── rejected jobs excluded ─────────────────────────────────────────────────────

def test_rejected_jobs_excluded(session):
    co = _make_company(session, "Beta Corp")
    _make_job(session, "Beta Corp", company_id=co.id, seed="b1")
    _make_job(session, "Beta Corp", company_id=co.id, is_rejected=True, is_active=False, seed="b2")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    assert result[0]["total_active_jobs"] == 1


# ── company with zero active jobs not included ────────────────────────────────

def test_company_with_no_active_jobs_excluded(session):
    co = _make_company(session, "Ghost Inc")
    _make_job(session, "Ghost Inc", company_id=co.id, is_active=False, seed="g1")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert result == []


# ── null sector / type handled ────────────────────────────────────────────────

def test_null_sector_and_type_returned(session):
    co = _make_company(session, "NullCo", sector=None, company_type=None)
    _make_job(session, "NullCo", company_id=co.id, seed="n1")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    assert result[0]["sector"] is None
    assert result[0]["company_type"] is None


# ── company with jobs in 2 locations reports both ────────────────────────────

def test_company_with_two_locations(session):
    co = _make_company(session, "Multisite")
    _make_job(session, "Multisite", company_id=co.id, location="Tel Aviv", seed="m1")
    _make_job(session, "Multisite", company_id=co.id, location="Remote", seed="m2")
    _make_job(session, "Multisite", company_id=co.id, location="Tel Aviv", seed="m3")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    c = result[0]
    assert c["total_active_jobs"] == 3
    locs = {item["location"]: item["count"] for item in c["location_breakdown"]}
    assert locs["Tel Aviv"] == 2
    assert locs["Remote"] == 1


# ── company without Company row falls back to job.company string ──────────────

def test_company_without_company_row(session):
    _make_job(session, "Orphan Ltd", company_id=None, location="NY", seed="o1")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    c = result[0]
    assert c["name_display"] == "Orphan Ltd"
    assert c["company_id"] is None
    assert c["sector"] is None
    assert c["company_type"] is None
    assert c["total_active_jobs"] == 1


# ── null location bucketed into "Unknown / Unspecified" ───────────────────────

def test_null_location_bucketed(session):
    _make_job(session, "NoLoc", company_id=None, location=None, seed="nl1")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    locs = {item["location"] for item in result[0]["location_breakdown"]}
    assert "Unknown / Unspecified" in locs


# ── validity filters: stale jobs excluded ────────────────────────────────────

def test_company_with_only_stale_jobs_excluded(session):
    co = _make_company(session, "OldCo")
    stale_at = datetime.utcnow() - timedelta(days=VALID_JOB_MAX_AGE_DAYS + 1)
    _make_job(session, "OldCo", company_id=co.id, seed="s1", scraped_at=stale_at)
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert result == []


def test_company_with_fresh_and_stale_jobs_counts_only_fresh(session):
    co = _make_company(session, "MixedAge")
    stale_at = datetime.utcnow() - timedelta(days=VALID_JOB_MAX_AGE_DAYS + 5)
    _make_job(session, "MixedAge", company_id=co.id, location="TLV", seed="ma1")
    _make_job(session, "MixedAge", company_id=co.id, location="TLV", seed="ma2", scraped_at=stale_at)
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    assert result[0]["total_active_jobs"] == 1


# ── validity filters: missing apply_url excluded ─────────────────────────────

def test_company_with_only_null_apply_url_excluded(session):
    co = _make_company(session, "NoURL")
    _make_job(session, "NoURL", company_id=co.id, seed="nu1", apply_url=None)
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert result == []


def test_company_with_only_empty_apply_url_excluded(session):
    co = _make_company(session, "EmptyURL")
    _make_job(session, "EmptyURL", company_id=co.id, seed="eu1", apply_url="")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert result == []


def test_company_with_mixed_apply_url_counts_only_valid(session):
    co = _make_company(session, "PartialURL")
    _make_job(session, "PartialURL", company_id=co.id, location="NY", seed="pu1")
    _make_job(session, "PartialURL", company_id=co.id, location="NY", seed="pu2", apply_url=None)
    _make_job(session, "PartialURL", company_id=co.id, location="NY", seed="pu3", apply_url="")
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert len(result) == 1
    assert result[0]["total_active_jobs"] == 1


# ── validity filters: rejected-only company excluded (regression) ─────────────

def test_company_with_only_rejected_jobs_excluded(session):
    co = _make_company(session, "RejectedCo")
    _make_job(session, "RejectedCo", company_id=co.id, seed="r1", is_rejected=True, is_active=False)
    session.commit()

    repo = JobRepository(session)
    result = repo.get_companies_with_active_jobs()
    assert result == []
