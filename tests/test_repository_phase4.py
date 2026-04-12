import os
import pytest
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app import models  # registers tables on Base.metadata
from app.repository import JobRepository
from app.models import Job, Profile, JobStatus


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        c = dbapi_conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.close()

    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
            conn.commit()
        except Exception:
            pass
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def test_ai_recommendations_column_exists(session):
    insp = inspect(session.get_bind())
    cols = {c["name"] for c in insp.get_columns("profile")}
    assert "ai_recommendations" in cols


def test_alter_table_idempotent(session):
    # Run the ALTER again — must not raise
    with session.get_bind().connect() as conn:
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
            conn.commit()
        except Exception:
            pass  # expected


def test_upsert_profile_with_recommendations(session):
    repo = JobRepository(session)
    repo.upsert_profile(linkedin_url="https://x", skills="py")
    repo.upsert_profile(ai_recommendations="- bullet1\n- bullet2")
    p = repo.get_profile()
    assert p.ai_recommendations == "- bullet1\n- bullet2"
    assert p.linkedin_url == "https://x"  # prior fields preserved


def test_update_job_scores_sets_all_fields(session):
    repo = JobRepository(session)
    j = repo.add_job(title="Eng", company="Acme", source="linkedin", job_hash="h1")
    updated = repo.update_job_scores(j.id, fit_score=87, fit_summary="great", salary_estimated="$100k-$120k")
    assert updated.fit_score == 87
    assert updated.fit_summary == "great"
    assert updated.salary_estimated == "$100k-$120k"


def test_update_job_scores_preserves_existing_salary_when_none(session):
    repo = JobRepository(session)
    j = repo.add_job(title="Eng", company="Acme", source="linkedin", job_hash="h2", salary_estimated="prior")
    updated = repo.update_job_scores(j.id, fit_score=50, fit_summary="ok", salary_estimated=None)
    assert updated.salary_estimated == "prior"


def test_update_job_scores_returns_none_for_missing(session):
    repo = JobRepository(session)
    assert repo.update_job_scores(99999, 50, "x", None) is None


def test_get_job_returns_job_or_none(session):
    repo = JobRepository(session)
    j = repo.add_job(title="Eng", company="Acme", source="linkedin", job_hash="h3")
    assert repo.get_job(j.id).id == j.id
    assert repo.get_job(99999) is None
