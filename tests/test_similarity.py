"""Unit tests for the similarity engine."""
import json
import pytest
from unittest.mock import MagicMock

from app.services.similarity_service import (
    TargetProfile,
    build_target_profile,
    title_sim,
    skills_sim,
    seniority_sim,
    sector_sim,
    compute_similarity,
    _normalize_tokens,
    _extract_seniority,
    _extract_skills,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_job(
    title="Software Engineer",
    intelligence_json=None,
    summary_tech_stack_json=None,
    summary_qualifications_json=None,
    company_info=None,
):
    job = MagicMock()
    job.title = title
    job.intelligence_json = json.dumps(intelligence_json) if intelligence_json else None
    job.summary_tech_stack_json = json.dumps(summary_tech_stack_json) if summary_tech_stack_json else None
    job.summary_qualifications_json = json.dumps(summary_qualifications_json) if summary_qualifications_json else None
    job.company_info = company_info
    return job


def _make_weights(title=1.0, skills=1.0, seniority=1.0, sector=1.0, is_enabled=True):
    w = MagicMock()
    w.weight_title = title
    w.weight_skills = skills
    w.weight_seniority = seniority
    w.weight_sector = sector
    w.is_enabled = is_enabled
    return w


def _make_profile(
    title_tokens=None,
    skill_union=None,
    seniority_levels=None,
    sector_pairs=None,
):
    return TargetProfile(
        title_tokens=set(title_tokens or []),
        skill_union=set(skill_union or []),
        seniority_levels=set(seniority_levels or []),
        sector_pairs=set(sector_pairs or []),
    )


# ── Token normalization ────────────────────────────────────────────────────────

def test_normalize_tokens_basic():
    assert _normalize_tokens("Senior Software Engineer") == {"senior", "software", "engineer"}


def test_normalize_tokens_strips_punctuation():
    tokens = _normalize_tokens("C++ Developer, Full-Stack")
    assert "developer" in tokens
    assert "full" in tokens


# ── Seniority extraction ──────────────────────────────────────────────────────

def test_extract_seniority_from_intelligence():
    job = _make_job(intelligence_json={"seniority_level": "Senior"})
    assert _extract_seniority(job) == "senior"


def test_extract_seniority_alias():
    job = _make_job(intelligence_json={"seniority_level": "Sr."})
    assert _extract_seniority(job) == "senior"


def test_extract_seniority_missing():
    job = _make_job()
    assert _extract_seniority(job) is None


# ── Skills extraction ─────────────────────────────────────────────────────────

def test_extract_skills_from_intelligence():
    job = _make_job(intelligence_json={"required_skills": ["Python"], "tech_stack": ["FastAPI"]})
    skills = _extract_skills(job)
    assert "python" in skills
    assert "fastapi" in skills


def test_extract_skills_from_summary():
    job = _make_job(summary_tech_stack_json=["React", "TypeScript"])
    skills = _extract_skills(job)
    assert "react" in skills
    assert "typescript" in skills


# ── title_sim ─────────────────────────────────────────────────────────────────

def test_title_sim_exact():
    profile = _make_profile(title_tokens=["software", "engineer"])
    job = _make_job(title="Software Engineer")
    assert title_sim(job.title, profile) == 1.0


def test_title_sim_partial():
    profile = _make_profile(title_tokens=["software", "engineer", "senior"])
    job = _make_job(title="Software Engineer")
    sim = title_sim(job.title, profile)
    assert 0 < sim < 1


def test_title_sim_no_overlap():
    profile = _make_profile(title_tokens=["product", "manager"])
    job = _make_job(title="Software Engineer")
    assert title_sim(job.title, profile) == 0.0


def test_title_sim_empty_profile():
    profile = _make_profile(title_tokens=[])
    job = _make_job(title="Software Engineer")
    assert title_sim(job.title, profile) == 0.0


# ── skills_sim ────────────────────────────────────────────────────────────────

def test_skills_sim_full_overlap():
    profile = _make_profile(skill_union=["python", "fastapi"])
    job = _make_job(intelligence_json={"required_skills": ["Python"], "tech_stack": ["FastAPI"], "preferred_skills": []})
    assert skills_sim(job, profile) == 1.0


def test_skills_sim_no_overlap():
    profile = _make_profile(skill_union=["java", "spring"])
    job = _make_job(intelligence_json={"required_skills": ["Python"], "tech_stack": [], "preferred_skills": []})
    assert skills_sim(job, profile) == 0.0


def test_skills_sim_empty_profile():
    profile = _make_profile(skill_union=[])
    job = _make_job(intelligence_json={"required_skills": ["Python"], "tech_stack": [], "preferred_skills": []})
    assert skills_sim(job, profile) == 0.0


# ── seniority_sim ─────────────────────────────────────────────────────────────

def test_seniority_sim_exact():
    profile = _make_profile(seniority_levels=["senior"])
    job = _make_job(intelligence_json={"seniority_level": "Senior"})
    assert seniority_sim(job, profile) == 1.0


def test_seniority_sim_adjacent():
    profile = _make_profile(seniority_levels=["senior"])
    job = _make_job(intelligence_json={"seniority_level": "Staff"})
    assert seniority_sim(job, profile) == 0.5


def test_seniority_sim_far():
    profile = _make_profile(seniority_levels=["junior"])
    job = _make_job(intelligence_json={"seniority_level": "Director"})
    assert seniority_sim(job, profile) == 0.0


def test_seniority_sim_missing_job():
    profile = _make_profile(seniority_levels=["senior"])
    job = _make_job()
    assert seniority_sim(job, profile) is None


def test_seniority_sim_empty_profile():
    profile = _make_profile(seniority_levels=[])
    job = _make_job(intelligence_json={"seniority_level": "Senior"})
    assert seniority_sim(job, profile) is None


# ── sector_sim ────────────────────────────────────────────────────────────────

def test_sector_sim_exact_match():
    co = MagicMock()
    co.sector = "FinTech"
    co.company_type = "startup"
    profile = _make_profile(sector_pairs=[("fintech", "startup")])
    job = _make_job(company_info=co)
    assert sector_sim(job, profile) == 1.0


def test_sector_sim_partial_match():
    co = MagicMock()
    co.sector = "FinTech"
    co.company_type = "corporate"
    profile = _make_profile(sector_pairs=[("fintech", "startup")])
    job = _make_job(company_info=co)
    sim = sector_sim(job, profile)
    assert 0 < sim < 1


def test_sector_sim_no_company_info():
    profile = _make_profile(sector_pairs=[("fintech", "startup")])
    job = _make_job(company_info=None)
    assert sector_sim(job, profile) is None


def test_sector_sim_empty_profile():
    co = MagicMock()
    co.sector = "FinTech"
    co.company_type = "startup"
    profile = _make_profile(sector_pairs=[])
    job = _make_job(company_info=co)
    assert sector_sim(job, profile) is None


# ── compute_similarity ────────────────────────────────────────────────────────

def test_compute_similarity_all_dimensions():
    profile = _make_profile(
        title_tokens=["software", "engineer"],
        skill_union=["python"],
        seniority_levels=["senior"],
        sector_pairs=[("fintech", "startup")],
    )
    co = MagicMock()
    co.sector = "FinTech"
    co.company_type = "startup"
    job = _make_job(
        title="Senior Software Engineer",
        intelligence_json={"required_skills": ["Python"], "tech_stack": [], "preferred_skills": [], "seniority_level": "Senior"},
        company_info=co,
    )
    weights = _make_weights()
    result = compute_similarity(job, profile, weights)
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert "breakdown" in result
    assert "title" in result["breakdown"]
    assert "skills" in result["breakdown"]
    assert "seniority" in result["breakdown"]
    assert "sector" in result["breakdown"]


def test_compute_similarity_missing_dimension_renormalized():
    """Missing seniority and sector shouldn't zero out the score."""
    profile = _make_profile(
        title_tokens=["software", "engineer"],
        skill_union=["python"],
        seniority_levels=[],  # no seniority in profile → None
        sector_pairs=[],      # no sector info
    )
    job = _make_job(
        title="Software Engineer",
        intelligence_json={"required_skills": ["Python"], "tech_stack": [], "preferred_skills": []},
        company_info=None,
    )
    weights = _make_weights(title=1.0, skills=1.0, seniority=1.0, sector=1.0)
    result = compute_similarity(job, profile, weights)
    # Only title and skills should contribute
    assert result["score"] > 0
    assert "seniority" not in result["breakdown"]
    assert "sector" not in result["breakdown"]


def test_compute_similarity_zero_weights():
    profile = _make_profile(title_tokens=["software", "engineer"])
    job = _make_job(title="Software Engineer")
    weights = _make_weights(title=0.0, skills=0.0, seniority=0.0, sector=0.0)
    result = compute_similarity(job, profile, weights)
    assert result["score"] == 0


def test_compute_similarity_empty_profile_returns_zero():
    profile = _make_profile()
    job = _make_job(title="Software Engineer")
    weights = _make_weights()
    result = compute_similarity(job, profile, weights)
    assert result["score"] == 0


# ── build_target_profile with no targets ──────────────────────────────────────

def test_build_target_profile_no_targets():
    session = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_target_jobs.return_value = []

    import app.services.similarity_service as svc
    import app.repository as repo_mod
    original = repo_mod.JobRepository

    repo_mod.JobRepository = lambda s: mock_repo
    try:
        result = build_target_profile(session)
        assert result is None
    finally:
        repo_mod.JobRepository = original
