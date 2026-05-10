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


def get_search_backend() -> SearchBackend:
    """Return a SearchBackend based on GOOGLE_SEARCH_BACKEND env var (default: ddgs)."""
    backend_name = os.getenv("GOOGLE_SEARCH_BACKEND", "cse").lower()
    if backend_name == "playwright":
        return PlaywrightGoogleBackend()
    elif backend_name == "google":
        return GoogleScrapeBackend()
    elif backend_name == "serpapi":
        return SerpApiBackend()
    elif backend_name == "cse":
        return GoogleCseBackend()
    else:
        return DdgsBackend()
