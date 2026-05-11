"""Tests for Comeet scraper — no real network access."""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "comeet"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _make_http_response(html: str = "", status: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = html
    return mock_resp


_LLM_FULL = {
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "location": "Tel Aviv, Israel",
    "description": "We are looking for a Senior Backend Engineer.",
    "date_posted": "2024-01-15",
    "salary_min": None,
    "salary_max": None,
    "salary_currency": None,
    "is_remote": False,
    "company_industry": None,
    "company_description": None,
}


class TestIsComeetJobUrl:
    def test_accepts_valid_job_url(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert _is_comeet_job_url("https://www.comeet.com/jobs/acme-corp/XX.123/software-engineer/abc123")

    def test_rejects_company_page(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.comeet.com/jobs/acme-corp/")

    def test_rejects_category_page(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.comeet.com/jobs/acme-corp/engineering/")

    def test_rejects_4_segment_url(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.comeet.com/jobs/acme/XX.123/dev")

    def test_rejects_6_segment_url(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.comeet.com/jobs/a/XX.1/b/c/extra")

    def test_rejects_position_code_without_dot(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.comeet.com/jobs/acme/nodot/software-engineer/abc123")

    def test_rejects_non_comeet_domain(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert not _is_comeet_job_url("https://www.linkedin.com/jobs/acme/XX.1/dev/id")

    def test_accepts_comeet_co_domain(self):
        from app.scrapers.comeet import _is_comeet_job_url
        assert _is_comeet_job_url("https://www.comeet.co/jobs/acme-corp/XX.123/software-engineer/abc123")


class TestDiscoverComeetUrls:
    def test_returns_comeet_urls_only(self):
        from app.scrapers.comeet import discover_comeet_urls

        mock_backend = MagicMock()
        mock_backend.search.return_value = [
            "https://www.comeet.com/jobs/acme/XX.001/senior-engineer/id1",
            "https://www.google.com/some-other-page",
            "https://www.comeet.com/jobs/beta-corp/XX.002/frontend-dev/id2",
            "https://linkedin.com/jobs/view/999",
        ]

        with patch("app.scrapers.comeet.get_search_backend", return_value=mock_backend):
            urls = discover_comeet_urls("backend engineer")

        assert len(urls) == 2
        assert all("comeet.com/jobs/" in u for u in urls)

    def test_deduplicates_urls(self):
        from app.scrapers.comeet import discover_comeet_urls

        mock_backend = MagicMock()
        mock_backend.search.return_value = [
            "https://www.comeet.com/jobs/acme/XX.001/senior-engineer/id1",
            "https://www.comeet.com/jobs/acme/XX.001/senior-engineer/id1",
            "https://www.comeet.com/jobs/acme/XX.001/senior-engineer/id1",
        ]

        with patch("app.scrapers.comeet.get_search_backend", return_value=mock_backend):
            urls = discover_comeet_urls("backend")

        assert len(urls) == 1

    def test_falls_back_to_playwright_on_blocked(self):
        from app.scrapers.comeet import discover_comeet_urls
        from app.scrapers.search_backends import SearchBackendBlocked

        primary_backend = MagicMock()
        primary_backend.search.side_effect = SearchBackendBlocked("Rate limited by Google")

        playwright_backend = MagicMock()
        playwright_backend.search.return_value = [
            "https://www.comeet.com/jobs/fallback-corp/XX.789/python-dev/id3",
        ]

        with (
            patch("app.scrapers.comeet.get_search_backend", return_value=primary_backend),
            patch("app.scrapers.comeet.PlaywrightGoogleBackend", return_value=playwright_backend),
        ):
            urls = discover_comeet_urls("python")

        playwright_backend.search.assert_called_once()
        assert len(urls) == 1
        assert "fallback-corp" in urls[0]

    def test_empty_results_when_no_comeet_urls(self):
        from app.scrapers.comeet import discover_comeet_urls

        mock_backend = MagicMock()
        mock_backend.search.return_value = [
            "https://www.linkedin.com/jobs/123",
            "https://indeed.com/job/456",
        ]

        with patch("app.scrapers.comeet.get_search_backend", return_value=mock_backend):
            urls = discover_comeet_urls("engineer")

        assert urls == []


class TestScrapeComeetJob:
    def test_llm_invoked_with_stripped_text_and_url(self):
        """LLM is called with stripped page text (no script/style) and the original URL."""
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("happy_path.html")
        url = "https://www.comeet.com/jobs/acme-corp/senior-engineer/abc"

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response(html)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=dict(_LLM_FULL)) as mock_llm,
        ):
            scrape_comeet_job(url)

        mock_llm.assert_called_once()
        page_text_arg, url_arg = mock_llm.call_args[0]
        assert url_arg == url
        assert "<script>" not in page_text_arg
        assert "<style>" not in page_text_arg
        assert "javascript" not in page_text_arg.lower()
        assert "Backend Engineer" in page_text_arg

    def test_llm_fields_flow_through(self):
        """All LLM dict fields including salary/remote/industry appear in the return value."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {
            "title": "Backend Engineer",
            "company": "TechCo",
            "location": "Remote, USA",
            "description": "Great role at a great company.",
            "date_posted": "2024-03-01",
            "salary_min": 80000.0,
            "salary_max": 120000.0,
            "salary_currency": "USD",
            "is_remote": True,
            "company_industry": "Software",
            "company_description": "A fast-growing SaaS company.",
        }

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response("<html/>")),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job("https://www.comeet.com/jobs/techco/be/123")

        assert result is not None
        assert result["title"] == "Backend Engineer"
        assert result["company"] == "TechCo"
        assert result["location"] == "Remote, USA"
        assert result["salary_min"] == 80000.0
        assert result["salary_max"] == 120000.0
        assert result["salary_currency"] == "USD"
        assert result["is_remote"] is True
        assert result["company_industry"] == "Software"
        assert result["company_description"] == "A fast-growing SaaS company."
        assert result["date_posted"] == datetime.date(2024, 3, 1)
        assert result["job_url"] == "https://www.comeet.com/jobs/techco/be/123"

    def test_llm_returns_none_makes_scraper_return_none(self):
        """LLM failure (returns None) causes scrape_comeet_job to return None."""
        from app.scrapers.comeet import scrape_comeet_job

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response("<html/>")),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=None),
        ):
            result = scrape_comeet_job("https://www.comeet.com/jobs/co/role/1")

        assert result is None

    def test_empty_company_falls_back_to_url_slug(self):
        """Empty company from LLM falls back to slug derived from URL path."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "company": None}

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response("<html/>")),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job("https://www.comeet.com/jobs/acme-corp/dev/1")

        assert result is not None
        assert result["company"] == "Acme Corp"

    def test_empty_title_from_llm_returns_none(self):
        """LLM returning empty title causes scrape_comeet_job to return None."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "title": ""}

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response("<html/>")),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job("https://www.comeet.com/jobs/co/role/1")

        assert result is None

    def test_404_returns_none(self):
        from app.scrapers.comeet import scrape_comeet_job

        with patch("app.scrapers.comeet.requests.get", return_value=_make_http_response(status=404)):
            result = scrape_comeet_job("https://www.comeet.com/jobs/gone/position/000")

        assert result is None

    def test_missing_date_posted_returns_none_for_field(self):
        """date_posted is None when LLM returns null for that field."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "date_posted": None}

        with (
            patch("app.scrapers.comeet.requests.get", return_value=_make_http_response("<html/>")),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job("https://www.comeet.com/jobs/co/role/1")

        assert result is not None
        assert result["date_posted"] is None


class TestHtmlToLlmText:
    def test_strips_script_style_nav_header_footer(self):
        """Script/style/nav/header/footer are removed; visible job text survives."""
        from app.scrapers.comeet import _html_to_llm_text

        html = _read_fixture("happy_path.html")
        result = _html_to_llm_text(html)

        assert "<script>" not in result
        assert "<style>" not in result
        assert "javascript" not in result.lower()
        assert "tracking" not in result.lower()
        assert "Backend Engineer" in result
        assert "PostgreSQL" in result

    def test_truncates_to_max_chars(self):
        from app.scrapers.comeet import _html_to_llm_text

        html = "<html><body>" + "x" * 20000 + "</body></html>"
        result = _html_to_llm_text(html, max_chars=100)

        assert len(result) <= 100


class TestUrlToCompanySlug:
    def test_hyphenated_slug(self):
        from app.scrapers.comeet import _slug_to_company

        assert _slug_to_company("acme-corp") == "Acme Corp"

    def test_multi_word_slug(self):
        from app.scrapers.comeet import _slug_to_company

        assert _slug_to_company("some-tech-startup") == "Some Tech Startup"

    def test_single_word_slug(self):
        from app.scrapers.comeet import _slug_to_company

        assert _slug_to_company("google") == "Google"


class TestStubSeams:
    def test_serpapi_raises_not_implemented(self):
        from app.scrapers.search_backends import SerpApiBackend

        backend = SerpApiBackend()
        with pytest.raises(NotImplementedError, match="SerpAPI backend not yet implemented"):
            backend.search("test query", 10)

    def test_google_cse_raises_backend_blocked_when_unconfigured(self):
        from app.scrapers.search_backends import GoogleCseBackend, SearchBackendBlocked

        backend = GoogleCseBackend()
        with pytest.raises(SearchBackendBlocked):
            backend.search("test query", 10)
