"""Google search backend abstraction for Comeet URL discovery."""
from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class SearchBackendBlocked(Exception):
    """Raised when a Google search backend detects blocking (429/503/captcha)."""


@runtime_checkable
class SearchBackend(Protocol):
    def search(self, query: str, max_results: int) -> list[str]: ...


class DdgsBackend:
    """Primary backend using DuckDuckGo Search (ddgs library — no API key required)."""

    def search(self, query: str, max_results: int) -> list[str]:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError as exc:
            raise SearchBackendBlocked(
                "ddgs is not installed — falling back to next backend"
            ) from exc

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [r.get("href", r.get("url", "")) for r in results if r.get("href") or r.get("url")]
        except Exception as exc:
            msg = str(exc).lower()
            if any(kw in msg for kw in ("429", "503", "captcha", "rate limit", "ratelimit", "blocked")):
                raise SearchBackendBlocked(f"DuckDuckGo search blocked: {exc}") from exc
            raise


class GoogleScrapeBackend:
    """Fallback backend using googlesearch-python library."""

    def search(self, query: str, max_results: int) -> list[str]:
        try:
            from googlesearch import search  # type: ignore
        except ImportError as exc:
            raise SearchBackendBlocked(
                "googlesearch-python is not installed — falling back to Playwright"
            ) from exc

        try:
            results = list(search(query, num_results=max_results, lang="en"))
            return results
        except Exception as exc:
            msg = str(exc).lower()
            if any(kw in msg for kw in ("429", "503", "captcha", "unusual traffic", "rate limit")):
                raise SearchBackendBlocked(f"Google search blocked: {exc}") from exc
            raise


class PlaywrightGoogleBackend:
    """Last-resort backend using headless Chromium via Playwright."""

    def search(self, query: str, max_results: int) -> list[str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ImportError(
                "playwright is required. Run: pip install playwright && playwright install chromium"
            ) from exc

        import urllib.parse

        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&num={max_results}"
        urls: list[str] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
            )
            page = context.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            content = page.content()
            if "captcha" in content.lower() or "unusual traffic" in content.lower():
                browser.close()
                raise SearchBackendBlocked("Google Playwright backend hit CAPTCHA")
            anchors = page.query_selector_all("div.g a, a[jsname]")
            for a in anchors:
                href = a.get_attribute("href")
                if href and href.startswith("http") and "google.com" not in href:
                    urls.append(href)
                    if len(urls) >= max_results:
                        break
            browser.close()

        return urls


class SerpApiBackend:
    """Stub backend for SerpAPI — raises NotImplementedError until implemented."""

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY", "")

    def search(self, query: str, max_results: int) -> list[str]:
        raise NotImplementedError("SerpAPI backend not yet implemented — see .specs/comeet-scraper.md")


class GoogleCseBackend:
    """Google Custom Search Engine backend (paid/quota'd JSON API, most reliable)."""

    _BASE_URL = "https://www.googleapis.com/customsearch/v1"
    _PAGE_SIZE = 10  # CSE max per request

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_CSE_KEY", "")
        self.cx = os.getenv("GOOGLE_CSE_CX", "")

    def search(self, query: str, max_results: int) -> list[str]:
        import requests as _requests

        if not self.api_key or not self.cx:
            raise SearchBackendBlocked("CSE not configured — set GOOGLE_CSE_KEY and GOOGLE_CSE_CX")

        urls: list[str] = []
        fetched = 0
        # CSE uses 1-based start index; max 100 results total
        cap = min(max_results, 100)
        while fetched < cap:
            batch = min(self._PAGE_SIZE, cap - fetched)
            params = {
                "key": self.api_key,
                "cx": self.cx,
                "q": query,
                "num": batch,
                "start": fetched + 1,
            }
            try:
                resp = _requests.get(self._BASE_URL, params=params, timeout=15)
            except _requests.RequestException as exc:
                raise SearchBackendBlocked(f"CSE request failed: {exc}") from exc

            if resp.status_code == 429:
                raise SearchBackendBlocked("CSE quota exhausted (HTTP 429)")
            if resp.status_code == 403:
                data = resp.json() if resp.content else {}
                reasons = [
                    e.get("reason", "")
                    for e in data.get("error", {}).get("errors", [])
                ]
                if any(r in ("rateLimitExceeded", "dailyLimitExceeded") for r in reasons):
                    raise SearchBackendBlocked(f"CSE quota exhausted (403): {reasons}")
                raise SearchBackendBlocked(f"CSE auth failure (HTTP 403): {reasons or 'invalid key or disabled API'}")
            if resp.status_code != 200:
                raise SearchBackendBlocked(f"CSE unexpected HTTP {resp.status_code}")

            data = resp.json()
            # Check error block inside a 200 response (rare but possible)
            if "error" in data:
                reasons = [e.get("reason", "") for e in data["error"].get("errors", [])]
                if any(r in ("rateLimitExceeded", "dailyLimitExceeded") for r in reasons):
                    raise SearchBackendBlocked(f"CSE quota exhausted: {reasons}")
                raise SearchBackendBlocked(f"CSE API error: {data['error'].get('message', reasons)}")

            items = data.get("items", [])
            urls.extend(item["link"] for item in items if item.get("link"))
            fetched += batch
            if len(items) < batch:
                break  # no more results

        return urls


