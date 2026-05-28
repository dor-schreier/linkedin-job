"""Comeet job scraper — discovery via Google site search + LLM-driven extraction."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.services.llm_service import extract_comeet_job_fields
from app.scrapers.search_backends import (
    GoogleScrapeBackend,
    PlaywrightGoogleBackend,
    SearchBackendBlocked,
    get_search_backend,
)

logger = logging.getLogger(__name__)

_COMEET_DOMAINS = {"comeet.com", "comeet.co"}
_DEFAULT_DELAY_MS = int(os.getenv("COMEET_REQUEST_DELAY_MS", "2000"))
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _is_comeet_job_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        if domain not in _COMEET_DOMAINS:
            return False
        # Exact shape: /jobs/{company}/{position-code}/{title}/{job-id} (5 non-empty segments)
        # position-code must contain a dot (e.g. XX.123) to distinguish from category pages
        parts = [p for p in parsed.path.split("/") if p]
        return (
            len(parts) == 5
            and parts[0] == "jobs"
            and "." in parts[2]
        )
    except Exception:
        return False


def _comeet_identity(url: str) -> Optional[str]:
    """Return a stable identity string for a Comeet job URL.

    Parses `comeet.com/jobs/{company}/{position-code}/{title-slug}/{job-id}` and
    returns `"{company}/{position-code}/{job-id}"` — the title slug is excluded
    because LLM extraction may vary. Returns None if the URL doesn't match.
    """
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 5 and parts[0] == "jobs" and "." in parts[2]:
            company_slug, position_code, job_id = parts[1], parts[2], parts[4]
            return f"{company_slug}/{position_code}/{job_id}"
    except Exception:
        pass
    return None


def _slug_to_company(slug: str) -> str:
    """Convert URL slug (e.g. 'acme-corp') to display name ('Acme Corp')."""
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


_DEFAULT_MAX_RESULTS = int(os.getenv("VERTEX_AI_MAX_RESULTS", "30"))


def discover_comeet_urls(
    keyword: str,
    max_results: int = _DEFAULT_MAX_RESULTS,
    request_delay_ms: int = _DEFAULT_DELAY_MS,
) -> list[str]:
    """Search for Comeet job URLs matching a keyword.

    Tries backends in order: configured primary → GoogleScrapeBackend
    → PlaywrightGoogleBackend. Returns a deduped list of comeet.com/jobs/... URLs.
    """
    query = f"site:comeet.com/jobs/ {keyword}"
    primary = get_search_backend()

    # Build fallback chain: primary first, then fixed fallbacks (skipping duplicates)
    fixed_fallbacks = [GoogleScrapeBackend(), PlaywrightGoogleBackend()]
    chain = [primary] + [b for b in fixed_fallbacks if type(b) is not type(primary)]

    raw_urls: list[str] = []
    for backend in chain:
        name = type(backend).__name__
        try:
            results = backend.search(query, max_results)
            if not results:
                logger.warning("comeet discovery: %s returned 0 results for %r — trying next", name, query)
                raise SearchBackendBlocked("0 results (possible silent block)")
            raw_urls = results
            logger.info("comeet discovery: %s returned %d raw URLs for %r", name, len(results), query)
            break
        except SearchBackendBlocked as exc:
            logger.warning("comeet discovery: %s blocked (%s) — trying next backend", name, exc)
    else:
        logger.warning("comeet discovery: all backends exhausted for %r — skipping keyword", query)
        return []

    seen: set[str] = set()
    urls: list[str] = []
    rejected_samples: list[str] = []
    for url in raw_urls:
        if _is_comeet_job_url(url) and url not in seen:
            seen.add(url)
            urls.append(url)
        elif url not in seen and len(rejected_samples) < 5:
            rejected_samples.append(url)

    logger.info(
        "discover_comeet_urls: keyword=%r raw=%d job_urls=%d rejected_samples=%s",
        keyword, len(raw_urls), len(urls), rejected_samples,
    )
    return urls


def _html_to_llm_text(html: str, max_chars: int = 12000) -> str:
    """Strip non-content tags from HTML and return visible text truncated to max_chars."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:max_chars]


