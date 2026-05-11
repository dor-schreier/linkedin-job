"""Unit tests for search backends."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.scrapers.search_backends import (
    GoogleCseBackend,
    SearchBackendBlocked,
    VertexAiSearchBackend,
    get_search_backend,
)


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


# ── Vertex AI Search backend tests ────────────────────────────────────────────

def _make_vertex_result(link: str) -> MagicMock:
    result = MagicMock()
    result.document.derived_struct_data = {"link": link}
    return result


@pytest.fixture()
def vertex_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    monkeypatch.setenv("VERTEX_AI_DATA_STORE_ID", "my-data-store")
    monkeypatch.setenv("VERTEX_AI_LOCATION", "global")


class TestVertexAiSearchBackend:
    def test_returns_links_on_success(self, vertex_env):
        links = ["https://comeet.com/jobs/acme/1", "https://comeet.com/jobs/acme/2"]
        mock_pager = [_make_vertex_result(l) for l in links]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter(mock_pager)
            result = VertexAiSearchBackend().search("software engineer", max_results=10)

        assert result == links

    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("VERTEX_AI_DATA_STORE_ID", raising=False)
        with pytest.raises(SearchBackendBlocked, match="not configured"):
            VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_when_project_missing(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.setenv("VERTEX_AI_DATA_STORE_ID", "my-store")
        with pytest.raises(SearchBackendBlocked, match="not configured"):
            VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_when_data_store_missing(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
        monkeypatch.delenv("VERTEX_AI_DATA_STORE_ID", raising=False)
        with pytest.raises(SearchBackendBlocked, match="not configured"):
            VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_on_permission_denied(self, vertex_env):
        from google.api_core import exceptions as google_exceptions

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = google_exceptions.PermissionDenied("denied")
            with pytest.raises(SearchBackendBlocked, match="permission denied"):
                VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_on_unauthenticated(self, vertex_env):
        from google.api_core import exceptions as google_exceptions

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = google_exceptions.Unauthenticated("unauth")
            with pytest.raises(SearchBackendBlocked, match="unauthenticated"):
                VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_on_resource_exhausted(self, vertex_env):
        from google.api_core import exceptions as google_exceptions

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = google_exceptions.ResourceExhausted("quota")
            with pytest.raises(SearchBackendBlocked, match="quota exhausted"):
                VertexAiSearchBackend().search("q", max_results=5)

    def test_raises_on_invalid_argument(self, vertex_env):
        from google.api_core import exceptions as google_exceptions

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = google_exceptions.InvalidArgument("bad arg")
            with pytest.raises(SearchBackendBlocked, match="invalid argument"):
                VertexAiSearchBackend().search("q", max_results=5)

    def test_pagination_stops_at_max_results(self, vertex_env):
        # Pager has 20 results but we only want 5
        all_links = [f"https://comeet.com/jobs/a/{i}" for i in range(20)]
        mock_pager = [_make_vertex_result(l) for l in all_links]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter(mock_pager)
            result = VertexAiSearchBackend().search("engineer", max_results=5)

        assert len(result) == 5
        assert result == all_links[:5]

    def test_empty_result_returns_empty_list(self, vertex_env):
        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter([])
            result = VertexAiSearchBackend().search("q", max_results=10)
        assert result == []

    def test_skips_results_without_link(self, vertex_env):
        no_link = MagicMock()
        no_link.document.derived_struct_data = {}
        with_link = _make_vertex_result("https://comeet.com/jobs/x/1")
        mock_pager = [no_link, with_link]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter(mock_pager)
            result = VertexAiSearchBackend().search("q", max_results=10)

        assert result == ["https://comeet.com/jobs/x/1"]

    def test_pagination_makes_multiple_requests(self, vertex_env, monkeypatch):
        monkeypatch.setenv("VERTEX_AI_QUERY_EXPANSION", "disabled")
        monkeypatch.setenv("VERTEX_AI_MAX_RESULTS", "30")

        page1 = [_make_vertex_result(f"https://comeet.com/jobs/a/XX.{i}/dev/id{i}") for i in range(10)]
        page2 = [_make_vertex_result(f"https://comeet.com/jobs/b/XX.{i}/dev/id{i}") for i in range(10)]
        page3 = [_make_vertex_result(f"https://comeet.com/jobs/c/XX.{i}/dev/id{i}") for i in range(5)]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = [iter(page1), iter(page2), iter(page3)]
            result = VertexAiSearchBackend().search("engineer", max_results=25)

        assert MockClient.return_value.search.call_count == 3
        offsets = [call.args[0].offset for call in MockClient.return_value.search.call_args_list]
        assert offsets == [0, 10, 20]
        assert len(result) == 25

    def test_pagination_stops_when_fewer_results_than_batch(self, vertex_env, monkeypatch):
        monkeypatch.setenv("VERTEX_AI_QUERY_EXPANSION", "disabled")

        page1 = [_make_vertex_result(f"https://comeet.com/jobs/a/XX.{i}/dev/id{i}") for i in range(10)]
        page2 = [_make_vertex_result(f"https://comeet.com/jobs/b/XX.{i}/dev/id{i}") for i in range(3)]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.side_effect = [iter(page1), iter(page2)]
            result = VertexAiSearchBackend().search("engineer", max_results=30)

        assert MockClient.return_value.search.call_count == 2
        assert len(result) == 13

    def test_query_expansion_included_by_default(self, vertex_env, monkeypatch):
        monkeypatch.delenv("VERTEX_AI_QUERY_EXPANSION", raising=False)
        from google.cloud import discoveryengine_v1

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter([])
            VertexAiSearchBackend().search("q", max_results=5)

        request = MockClient.return_value.search.call_args.args[0]
        AutoCondition = discoveryengine_v1.SearchRequest.QueryExpansionSpec.Condition.AUTO
        assert request.query_expansion_spec.condition == AutoCondition

    def test_query_expansion_excluded_when_disabled(self, vertex_env, monkeypatch):
        monkeypatch.setenv("VERTEX_AI_QUERY_EXPANSION", "disabled")
        from google.cloud import discoveryengine_v1

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter([])
            VertexAiSearchBackend().search("q", max_results=5)

        request = MockClient.return_value.search.call_args.args[0]
        UnspecifiedCondition = discoveryengine_v1.SearchRequest.QueryExpansionSpec.Condition.CONDITION_UNSPECIFIED
        assert request.query_expansion_spec.condition == UnspecifiedCondition

    def test_vertex_max_results_env_var_caps_results(self, vertex_env, monkeypatch):
        monkeypatch.setenv("VERTEX_AI_MAX_RESULTS", "5")
        monkeypatch.setenv("VERTEX_AI_QUERY_EXPANSION", "disabled")

        # Provide more results than the cap to confirm truncation
        all_links = [_make_vertex_result(f"https://comeet.com/jobs/a/XX.{i}/dev/id{i}") for i in range(20)]

        with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as MockClient:
            MockClient.return_value.search.return_value = iter(all_links)
            result = VertexAiSearchBackend().search("q", max_results=30)

        assert len(result) == 5


class TestGetSearchBackend:
    def test_returns_vertex_by_default(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SEARCH_BACKEND", raising=False)
        backend = get_search_backend()
        assert isinstance(backend, VertexAiSearchBackend)

    def test_returns_vertex_for_vertex(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SEARCH_BACKEND", "vertex")
        assert isinstance(get_search_backend(), VertexAiSearchBackend)

    def test_returns_vertex_for_vertexai(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SEARCH_BACKEND", "vertexai")
        assert isinstance(get_search_backend(), VertexAiSearchBackend)

    def test_returns_cse_for_cse(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SEARCH_BACKEND", "cse")
        assert isinstance(get_search_backend(), GoogleCseBackend)

    def test_returns_ddgs_for_ddgs(self, monkeypatch):
        from app.scrapers.search_backends import DdgsBackend
        monkeypatch.setenv("GOOGLE_SEARCH_BACKEND", "ddgs")
        assert isinstance(get_search_backend(), DdgsBackend)
