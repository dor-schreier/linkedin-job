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


class GoogleScrapeBackend:
    """Primary backend using googlesearch-python library."""

    def search(self, query: str, max_results: int) -> list[str]:
        try:
            from googlesearch import search  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "googlesearch-python is required. Run: pip install googlesearch-python"
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
    """Fallback backend using headless Chromium via Playwright."""

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
    """Stub backend for Google Custom Search Engine — raises NotImplementedError until implemented."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_CSE_KEY", "")
        self.cx = os.getenv("GOOGLE_CSE_CX", "")

    def search(self, query: str, max_results: int) -> list[str]:
        raise NotImplementedError("Google CSE backend not yet implemented — see .specs/comeet-scraper.md")


def get_search_backend() -> SearchBackend:
    """Return a SearchBackend based on GOOGLE_SEARCH_BACKEND env var (default: google)."""
    backend_name = os.getenv("GOOGLE_SEARCH_BACKEND", "google").lower()
    if backend_name == "playwright":
        return PlaywrightGoogleBackend()
    elif backend_name == "serpapi":
        return SerpApiBackend()
    elif backend_name == "cse":
        return GoogleCseBackend()
    else:
        return GoogleScrapeBackend()
