"""Tests for JD intelligence extraction: extract_job_intelligence, rate limiter, scraper hook."""
from __future__ import annotations

import json
import time
import types
from unittest.mock import MagicMock, patch

import pytest

from app.services import llm_service as gs


# ---------------------------------------------------------------------------
# Fake Groq helpers (reuse pattern from test_groq_service.py)
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content_or_exc):
        self._c = content_or_exc

    def create(self, **kwargs):
        if isinstance(self._c, Exception):
            raise self._c
        return _FakeResponse(self._c)


class _FakeGroqClient:
    def __init__(self, content_or_exc):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(content_or_exc))


def _make_job(**kwargs):
    defaults = dict(title="Software Engineer", company="Acme", location="NYC", description="Python, SQL required. Nice to have: Go. Fast-paced environment.")
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


VALID_INTELLIGENCE_JSON = json.dumps({
    "required_skills": ["Python", "SQL"],
    "preferred_skills": ["Go"],
    "seniority_level": "mid",
    "remote_policy": "hybrid",
    "tech_stack": ["Django", "PostgreSQL"],
    "team_size_signals": None,
    "salary_signals": None,
    "red_flags": ["fast-paced environment"],
})


# ---------------------------------------------------------------------------
# Unit tests: extract_job_intelligence
# ---------------------------------------------------------------------------

def test_extract_job_intelligence_returns_valid_dict(monkeypatch):
    monkeypatch.setattr(gs, "_get_client", lambda: _FakeGroqClient(VALID_INTELLIGENCE_JSON))
    monkeypatch.setattr(gs, "_rate_limit", lambda: None)

    job = _make_job()
    result = gs.extract_job_intelligence(job)

    assert result is not None
    assert result["required_skills"] == ["Python", "SQL"]
    assert result["preferred_skills"] == ["Go"]
    assert result["seniority_level"] == "mid"
    assert result["remote_policy"] == "hybrid"
    assert result["tech_stack"] == ["Django", "PostgreSQL"]
    assert result["red_flags"] == ["fast-paced environment"]


def test_extract_job_intelligence_returns_none_on_groq_exception(monkeypatch):
    monkeypatch.setattr(gs, "_get_client", lambda: _FakeGroqClient(RuntimeError("network error")))
    monkeypatch.setattr(gs, "_rate_limit", lambda: None)

    result = gs.extract_job_intelligence(_make_job())
    assert result is None


def test_extract_job_intelligence_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(gs, "_get_client", lambda: _FakeGroqClient("not json at all {{{"))
    monkeypatch.setattr(gs, "_rate_limit", lambda: None)

    result = gs.extract_job_intelligence(_make_job())
    assert result is None


def test_extract_job_intelligence_returns_none_on_schema_validation_failure(monkeypatch):
    # Missing required fields
    bad = json.dumps({"required_skills": "not a list"})
    monkeypatch.setattr(gs, "_get_client", lambda: _FakeGroqClient(bad))
    monkeypatch.setattr(gs, "_rate_limit", lambda: None)

    result = gs.extract_job_intelligence(_make_job())
    assert result is None


def test_extract_job_intelligence_empty_description(monkeypatch):
    monkeypatch.setattr(gs, "_get_client", lambda: _FakeGroqClient(VALID_INTELLIGENCE_JSON))
    monkeypatch.setattr(gs, "_rate_limit", lambda: None)

    result = gs.extract_job_intelligence(_make_job(description=""))
    assert result is not None  # fallback JSON is valid; should not raise


# ---------------------------------------------------------------------------
# Unit tests: rate limiter
# ---------------------------------------------------------------------------

def test_rate_limiter_enforces_minimum_interval(monkeypatch):
    """Rate limiter should sleep when calls come too fast."""
    calls = []
    # _last_groq_call = 10.0, then call at now=10.5 → elapsed=0.5 < 2.0 → sleep 1.5
    mono_values = iter([10.5, 12.5])
    monkeypatch.setattr(gs.time, "monotonic", lambda: next(mono_values))
    monkeypatch.setattr(gs.time, "sleep", lambda s: calls.append(s))
    monkeypatch.setattr(gs, "_groq_min_interval", 2.0)
    gs._last_llm_call = 10.0

    gs._rate_limit()

    assert len(calls) == 1
    assert calls[0] == pytest.approx(1.5, abs=0.01)


def test_rate_limiter_no_sleep_after_sufficient_gap(monkeypatch):
    """Rate limiter should not sleep when enough time has passed."""
    calls = []
    # _last_llm_call=10.0, now=15.0 → elapsed=5.0 > 2.0 → no sleep
    mono_values = iter([15.0, 15.0])
    monkeypatch.setattr(gs.time, "monotonic", lambda: next(mono_values))
    monkeypatch.setattr(gs.time, "sleep", lambda s: calls.append(s))
    monkeypatch.setattr(gs, "_groq_min_interval", 2.0)
    gs._last_llm_call = 10.0

    gs._rate_limit()

    assert calls == []


# ---------------------------------------------------------------------------
# Integration tests: scraper pipeline (no pandas dependency)
# ---------------------------------------------------------------------------

def _make_fake_df(rows):
    """Build a minimal DataFrame-like object without pandas."""
    class _FakeRow:
        def __init__(self, data):
            self._data = data
        def to_dict(self):
            return dict(self._data)

    class _FakeDF:
        def __init__(self, rows):
            self._rows = [_FakeRow(r) for r in rows]
        def __len__(self):
            return len(self._rows)
        def iterrows(self):
            return enumerate(self._rows)

    return _FakeDF(rows)


