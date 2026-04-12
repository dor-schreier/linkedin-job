"""Route tests for Phase 4: profile editor + AI Insights + per-job score button."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_session
from app import models  # noqa
from app.routes import pages as pages_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _p(c, _):
        cur = c.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
            conn.commit()
        except Exception:
            pass

    Sess = sessionmaker(bind=engine)

    def _get_session_override():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _get_session_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_profile_renders_form(client):
    r = client.get("/profile")
    assert r.status_code == 200
    for name in ("linkedin_url", "skills", "current_title", "target_title", "years_experience"):
        assert f'name="{name}"' in r.text


def test_post_profile_persists_and_redirects(client):
    r = client.post(
        "/profile",
        data={
            "linkedin_url": "https://x",
            "skills": "py",
            "current_title": "Dev",
            "target_title": "Sr Dev",
            "years_experience": "5",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    r2 = client.get("/profile")
    assert 'value="https://x"' in r2.text
    assert 'value="Dev"' in r2.text
    assert 'value="Sr Dev"' in r2.text


def test_profile_page_always_renders_ai_insights_div(client):
    r = client.get("/profile")
    assert 'id="ai-insights"' in r.text


def test_profile_page_renders_persisted_bullets(client):
    client.post(
        "/profile",
        data={
            "linkedin_url": "https://x",
            "skills": "py",
            "current_title": "Dev",
            "target_title": "Sr",
            "years_experience": "3",
        },
    )
    # Manually set ai_recommendations via repo to simulate prior analyze
    from app.repository import JobRepository

    gen = app.dependency_overrides[get_session]()
    s = next(gen)
    JobRepository(s).upsert_profile(ai_recommendations="bullet one\nbullet two")
    try:
        next(gen)
    except StopIteration:
        pass
    r = client.get("/profile")
    assert "bullet one" in r.text
    assert "bullet two" in r.text


def test_post_analyze_without_profile_returns_save_first(client):
    r = client.post("/profile/analyze")
    assert r.status_code == 200
    assert "Save your profile first" in r.text


def test_post_analyze_with_profile_calls_groq_and_persists(client, monkeypatch):
    client.post(
        "/profile",
        data={
            "linkedin_url": "",
            "skills": "python",
            "current_title": "Dev",
            "target_title": "Sr Dev",
            "years_experience": "5",
        },
    )
    monkeypatch.setattr(
        pages_module.groq_service,
        "get_profile_recommendations",
        lambda profile: ["alpha", "beta", "gamma"],
    )
    r = client.post("/profile/analyze")
    assert r.status_code == 200
    assert "alpha" in r.text and "beta" in r.text and "gamma" in r.text
    # And persisted: a fresh GET shows them too
    r2 = client.get("/profile")
    assert "alpha" in r2.text


# ---------------------------------------------------------------------------
# Task 2: Per-job score endpoint tests
# ---------------------------------------------------------------------------
from app.routes import jobs as jobs_module
from app.repository import JobRepository
from app.database import get_session


def _seed_job(client_fixture, **kw):
    gen = app.dependency_overrides[get_session]()
    s = next(gen)
    defaults = dict(
        title="Backend Engineer",
        company="Acme",
        location="NYC",
        description="Build APIs",
        source="linkedin",
        job_hash="seed-hash",
    )
    defaults.update(kw)
    j = JobRepository(s).add_job(**defaults)
    jid = j.id
    try:
        next(gen)
    except StopIteration:
        pass
    return jid


def _seed_profile():
    gen = app.dependency_overrides[get_session]()
    s = next(gen)
    JobRepository(s).upsert_profile(
        linkedin_url="https://x",
        skills="python",
        current_title="Dev",
        target_title="Sr Dev",
        years_experience=5,
    )
    try:
        next(gen)
    except StopIteration:
        pass


def test_score_nonexistent_job_returns_404(client):
    r = client.post("/jobs/99999/score")
    assert r.status_code == 404


def test_score_without_profile_returns_save_first(client):
    jid = _seed_job(client)
    r = client.post(f"/jobs/{jid}/score")
    assert r.status_code == 200
    assert "Save your profile first" in r.text


def test_score_with_profile_persists_and_renders(client, monkeypatch):
    jid = _seed_job(client)
    _seed_profile()
    monkeypatch.setattr(
        jobs_module.groq_service,
        "get_fit_score_and_salary",
        lambda job, profile: {
            "fit_score": 85,
            "fit_summary": "great fit",
            "salary_estimated": "$100k-$120k",
        },
    )
    r = client.post(f"/jobs/{jid}/score")
    assert r.status_code == 200
    assert "85" in r.text
    assert "Excellent" in r.text
    assert "great fit" in r.text
    # Re-render via /jobs and confirm score is on the card
    r2 = client.get("/jobs")
    assert "85" in r2.text


def test_score_for_listed_salary_does_not_show_estimated(client, monkeypatch):
    jid = _seed_job(
        client, salary_min=100000.0, salary_max=120000.0, salary_currency="$", job_hash="listed-h"
    )
    _seed_profile()
    monkeypatch.setattr(
        jobs_module.groq_service,
        "get_fit_score_and_salary",
        lambda job, profile: {"fit_score": 70, "fit_summary": "ok", "salary_estimated": None},
    )
    r = client.post(f"/jobs/{jid}/score")
    assert "Estimated" not in r.text
    assert "70" in r.text and "Good" in r.text


def test_score_for_unlisted_salary_shows_estimated_label(client, monkeypatch):
    jid = _seed_job(client, job_hash="unlisted-h")
    _seed_profile()
    monkeypatch.setattr(
        jobs_module.groq_service,
        "get_fit_score_and_salary",
        lambda job, profile: {
            "fit_score": 65,
            "fit_summary": "ok",
            "salary_estimated": "$90k-$110k",
        },
    )
    r = client.post(f"/jobs/{jid}/score")
    assert "Estimated" in r.text
    assert "$90k-$110k" in r.text


@pytest.mark.parametrize(
    "score,label", [(30, "Poor"), (50, "Fair"), (70, "Good"), (90, "Excellent")]
)
def test_fit_label_thresholds(client, monkeypatch, score, label):
    jid = _seed_job(client, job_hash=f"thr-{score}")
    _seed_profile()
    monkeypatch.setattr(
        jobs_module.groq_service,
        "get_fit_score_and_salary",
        lambda job, profile, _s=score: {"fit_score": _s, "fit_summary": "x", "salary_estimated": None},
    )
    r = client.post(f"/jobs/{jid}/score")
    assert label in r.text