class VertexAiSearchBackend:
    """Vertex AI Search backend using Google Cloud Discovery Engine API."""

    _PAGE_SIZE = 20  # API caps responses at ~20 docs regardless of requested size

    def __init__(self):
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = os.getenv("VERTEX_AI_LOCATION", "global")
        self.data_store_id = os.getenv("VERTEX_AI_DATA_STORE_ID", "")
        self.engine_id = os.getenv("VERTEX_AI_ENGINE_ID", "")

    def search(self, query: str, max_results: int) -> list[str]:
        if not self.project or not (self.data_store_id or self.engine_id):
            raise SearchBackendBlocked(
                "VertexAiSearchBackend not configured — set GOOGLE_CLOUD_PROJECT and VERTEX_AI_DATA_STORE_ID"
            )

        try:
            from google.cloud import discoveryengine_v1
            from google.api_core import exceptions as google_exceptions
        except ImportError as exc:
            raise SearchBackendBlocked(
                "google-cloud-discoveryengine is not installed — falling back to next backend"
            ) from exc

        vertex_max = int(os.getenv("VERTEX_AI_MAX_RESULTS", "30"))
        cap = min(max_results, vertex_max)
        # Engine-based path supports enterprise features; data-store path requires standard edition only
        if self.engine_id:
            serving_config = (
                f"projects/{self.project}/locations/{self.location}"
                f"/collections/default_collection/engines/{self.engine_id}"
                f"/servingConfigs/default_search"
            )
        else:
            serving_config = (
                f"projects/{self.project}/locations/{self.location}"
                f"/collections/default_collection/dataStores/{self.data_store_id}"
                f"/servingConfigs/default_search"
            )

        client = discoveryengine_v1.SearchServiceClient()

        expansion_setting = os.getenv("VERTEX_AI_QUERY_EXPANSION", "auto").lower()
        query_expansion_spec = (
            None
            if expansion_setting == "disabled"
            else discoveryengine_v1.SearchRequest.QueryExpansionSpec(
                condition=discoveryengine_v1.SearchRequest.QueryExpansionSpec.Condition.AUTO
            )
        )

        urls: list[str] = []
        offset = 0

        try:
            while len(urls) < cap:
                batch_size = min(self._PAGE_SIZE, cap - len(urls))
                kwargs: dict = dict(
                    serving_config=serving_config,
                    query=query,
                    page_size=batch_size,
                    offset=offset,
                )
                if query_expansion_spec is not None:
                    kwargs["query_expansion_spec"] = query_expansion_spec
                request = discoveryengine_v1.SearchRequest(**kwargs)

                batch_urls: list[str] = []
                for result in client.search(request):
                    link = result.document.derived_struct_data.get("link", "")
                    if link:
                        batch_urls.append(link)
                    if len(batch_urls) >= batch_size:
                        break

                urls.extend(batch_urls)
                logger.debug(
                    "VertexAiSearchBackend offset=%d returned=%d total=%d",
                    offset,
                    len(batch_urls),
                    len(urls),
                )
                if not batch_urls:
                    break
                offset += self._PAGE_SIZE

            return urls
        except google_exceptions.PermissionDenied as exc:
            raise SearchBackendBlocked(f"Vertex AI Search: permission denied — {exc}") from exc
        except google_exceptions.Unauthenticated as exc:
            raise SearchBackendBlocked(
                "Vertex AI Search: unauthenticated — check GOOGLE_APPLICATION_CREDENTIALS or ADC"
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raise SearchBackendBlocked(f"Vertex AI Search: quota exhausted — {exc}") from exc
        except google_exceptions.InvalidArgument as exc:
            raise SearchBackendBlocked(
                f"Vertex AI Search: invalid argument (bad data store config?) — {exc}"
            ) from exc
        except google_exceptions.FailedPrecondition as exc:
            raise SearchBackendBlocked(
                f"Vertex AI Search: enterprise edition required for website search — "
                f"enable it at https://cloud.google.com/generative-ai-app-builder/docs/enterprise-edition#toggle-enterprise "
                f"or set VERTEX_AI_ENGINE_ID to use an engine-based serving config — {exc}"
            ) from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise SearchBackendBlocked(f"Vertex AI Search: API error — {exc}") from exc


def get_search_backend() -> SearchBackend:
    """Return a SearchBackend based on GOOGLE_SEARCH_BACKEND env var (default: vertex)."""
    backend_name = os.getenv("GOOGLE_SEARCH_BACKEND", "vertex").lower()
    if backend_name in ("vertex", "vertexai"):
        return VertexAiSearchBackend()
    elif backend_name == "playwright":
        return PlaywrightGoogleBackend()
    elif backend_name == "google":
        return GoogleScrapeBackend()
    elif backend_name == "serpapi":
        return SerpApiBackend()
    elif backend_name == "cse":
        return GoogleCseBackend()
    elif backend_name == "ddgs":
        return DdgsBackend()
    else:
        return VertexAiSearchBackend()
