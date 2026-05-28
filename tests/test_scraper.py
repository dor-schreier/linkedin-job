"""Unit tests for scraper pure functions — no network, no DB required."""
import hashlib

import pytest


# ---------------------------------------------------------------------------
# _compute_hash
# ---------------------------------------------------------------------------

def test_compute_hash_deterministic():
    """Same inputs always produce the same hash."""
    from app.scraper import _compute_hash

    h1 = _compute_hash("Software Engineer", "Google", "NYC")
    h2 = _compute_hash("Software Engineer", "Google", "NYC")
    assert h1 == h2


def test_compute_hash_is_sha256():
    """Hash matches expected SHA-256 of lowercased pipe-joined string."""
    from app.scraper import _compute_hash

    raw = "software engineer|google|nyc"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert _compute_hash("Software Engineer", "Google", "NYC") == expected


def test_compute_hash_case_insensitive():
    """Hash is the same regardless of title/company/location casing."""
    from app.scraper import _compute_hash

    h1 = _compute_hash("Software Engineer", "Google", "NYC")
    h2 = _compute_hash("SOFTWARE ENGINEER", "GOOGLE", "nyc")
    assert h1 == h2


def test_compute_hash_strips_whitespace():
    """Leading/trailing whitespace does not affect hash output."""
    from app.scraper import _compute_hash

    h1 = _compute_hash("Software Engineer", "Google", "NYC")
    h2 = _compute_hash("  Software Engineer  ", "  Google  ", "  NYC  ")
    assert h1 == h2


def test_compute_hash_returns_64_char_hex():
    """SHA-256 hex digest is always 64 characters."""
    from app.scraper import _compute_hash

    h = _compute_hash("Engineer", "Acme", "Remote")
    assert len(h) == 64
    int(h, 16)  # must be valid hex


# ---------------------------------------------------------------------------
# _normalize_row
# ---------------------------------------------------------------------------

def _make_row(**overrides):
    """Return a complete valid row dict, with optional field overrides."""
    base = {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "New York, NY",
        "description": "Great job description",
        "site": "linkedin",
        "job_url": "https://linkedin.com/jobs/123",
        "min_amount": 100000.0,
        "max_amount": 150000.0,
        "currency": "USD",
        "is_remote": False,
    }
    base.update(overrides)
    return base


def test_normalize_row_complete_row():
    """All fields extracted correctly from a complete row."""
    from app.scraper import _normalize_row

    result = _normalize_row(_make_row())
    assert result is not None
    assert result["title"] == "Software Engineer"
    assert result["company"] == "Acme Corp"
    assert result["location"] == "New York, NY"
    assert result["description"] == "Great job description"
    assert result["source"] == "linkedin"
    assert result["apply_url"] == "https://linkedin.com/jobs/123"
    assert result["salary_min"] == 100000.0
    assert result["salary_max"] == 150000.0
    assert result["salary_currency"] == "USD"
    assert "job_hash" in result
    assert len(result["job_hash"]) == 64


def test_normalize_row_filters_remote():
    """Returns None when is_remote is True."""
    from app.scraper import _normalize_row

    assert _normalize_row(_make_row(is_remote=True)) is None


def test_normalize_row_filters_empty_title():
    """Returns None when title is empty or whitespace-only."""
    from app.scraper import _normalize_row

    assert _normalize_row(_make_row(title="")) is None
    assert _normalize_row(_make_row(title="   ")) is None


def test_normalize_row_nan_string_fields():
    """NaN string fields coerce to empty string, not 'nan'."""
    import math
    from app.scraper import _normalize_row

    nan = float("nan")
    result = _normalize_row(_make_row(title="Engineer", description=nan, location=nan))
    assert result is not None
    assert result["description"] == ""
    # location NaN -> empty string; title still valid
    assert result["location"] == ""


