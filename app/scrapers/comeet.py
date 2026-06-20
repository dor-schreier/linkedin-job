"""Comeet job scraper — discovery via Google site search + LLM-driven extraction."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    PlaywrightTimeoutError = None  # type: ignore[assignment]

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


def _slug_to_title(url: str) -> str:
    """Derive a human-readable title from the URL title slug (path segment index 3)."""
    try:
        parts = [p for p in urlparse(url).path.split("/") if p]
        if len(parts) >= 4:
            return " ".join(w.capitalize() for w in parts[3].replace("-", " ").split())
    except Exception:
        pass
    return ""


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


def _fetch_comeet_html(url: str, timeout_s: int = 20) -> tuple[str | None, str | None]:
    """Render a Comeet job page with headless Playwright and return (html, final_url).

    Waits for networkidle then probes for job-specific selectors before returning.
    Returns (None, None) on navigation error, HTTP 4xx/5xx, or playwright import failure.
    """
    if sync_playwright is None:
        raise ImportError(
            "playwright is required. Run: pip install playwright && playwright install chromium"
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()

            response = page.goto(url, timeout=timeout_s * 1000, wait_until="domcontentloaded")
            if response is None or response.status == 404:
                browser.close()
                return None, None
            if response.status >= 400:
                logger.debug("_fetch_comeet_html: HTTP %d at %s", response.status, url)
                browser.close()
                return None, None

            # Wait for network to settle; SPAs may time out — that's fine
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeoutError:
                pass

            # Probe for job-content signals so we don't return too early
            _JOB_SELECTORS = [
                'script[type="application/ld+json"]',
                "h1",
                '[class*="position"]',
                '[class*="job-title"]',
            ]
            for selector in _JOB_SELECTORS:
                try:
                    page.wait_for_selector(selector, timeout=3_000)
                    break
                except PlaywrightTimeoutError:
                    continue

            html = page.content()
            final_url = page.url
            browser.close()
            return html, final_url
    except Exception as exc:
        logger.warning("_fetch_comeet_html: error fetching %s: %s", url, exc)
        return None, None


def _extract_jsonld_jobposting(soup: BeautifulSoup) -> dict | None:
    """Parse <script type="application/ld+json"> blocks for a JobPosting and return a data dict.

    Returns None if no JobPosting block is found.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return _map_jsonld_to_dict(item)
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _map_jsonld_to_dict(posting: dict) -> dict:
    """Map a JSON-LD JobPosting object to our extraction dict shape."""
    title = posting.get("title") or ""

    hiring_org = posting.get("hiringOrganization") or {}
    company = (hiring_org.get("name") or "") if isinstance(hiring_org, dict) else ""

    job_location = posting.get("jobLocation") or {}
    location = ""
    if isinstance(job_location, dict):
        address = job_location.get("address") or {}
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
            location = ", ".join(p for p in parts if p)
        elif isinstance(address, str):
            location = address
    elif isinstance(job_location, str):
        location = job_location

    # Strip HTML from description
    desc_html = posting.get("description") or ""
    desc_text = BeautifulSoup(desc_html, "html.parser").get_text(separator="\n", strip=True)

    salary = posting.get("baseSalary") or {}
    salary_min = salary_max = salary_currency = None
    if isinstance(salary, dict):
        value = salary.get("value") or {}
        if isinstance(value, dict):
            salary_min = value.get("minValue")
            salary_max = value.get("maxValue") or value.get("value")
        salary_currency = salary.get("currency")

    date_posted = posting.get("datePosted")

    employment_type = (posting.get("jobLocationType") or "").upper()
    location_lower = location.lower()
    is_remote = employment_type == "TELECOMMUTE" or any(
        kw in location_lower for kw in ("remote", "anywhere", "work from home")
    )

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": desc_text,
        "date_posted": date_posted,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "is_remote": is_remote,
        "company_industry": None,
        "company_description": None,
    }


