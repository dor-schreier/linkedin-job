"""Tests for Comeet scraper — no real network access."""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "comeet"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestDiscoverComeetUrls:
    def test_returns_comeet_urls_only(self):
        from app.scrapers.comeet import discover_comeet_urls

        mock_backend = MagicMock()
        mock_backend.search.return_value = [
            "https://www.comeet.com/jobs/acme/senior-engineer/123",
            "https://www.google.com/some-other-page",
            "https://www.comeet.com/jobs/beta-corp/frontend-dev/456",
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
            "https://www.comeet.com/jobs/acme/senior-engineer/123",
            "https://www.comeet.com/jobs/acme/senior-engineer/123",
            "https://www.comeet.com/jobs/acme/senior-engineer/123",
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
            "https://www.comeet.com/jobs/fallback-corp/python-dev/999",
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
    def test_happy_path(self):
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("happy_path.html")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("app.scrapers.comeet.requests.get", return_value=mock_resp):
            result = scrape_comeet_job("https://www.comeet.com/jobs/acme-corp/senior-engineer/abc")

        assert result is not None
        assert result["title"] == "Senior Backend Engineer"
        assert result["company"] == "Acme Corp"
        assert result["location"] == "Tel Aviv, Israel"
        assert "Backend Engineer" in result["description"]
        assert result["date_posted"] == datetime.date(2024, 1, 15)
        assert result["job_url"] == "https://www.comeet.com/jobs/acme-corp/senior-engineer/abc"

    def test_missing_location_returns_empty_string(self):
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("missing_location.html")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("app.scrapers.comeet.requests.get", return_value=mock_resp):
            result = scrape_comeet_job("https://www.comeet.com/jobs/tech-startup/frontend-dev/def")

        assert result is not None
        assert result["title"] == "Frontend Developer"
        assert result["location"] == ""

    def test_404_returns_none(self):
        from app.scrapers.comeet import scrape_comeet_job

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("app.scrapers.comeet.requests.get", return_value=mock_resp):
            result = scrape_comeet_job("https://www.comeet.com/jobs/gone/position/000")

        assert result is None

    def test_empty_page_no_h1_no_og_title_returns_none(self):
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("empty_page.html")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        with patch("app.scrapers.comeet.requests.get", return_value=mock_resp):
            result = scrape_comeet_job("https://www.comeet.com/jobs/old/position/999")

        assert result is None


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

    def test_google_cse_raises_not_implemented(self):
        from app.scrapers.search_backends import GoogleCseBackend

        backend = GoogleCseBackend()
        with pytest.raises(NotImplementedError, match="Google CSE backend not yet implemented"):
            backend.search("test query", 10)