def test_normalize_row_nan_salary_fields():
    """NaN salary fields become None, not 'nan' string."""
    import math
    from app.scraper import _normalize_row

    nan = float("nan")
    result = _normalize_row(_make_row(min_amount=nan, max_amount=nan, currency=nan))
    assert result is not None
    assert result["salary_min"] is None
    assert result["salary_max"] is None
    assert result["salary_currency"] == ""  # currency is a string field, coerced to ""


def test_normalize_row_missing_optional_fields():
    """Missing optional fields default safely without KeyError."""
    from app.scraper import _normalize_row

    minimal = {"title": "Engineer", "company": "Acme", "site": "indeed"}
    result = _normalize_row(minimal)
    assert result is not None
    assert result["location"] == ""
    assert result["description"] == ""
    assert result["apply_url"] == ""
    assert result["salary_min"] is None
    assert result["salary_max"] is None
    assert result["salary_currency"] == ""


def test_normalize_row_none_values():
    """None values are handled the same as missing fields."""
    from app.scraper import _normalize_row

    row = _make_row(description=None, location=None, min_amount=None, max_amount=None)
    result = _normalize_row(row)
    assert result is not None
    assert result["description"] == ""
    assert result["location"] == ""
    assert result["salary_min"] is None
    assert result["salary_max"] is None


# ---------------------------------------------------------------------------
# Comeet URL-derived dedup hash
# ---------------------------------------------------------------------------

_COMEET_BASE = "https://www.comeet.com/jobs/acme-corp/A1.234"


def _comeet_row(**overrides):
    base = {
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "location": "Tel Aviv",
        "description": "desc",
        "site": "comeet",
        "job_url": f"{_COMEET_BASE}/senior-backend-engineer/abc123",
        "min_amount": None,
        "max_amount": None,
        "currency": "",
        "is_remote": False,
    }
    base.update(overrides)
    return base


def test_comeet_same_url_different_title_same_hash():
    """Two Comeet rows with the same URL but different LLM-extracted titles get the same job_hash."""
    from app.scraper import _normalize_row

    row1 = _comeet_row(title="Senior Backend Engineer")
    row2 = _comeet_row(title="SENIOR BACKEND ENGINEER — REVISED BY LLM")
    r1 = _normalize_row(row1)
    r2 = _normalize_row(row2)
    assert r1 is not None and r2 is not None
    assert r1["job_hash"] == r2["job_hash"]


def test_comeet_different_postings_different_hash():
    """Two different Comeet postings (different position-code) produce distinct hashes."""
    from app.scraper import _normalize_row

    row1 = _comeet_row(job_url=f"{_COMEET_BASE}/engineer/abc123")
    row2 = _comeet_row(job_url="https://www.comeet.com/jobs/acme-corp/B2.567/engineer/xyz999")
    r1 = _normalize_row(row1)
    r2 = _normalize_row(row2)
    assert r1 is not None and r2 is not None
    assert r1["job_hash"] != r2["job_hash"]


def test_comeet_malformed_url_falls_back_to_legacy_hash():
    """Malformed Comeet URL (site=comeet but bad URL) falls back to title+company+location hash."""
    from app.scraper import _normalize_row, _compute_hash

    row = _comeet_row(job_url="https://www.comeet.com/jobs/acme-corp/")
    result = _normalize_row(row)
    assert result is not None
    expected = _compute_hash(row["title"], row["company"], row["location"])
    assert result["job_hash"] == expected


def test_non_comeet_rows_use_legacy_hash():
    """LinkedIn/Indeed/Glassdoor rows still use SHA256(title+company+location)."""
    from app.scraper import _normalize_row, _compute_hash

    for site in ("linkedin", "indeed", "glassdoor"):
        row = _make_row(site=site)
        result = _normalize_row(row)
        assert result is not None
        expected = _compute_hash(row["title"], row["company"], row["location"])
        assert result["job_hash"] == expected, f"Legacy hash mismatch for site={site}"