def _looks_like_job_page(soup: BeautifulSoup) -> bool:
    """Return True when the rendered page looks like a single job posting.

    False for company/careers listing pages (multiple position links, no JobPosting).
    """
    # Strong positive signal: JSON-LD JobPosting block
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            if any(isinstance(item, dict) and item.get("@type") == "JobPosting" for item in items):
                return True
        except (json.JSONDecodeError, AttributeError):
            continue

    # Negative signal: multiple links that look like individual job URLs
    # Comeet careers pages list many /jobs/company/code/title/id links
    def _is_job_href(href: str | None) -> bool:
        if not href:
            return False
        try:
            return _is_comeet_job_url(href) or (
                "/jobs/" in href and href.count("/") >= 5
            )
        except Exception:
            return False

    position_links = [a for a in soup.find_all("a", href=True) if _is_job_href(a["href"])]
    if len(position_links) > 3:
        return False

    # Single h1 is a moderate positive signal
    if len(soup.find_all("h1")) == 1:
        return True

    # Default: assume single job if no clear listing detected
    return True


def _html_to_llm_text(html: str, max_chars: int = 12000) -> str:
    """Strip non-content tags from HTML and return visible text truncated to max_chars."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:max_chars]


def scrape_comeet_job(url: str, timeout_s: int = 20) -> Optional[dict]:
    """Fetch a Comeet job page and return structured data.

    Renders the JS SPA with Playwright, checks the page is a single job (not a listing),
    extracts via JSON-LD first and falls back to LLM extraction. Returns None on fetch
    failure, non-job pages, or when no title can be resolved.

    Returns dict with keys: title, company, location, description, job_url, date_posted,
    salary_min, salary_max, salary_currency, is_remote, company_industry, company_description.
    """
    import datetime

    html, final_url = _fetch_comeet_html(url, timeout_s=timeout_s)
    if html is None:
        return None

    if not _is_comeet_job_url(final_url or ""):
        logger.debug("scrape_comeet_job: redirected away from job page %s -> %s", url, final_url)
        return None

    soup = BeautifulSoup(html, "html.parser")

    if not _looks_like_job_page(soup):
        logger.info("scrape_comeet_job: not a job page (company/listing), skipping %s", url)
        return None

    # --- Primary: JSON-LD extraction ---
    jsonld_result = _extract_jsonld_jobposting(soup)
    if jsonld_result and jsonld_result.get("title"):
        result = jsonld_result
    else:
        # --- Fallback: LLM extraction on visible text ---
        # JSON-LD scripts are already parsed above; stripping them here for the LLM is fine
        page_text = _html_to_llm_text(html)
        llm_result = extract_comeet_job_fields(page_text, url)
        if llm_result is None:
            logger.warning("scrape_comeet_job: LLM extraction failed for %s", url)
            result = {}
        else:
            result = llm_result

    title = result.get("title") or ""
    if not title:
        # Last resort: derive from the title slug in the URL path
        title = _slug_to_title(url)
        if title:
            logger.debug("scrape_comeet_job: using slug-derived title %r for %s", title, url)

    if not title:
        logger.warning("scrape_comeet_job: could not determine title for %s", url)
        return None

    company = result.get("company") or ""
    if not company:
        try:
            path_parts = urlparse(url).path.strip("/").split("/")
            company_slug = path_parts[1] if len(path_parts) > 1 else ""
            company = _slug_to_company(company_slug)
        except Exception:
            company = ""

    date_posted = None
    date_str = result.get("date_posted")
    if date_str:
        try:
            date_posted = datetime.date.fromisoformat(date_str[:10])
        except (ValueError, TypeError):
            pass

    return {
        "title": title,
        "company": company,
        "location": result.get("location") or "",
        "description": result.get("description") or "",
        "job_url": url,
        "date_posted": date_posted,
        "salary_min": result.get("salary_min"),
        "salary_max": result.get("salary_max"),
        "salary_currency": result.get("salary_currency"),
        "is_remote": result.get("is_remote", False),
        "company_industry": result.get("company_industry"),
        "company_description": result.get("company_description"),
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
