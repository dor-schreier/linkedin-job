"""Unit tests for GoogleCseBackend."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.scrapers.search_backends import GoogleCseBackend, SearchBackendBlocked


def _make_cse_response(links: list[str], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = b"x"
    resp.json.return_value = {
        "items": [{"link": u} for u in links]
    }
    return resp


@pytest.fixture(autouse=True)
def cse_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CSE_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_CSE_CX", "test-cx")


class TestGoogleCseBackendSearch:
    def test_returns_links_on_200(self):
        links = ["https://comeet.com/jobs/acme/1", "https://comeet.com/jobs/acme/2"]
        with patch("requests.get", return_value=_make_cse_response(links)) as mock_get:
            backend = GoogleCseBackend()
            result = backend.search("software engineer", max_results=10)
        assert result == links
        mock_get.assert_called_once()

    def test_raises_on_429(self):
        resp = MagicMock()
        resp.status_code = 429
        with patch("requests.get", return_value=resp):
            with pytest.raises(SearchBackendBlocked, match="429"):
                GoogleCseBackend().search("q", max_results=5)

    def test_raises_on_403_quota(self):
        resp = MagicMock()
        resp.status_code = 403
        resp.content = b"x"
        resp.json.return_value = {
            "error": {"errors": [{"reason": "dailyLimitExceeded"}]}
        }
        with patch("requests.get", return_value=resp):
            with pytest.raises(SearchBackendBlocked, match="quota"):
                GoogleCseBackend().search("q", max_results=5)

    def test_raises_on_403_auth(self):
        resp = MagicMock()
        resp.status_code = 403
        resp.content = b"x"
        resp.json.return_value = {"error": {"errors": [{"reason": "forbidden"}]}}
        with patch("requests.get", return_value=resp):
            with pytest.raises(SearchBackendBlocked, match="auth failure"):
                GoogleCseBackend().search("q", max_results=5)

    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CSE_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CSE_CX", raising=False)
        with pytest.raises(SearchBackendBlocked, match="not configured"):
            GoogleCseBackend().search("q", max_results=5)

    def test_pagination_25_results_triggers_3_calls(self):
        page1 = [f"https://comeet.com/jobs/a/{i}" for i in range(10)]
        page2 = [f"https://comeet.com/jobs/b/{i}" for i in range(10)]
        page3 = [f"https://comeet.com/jobs/c/{i}" for i in range(5)]

        responses = [
            _make_cse_response(page1),
            _make_cse_response(page2),
            _make_cse_response(page3),
        ]

        with patch("requests.get", side_effect=responses) as mock_get:
            backend = GoogleCseBackend()
            result = backend.search("engineer", max_results=25)

        assert mock_get.call_count == 3
        # Verify start indices: 1, 11, 21
        starts = [call.kwargs["params"]["start"] for call in mock_get.call_args_list]
        assert starts == [1, 11, 21]
        assert len(result) == 25

    def test_stops_early_when_fewer_items_than_requested(self):
        # API returns 3 items when we asked for 10 — only 1 call should be made
        resp = _make_cse_response(["https://comeet.com/jobs/x/1"] * 3)
        with patch("requests.get", return_value=resp) as mock_get:
            result = GoogleCseBackend().search("q", max_results=10)
        assert mock_get.call_count == 1
        assert len(result) == 3
