"""Comeet job scraper — discovery via Google site search + HTML parsing."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.scrapers.search_backends import (
    DdgsBackend,
    GoogleCseBackend,
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
        return domain in _COMEET_DOMAINS and "/jobs/" in parsed.path
    except Exception:
        return False


def _slug_to_company(slug: str) -> str:
    """Convert URL slug (e.g. 'acme-corp') to display name ('Acme Corp')."""
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def discover_comeet_urls(
    keyword: str,
    max_results: int = 30,
    request_delay_ms: int = _DEFAULT_DELAY_MS,
) -> list[str]:
    """Search for Comeet job URLs matching a keyword.

    Tries backends in order: configured primary → DdgsBackend → GoogleScrapeBackend
    → PlaywrightGoogleBackend. Returns a deduped list of comeet.com/jobs/... URLs.
    """
    query = f"site:comeet.com/jobs/ {keyword}"
    primary = get_search_backend()

    # Build fallback chain: primary first, then the fixed fallbacks (skipping duplicates)
    fixed_fallbacks = [DdgsBackend(), GoogleScrapeBackend(), PlaywrightGoogleBackend()]
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
            logger.debug("comeet discovery: %s succeeded for %r", name, query)
            break
        except SearchBackendBlocked as exc:
            logger.warning("comeet discovery: %s blocked (%s) — trying next backend", name, exc)
    else:
        logger.warning("comeet discovery: all backends exhausted for %r — skipping keyword", query)
        return []

    seen: set[str] = set()
    urls: list[str] = []
    for url in raw_urls:
        if _is_comeet_job_url(url) and url not in seen:
            seen.add(url)
            urls.append(url)

    logger.info("discover_comeet_urls: keyword=%r discovered=%d", keyword, len(urls))
    return urls


def scrape_comeet_job(url: str, timeout_s: int = 15) -> Optional[dict]:
    """Fetch a Comeet job page and return structured data.

    Returns dict with keys: title, company, location, description, job_url, date_posted.
    Returns None on 404, parse failure, or missing title.
    """
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
    except requests.RequestException as exc:
        logger.warning("scrape_comeet_job: request error for %s: %s", url, exc)
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("scrape_comeet_job: parse error for %s: %s", url, exc)
        return None

    # Title: h1 then og:title meta
    title_el = soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)
    else:
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"].strip() if og_title and og_title.get("content") else ""

    if not title:
        return None

    # Company: derive from URL slug, refine with og:site_name
    try:
        path_parts = urlparse(url).path.strip("/").split("/")
        company_slug = path_parts[1] if len(path_parts) > 1 else ""
        company = _slug_to_company(company_slug)
    except Exception:
        company = ""

    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        company = og_site["content"].strip() or company

    # Location: .location class, data-ui="location", or "Location:" text pattern
    location = ""
    loc_el = soup.find(class_="location") or soup.find(attrs={"data-ui": "location"})
    if loc_el:
        location = loc_el.get_text(strip=True)
    if not location:
        for tag in soup.find_all(["span", "div", "p"], limit=50):
            text = tag.get_text(strip=True)
            if text.lower().startswith("location:"):
                location = text[len("location:"):].strip()
                break

    # Description: main content div, stripped of scripts/styles
    description = ""
    content_el = (
        soup.find(class_=lambda c: c and any(x in c for x in ("job-description", "position-description", "description", "content")))
        or soup.find("article")
        or soup.find("main")
    )
    if content_el:
        for tag in content_el.find_all(["script", "style"]):
            tag.decompose()
        description = content_el.get_text(separator="\n", strip=True)

    # Date posted: article:published_time meta
    date_posted = None
    pub_meta = soup.find("meta", property="article:published_time")
    if pub_meta and pub_meta.get("content"):
        import datetime
        try:
            date_posted = datetime.date.fromisoformat(pub_meta["content"][:10])
        except (ValueError, TypeError):
            pass

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "job_url": url,
        "date_posted": date_posted,
    }


def comeet_search(
    keywords: list[str],
    max_results_per_keyword: int = 30,
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
                "min_amount": None,
                "max_amount": None,
                "currency": "",
                "date_posted": job["date_posted"],
                "is_remote": False,
                "company_industry": None,
                "company_description": None,
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
