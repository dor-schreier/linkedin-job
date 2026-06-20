"""Tests for Comeet scraper — no real network access."""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "comeet"

_VALID_URL = "https://www.comeet.com/jobs/acme-corp/XX.001/senior-backend-engineer/abc123"
_BEEWISE_URL = "https://www.comeet.com/jobs/beewise/0B.001/hardware-team-lead/E5.A61"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


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


class TestLooksLikeJobPage:
    def test_true_for_jsonld_jobposting(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _looks_like_job_page

        html = _read_fixture("jsonld_job.html")
        soup = BeautifulSoup(html, "html.parser")
        assert _looks_like_job_page(soup) is True

    def test_true_for_single_h1(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _looks_like_job_page

        html = "<html><body><h1>Software Engineer</h1><p>Job description here.</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert _looks_like_job_page(soup) is True

    def test_false_for_company_listing_page(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _looks_like_job_page

        html = _read_fixture("company_listing.html")
        soup = BeautifulSoup(html, "html.parser")
        assert _looks_like_job_page(soup) is False

    def test_false_for_many_job_links(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _looks_like_job_page

        links = "\n".join(
            f'<a href="https://www.comeet.com/jobs/co/XX.{i:03d}/title/id{i}">Job {i}</a>'
            for i in range(5)
        )
        html = f"<html><body><h1>Open Positions</h1>{links}</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert _looks_like_job_page(soup) is False

    def test_true_by_default_for_ambiguous_page(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _looks_like_job_page

        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert _looks_like_job_page(soup) is True


class TestExtractJsonldJobposting:
    def test_extracts_title_company_location(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = _read_fixture("jsonld_job.html")
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_jsonld_jobposting(soup)

        assert result is not None
        assert result["title"] == "Hardware Team Lead"
        assert result["company"] == "Beewise"
        assert "Tel Aviv" in result["location"]

    def test_extracts_salary_fields(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = _read_fixture("jsonld_job.html")
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_jsonld_jobposting(soup)

        assert result is not None
        assert result["salary_min"] == 30000
        assert result["salary_max"] == 50000
        assert result["salary_currency"] == "ILS"

    def test_strips_html_from_description(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = _read_fixture("jsonld_job.html")
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_jsonld_jobposting(soup)

        assert result is not None
        assert "<p>" not in result["description"]
        assert "<ul>" not in result["description"]
        assert "Lead our hardware engineering team" in result["description"]

    def test_returns_none_when_no_jsonld(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = _read_fixture("happy_path.html")
        soup = BeautifulSoup(html, "html.parser")
        assert _extract_jsonld_jobposting(soup) is None

    def test_returns_none_for_non_jobposting_jsonld(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = """<html><head>
        <script type="application/ld+json">{"@type": "Organization", "name": "Acme"}</script>
        </head><body></body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        assert _extract_jsonld_jobposting(soup) is None

    def test_detects_remote_from_job_location_type(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = """<html><head>
        <script type="application/ld+json">{
          "@type": "JobPosting",
          "title": "Remote Dev",
          "jobLocationType": "TELECOMMUTE",
          "hiringOrganization": {"name": "Co"}
        }</script>
        </head><body></body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_jsonld_jobposting(soup)
        assert result is not None
        assert result["is_remote"] is True

    def test_date_posted_extracted(self):
        from bs4 import BeautifulSoup
        from app.scrapers.comeet import _extract_jsonld_jobposting

        html = _read_fixture("jsonld_job.html")
        soup = BeautifulSoup(html, "html.parser")
        result = _extract_jsonld_jobposting(soup)
        assert result is not None
        assert result["date_posted"] == "2024-03-10"


class TestFetchComeetHtml:
    def test_returns_none_on_playwright_navigation_error(self):
        from app.scrapers.comeet import _fetch_comeet_html

        with patch("app.scrapers.comeet.sync_playwright") as mock_pw:
            mock_pw.side_effect = Exception("browser crashed")
            html, url = _fetch_comeet_html("https://www.comeet.com/jobs/co/XX.1/role/id")

        assert html is None
        assert url is None

    def test_returns_none_on_404(self):
        from app.scrapers.comeet import _fetch_comeet_html

        mock_response = MagicMock()
        mock_response.status = 404

        mock_page = MagicMock()
        mock_page.goto.return_value = mock_response

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        with patch("app.scrapers.comeet.sync_playwright") as mock_pw_ctx:
            mock_pw_ctx.return_value.__enter__ = lambda s, *a: mock_pw_instance
            mock_pw_ctx.return_value.__exit__ = MagicMock(return_value=False)
            html, url = _fetch_comeet_html("https://www.comeet.com/jobs/co/XX.1/role/id")

        assert html is None
        assert url is None

    def test_returns_html_and_final_url_on_success(self):
        from app.scrapers.comeet import _fetch_comeet_html

        mock_response = MagicMock()
        mock_response.status = 200

        mock_page = MagicMock()
        mock_page.goto.return_value = mock_response
        mock_page.content.return_value = "<html><body><h1>Job</h1></body></html>"
        mock_page.url = "https://www.comeet.com/jobs/co/XX.1/role/id"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        with patch("app.scrapers.comeet.sync_playwright") as mock_pw_ctx:
            mock_pw_ctx.return_value.__enter__ = lambda s, *a: mock_pw_instance
            mock_pw_ctx.return_value.__exit__ = MagicMock(return_value=False)
            html, url = _fetch_comeet_html("https://www.comeet.com/jobs/co/XX.1/role/id")

        assert html == "<html><body><h1>Job</h1></body></html>"
        assert url == "https://www.comeet.com/jobs/co/XX.1/role/id"


class TestScrapeComeetJob:
    def test_jsonld_used_as_primary_extraction(self):
        """When JSON-LD JobPosting is present, it is used and LLM is not called."""
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("jsonld_job.html")
        url = _BEEWISE_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=(html, url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields") as mock_llm,
        ):
            result = scrape_comeet_job(url)

        mock_llm.assert_not_called()
        assert result is not None
        assert result["title"] == "Hardware Team Lead"
        assert result["company"] == "Beewise"
        assert result["salary_min"] == 30000
        assert result["date_posted"] == datetime.date(2024, 3, 10)

    def test_llm_used_as_fallback_when_no_jsonld(self):
        """LLM is called when no JSON-LD is present; stripped text (no scripts) is passed."""
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("happy_path.html")
        url = _VALID_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=(html, url)),
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
            "salary_min": 80100.0,
            "salary_max": 120000.0,
            "salary_currency": "USD",
            "is_remote": True,
            "company_industry": "Software",
            "company_description": "A fast-growing SaaS company.",
        }
        url = _VALID_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=("<html/>", url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job(url)

        assert result is not None
        assert result["title"] == "Backend Engineer"
        assert result["company"] == "TechCo"
        assert result["location"] == "Remote, USA"
        assert result["salary_min"] == 80100.0
        assert result["salary_max"] == 120000.0
        assert result["salary_currency"] == "USD"
        assert result["is_remote"] is True
        assert result["company_industry"] == "Software"
        assert result["company_description"] == "A fast-growing SaaS company."
        assert result["date_posted"] == datetime.date(2024, 3, 1)
        assert result["job_url"] == url

    def test_company_listing_page_returns_none(self):
        """Company/careers listing pages are detected and skipped."""
        from app.scrapers.comeet import scrape_comeet_job

        html = _read_fixture("company_listing.html")
        url = _BEEWISE_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=(html, url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields") as mock_llm,
        ):
            result = scrape_comeet_job(url)

        assert result is None
        mock_llm.assert_not_called()

    def test_fetch_failure_returns_none(self):
        """_fetch_comeet_html returning (None, None) causes scrape_comeet_job to return None."""
        from app.scrapers.comeet import scrape_comeet_job

        with patch("app.scrapers.comeet._fetch_comeet_html", return_value=(None, None)):
            result = scrape_comeet_job(_VALID_URL)

        assert result is None

    def test_redirect_to_non_job_url_returns_none(self):
        """If the final URL after redirect is not a job page, return None."""
        from app.scrapers.comeet import scrape_comeet_job

        final_url = "https://www.comeet.com/jobs/beewise/"  # company page, not a job
        with patch("app.scrapers.comeet._fetch_comeet_html", return_value=("<html/>", final_url)):
            result = scrape_comeet_job(_VALID_URL)

        assert result is None

    def test_empty_company_falls_back_to_url_slug(self):
        """Empty company from LLM falls back to slug derived from URL path."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "company": None}
        url = _VALID_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=("<html/>", url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job(url)

        assert result is not None
        assert result["company"] == "Acme Corp"

    def test_empty_title_falls_back_to_url_slug(self):
        """Empty title from LLM falls back to slug derived from URL title segment."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "title": ""}
        url = _VALID_URL  # segment 3 = "senior-backend-engineer"

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=("<html/>", url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job(url)

        assert result is not None
        assert result["title"] == "Senior Backend Engineer"

    def test_missing_date_posted_returns_none_for_field(self):
        """date_posted is None when LLM returns null for that field."""
        from app.scrapers.comeet import scrape_comeet_job

        llm_return = {**_LLM_FULL, "date_posted": None}
        url = _VALID_URL

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=("<html/>", url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=llm_return),
        ):
            result = scrape_comeet_job(url)

        assert result is not None
        assert result["date_posted"] is None

    def test_jsonld_incomplete_title_falls_back_to_llm(self):
        """JSON-LD block with empty title falls back to LLM extraction."""
        from app.scrapers.comeet import scrape_comeet_job

        url = _VALID_URL
        html = """<html><head>
        <script type="application/ld+json">{"@type": "JobPosting", "title": "", "hiringOrganization": {"name": "Co"}}</script>
        </head><body><h1>Engineer</h1></body></html>"""

        with (
            patch("app.scrapers.comeet._fetch_comeet_html", return_value=(html, url)),
            patch("app.scrapers.comeet.extract_comeet_job_fields", return_value=dict(_LLM_FULL)) as mock_llm,
        ):
            result = scrape_comeet_job(url)

        mock_llm.assert_called_once()
        assert result is not None
        assert result["title"] == _LLM_FULL["title"]


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


class TestSlugToTitle:
    def test_derives_title_from_segment_3(self):
        from app.scrapers.comeet import _slug_to_title
        url = "https://www.comeet.com/jobs/acme-corp/XX.001/hardware-team-lead/abc123"
        assert _slug_to_title(url) == "Hardware Team Lead"

    def test_handles_single_word_slug(self):
        from app.scrapers.comeet import _slug_to_title
        url = "https://www.comeet.com/jobs/co/XX.1/engineer/id"
        assert _slug_to_title(url) == "Engineer"

    def test_returns_empty_for_short_url(self):
        from app.scrapers.comeet import _slug_to_title
        assert _slug_to_title("https://www.comeet.com/jobs/co") == ""

    def test_returns_empty_on_malformed_url(self):
        from app.scrapers.comeet import _slug_to_title
        assert _slug_to_title("not-a-url") == ""


class TestComeetIdentity:
    def test_returns_stable_identity(self):
        from app.scrapers.comeet import _comeet_identity
        url = "https://www.comeet.com/jobs/acme-corp/A1.234/senior-backend-engineer/abc123"
        assert _comeet_identity(url) == "acme-corp/A1.234/abc123"

    def test_different_title_slug_same_identity(self):
        """Two URLs that differ only in title slug must produce the same identity."""
        from app.scrapers.comeet import _comeet_identity
        url1 = "https://www.comeet.com/jobs/acme-corp/A1.234/senior-backend-engineer/abc123"
        url2 = "https://www.comeet.com/jobs/acme-corp/A1.234/SENIOR-BACKEND-ENGINEER-REVISED/abc123"
        assert _comeet_identity(url1) == _comeet_identity(url2)

    def test_different_position_code_different_identity(self):
        from app.scrapers.comeet import _comeet_identity
        url1 = "https://www.comeet.com/jobs/acme-corp/A1.234/engineer/abc123"
        url2 = "https://www.comeet.com/jobs/acme-corp/B2.567/engineer/abc123"
        assert _comeet_identity(url1) != _comeet_identity(url2)

    def test_different_job_id_different_identity(self):
        from app.scrapers.comeet import _comeet_identity
        url1 = "https://www.comeet.com/jobs/acme-corp/A1.234/engineer/abc123"
        url2 = "https://www.comeet.com/jobs/acme-corp/A1.234/engineer/xyz999"
        assert _comeet_identity(url1) != _comeet_identity(url2)

    def test_malformed_url_returns_none(self):
        from app.scrapers.comeet import _comeet_identity
        assert _comeet_identity("https://www.comeet.com/jobs/acme-corp/") is None
        assert _comeet_identity("https://www.linkedin.com/jobs/1234") is None
        assert _comeet_identity("not-a-url") is None

    def test_no_dot_in_position_code_returns_none(self):
        from app.scrapers.comeet import _comeet_identity
        assert _comeet_identity("https://www.comeet.com/jobs/acme/nodot/engineer/abc") is None


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