def scrape_comeet_job(url: str, timeout_s: int = 15) -> Optional[dict]:
    """Fetch a Comeet job page and return structured data via LLM extraction.

    Returns dict with keys: title, company, location, description, job_url, date_posted,
    salary_min, salary_max, salary_currency, is_remote, company_industry, company_description.
    Returns None on 404, network error, LLM failure, or empty title.
    """
    import datetime

    headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        if resp.status_code == 404:
            logger.debug("scrape_comeet_job: 404 at %s", url)
            return None
        if resp.status_code >= 500:
            time.sleep(1)
            resp = requests.get(url, headers=headers, timeout=timeout_s)
        if resp.status_code != 200:
            logger.debug("scrape_comeet_job: HTTP %d at %s", resp.status_code, url)
            return None
        if not _is_comeet_job_url(resp.url):
            logger.debug("scrape_comeet_job: redirected away from job page %s -> %s", url, resp.url)
            return None
    except requests.RequestException as exc:
        logger.warning("scrape_comeet_job: request error for %s: %s", url, exc)
        return None

    page_text = _html_to_llm_text(resp.text)
    llm_result = extract_comeet_job_fields(page_text, url)

    if llm_result is None:
        logger.warning("scrape_comeet_job: LLM extraction failed for %s", url)
        return None

    title = llm_result.get("title") or ""
    if not title:
        return None

    company = llm_result.get("company") or ""
    if not company:
        try:
            path_parts = urlparse(url).path.strip("/").split("/")
            company_slug = path_parts[1] if len(path_parts) > 1 else ""
            company = _slug_to_company(company_slug)
        except Exception:
            company = ""

    date_posted = None
    date_str = llm_result.get("date_posted")
    if date_str:
        try:
            date_posted = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass

    return {
        "title": title,
        "company": company,
        "location": llm_result.get("location") or "",
        "description": llm_result.get("description") or "",
        "job_url": url,
        "date_posted": date_posted,
        "salary_min": llm_result.get("salary_min"),
        "salary_max": llm_result.get("salary_max"),
        "salary_currency": llm_result.get("salary_currency"),
        "is_remote": llm_result.get("is_remote", False),
        "company_industry": llm_result.get("company_industry"),
        "company_description": llm_result.get("company_description"),
    }


def comeet_search(
    keywords: list[str],
    max_results_per_keyword: int = _DEFAULT_MAX_RESULTS,
) -> "tuple[pd.DataFrame, dict]":
    """Orchestrate Comeet discovery and scraping for all keywords.

    Returns (df, stats) where df is in JobSpy column shape with site='comeet'
    and stats is {"discovered": int, "parsed": int, "failed": int}.
    """
    import pandas as pd

    delay_ms = _DEFAULT_DELAY_MS
    all_rows: list[dict] = []
    discovered_total = 0
    parsed_total = 0
    failed_total = 0

    for keyword in keywords:
        urls = discover_comeet_urls(keyword, max_results=max_results_per_keyword)
        discovered_total += len(urls)
        logger.info("comeet_search: keyword=%r discovered=%d urls", keyword, len(urls))

        for url in urls:
            time.sleep(delay_ms / 1000)
            job = scrape_comeet_job(url)
            if job is None:
                failed_total += 1
                logger.debug("comeet_search: parse failed for %s", url)
                continue

            all_rows.append({
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "description": job["description"],
                "site": "comeet",
                "job_url": job["job_url"],
                "min_amount": job.get("salary_min"),
                "max_amount": job.get("salary_max"),
                "currency": job.get("salary_currency") or "",
                "date_posted": job["date_posted"],
                "is_remote": job.get("is_remote", False),
                "company_industry": job.get("company_industry"),
                "company_description": job.get("company_description"),
            })
            parsed_total += 1

    stats = {"discovered": discovered_total, "parsed": parsed_total, "failed": failed_total}
    logger.info(
        "comeet_search: total discovered=%d parsed=%d failed=%d",
        discovered_total,
        parsed_total,
        failed_total,
    )

    _COLUMNS = [
        "title", "company", "location", "description", "site", "job_url",
        "min_amount", "max_amount", "currency", "date_posted", "is_remote",
        "company_industry", "company_description",
    ]

    if not all_rows:
        return pd.DataFrame(columns=_COLUMNS), stats

    return pd.DataFrame(all_rows), stats