def _patch_jobspy(fake_df):
    """Insert a fake jobspy module into sys.modules so scraper can import it."""
    import sys
    fake_module = types.ModuleType("jobspy")
    fake_module.scrape_jobs = lambda **kw: fake_df
    sys.modules.setdefault("jobspy", fake_module)
    return patch.dict("sys.modules", {"jobspy": fake_module})


def test_scraper_writes_intelligence_json_for_new_jobs():
    """Scraper with skip_intelligence=False should call extract and persist."""
    fake_job = types.SimpleNamespace(
        id=1, title="Engineer", company="Corp", location="NY",
        description="Python needed", intelligence_json=None,
    )
    intel_result = {
        "required_skills": ["Python"], "preferred_skills": [], "seniority_level": "mid",
        "remote_policy": "onsite", "tech_stack": [], "team_size_signals": None,
        "salary_signals": None, "red_flags": [],
    }
    calls = []

    def fake_extract(job):
        calls.append(job)
        return intel_result

    fake_df = _make_fake_df([{
        "title": "Engineer", "company": "Corp", "location": "NY",
        "description": "Python needed", "site": "linkedin", "job_url": "http://x.com",
        "currency": "USD", "min_amount": None, "max_amount": None, "is_remote": False,
    }])

    mock_repo = MagicMock()
    mock_repo.get_job_by_hash.return_value = None
    mock_repo.add_job.return_value = fake_job
    mock_session = MagicMock()

    with _patch_jobspy(fake_df), \
         patch("app.scraper.SessionLocal") as mock_sl, \
         patch("app.scraper.JobRepository", return_value=mock_repo), \
         patch("app.services.llm_service.extract_job_intelligence", side_effect=fake_extract), \
         patch("app.services.watch_service.match_new_jobs_to_watch_rules", return_value=0):
        mock_sl.return_value.__enter__ = lambda s: mock_session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)

        from app.scraper import run_scrape
        result = run_scrape(keywords="python", location="NY", skip_intelligence=False)

    assert len(calls) == 1
    assert fake_job.intelligence_json == json.dumps(intel_result)


def test_scraper_failed_extraction_does_not_abort_batch():
    """A single failing extraction must not prevent other jobs from being inserted."""
    def make_fake_job(i):
        return types.SimpleNamespace(id=i, title=f"Job {i}", company="Corp", location="NY",
                                     description="desc", intelligence_json=None)

    job_iter = iter([make_fake_job(i) for i in range(3)])

    fake_df = _make_fake_df([
        {"title": f"Job {i}", "company": "Corp", "location": "NY",
         "description": "desc", "site": "linkedin", "job_url": f"http://x/{i}",
         "currency": "USD", "min_amount": None, "max_amount": None, "is_remote": False}
        for i in range(3)
    ])

    mock_repo = MagicMock()
    mock_repo.get_job_by_hash.return_value = None
    mock_repo.add_job.side_effect = lambda **kw: next(job_iter)
    mock_session = MagicMock()

    with _patch_jobspy(fake_df), \
         patch("app.scraper.SessionLocal") as mock_sl, \
         patch("app.scraper.JobRepository", return_value=mock_repo), \
         patch("app.services.llm_service.extract_job_intelligence", side_effect=RuntimeError("boom")), \
         patch("app.services.watch_service.match_new_jobs_to_watch_rules", return_value=0):
        mock_sl.return_value.__enter__ = lambda s: mock_session
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)

        from app.scraper import run_scrape
        result = run_scrape(keywords="python", location="NY", skip_intelligence=False)

    assert "error" not in result
    assert result["inserted"] == 3


# ---------------------------------------------------------------------------
# Integration tests: reextract endpoint
# ---------------------------------------------------------------------------

def test_reextract_endpoint_updates_row_and_returns_partial():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock

    fake_job = types.SimpleNamespace(
        id=42, title="Dev", company="Corp", location="NY", description="Python",
        intelligence_json=None, fit_score=None, fit_summary=None,
        score_breakdown_json=None, apply_url=None,
    )
    intel_result = {
        "required_skills": ["Python"], "preferred_skills": [], "seniority_level": "mid",
        "remote_policy": "hybrid", "tech_stack": [], "team_size_signals": None,
        "salary_signals": None, "red_flags": [],
    }

    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    with patch("app.routes.jobs.JobRepository") as MockRepo, \
         patch("app.routes.jobs.groq_service.extract_job_intelligence", return_value=intel_result), \
         patch("app.database.get_session", return_value=iter([mock_db])):
        mock_repo = MagicMock()
        mock_repo.get_job.return_value = fake_job
        mock_repo.count_unread_notifications.return_value = 0
        MockRepo.return_value = mock_repo

        from app.main import app
        client = TestClient(app)
        resp = client.post("/jobs/42/reextract")

    assert resp.status_code == 200
    assert fake_job.intelligence_json == json.dumps(intel_result)


def test_reextract_endpoint_404_on_unknown_id():
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock

    with patch("app.routes.jobs.JobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_job.return_value = None
        MockRepo.return_value = mock_repo

        from app.main import app
        client = TestClient(app)
        resp = client.post("/jobs/9999/reextract")

    assert resp.status_code == 404
