"""Cleanup service: re-checks job URLs and marks posts inactive when gone."""
import logging
import os
import random
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_cleanup_lock = threading.Lock()
_cleanup_status: dict = {
    "running": False,
    "last_run_at": None,
    "last_result": None,
}

_INACTIVE_PHRASES = [
    "no longer accepting applications",
    "this job is no longer available",
    "job has been removed",
    "posting has been removed",
    "job is closed",
    "position has been filled",
    "job has expired",
    # LinkedIn renders in the account's locale; Hebrew form of
    # "no longer accepting applications".
    "כבר לא מקבלים מועמדים",
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_BROWSER_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


def _classify_status(status_code: int | None) -> str | None:
    """Map an HTTP status to a verdict, or None to keep inspecting the body."""
    if status_code in (404, 410):
        return "inactive"
    # 401/403/429 = blocked or rate-limited by anti-bot (e.g. Indeed); we can't
    # determine the posting's state, so don't claim it's active.
    if status_code is not None and (status_code in (401, 403, 429) or status_code >= 500):
        return "unknown"
    return None


def _classify_body(body: str | None) -> str:
    """Scan rendered page text for 'gone' markers; default to active."""
    if not body:
        return "active"
    body = body.lower()
    for phrase in _INACTIVE_PHRASES:
        if phrase in body:
            return "inactive"
    return "active"


class _PlaywrightChecker:
    """Reuses one headless browser across a cleanup run to check job URLs."""

    # Indeed/Glassdoor aggressively rate-limit headless traffic with 403/429.
    # Back off and retry; a fresh browser context usually resets the limit.
    _MAX_ATTEMPTS = 3
    _BACKOFF_SECONDS = [8, 20]  # waited before attempts 2 and 3
    # The "expired"/"no longer accepting" banner is rendered client-side, so the
    # page text needs time to settle before we read it.
    _RENDER_WAIT_MS = 3000
    # Hosts that need gentle pacing to stay under the rate limit.
    _RATE_LIMITED_HOSTS = ("indeed", "glassdoor")

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        # Tracks LinkedIn auth health across the run so the UI can warn the user.
        self.li_at_present = False
        self.linkedin_checked = 0
        self.linkedin_authwall = 0
        # Proactive throttling for rate-limited hosts (env-tunable). Indeed/Glassdoor
        # rate-limit per browser context (fingerprint/cookies), so rotating to a
        # fresh context before each request keeps responses at 200 and avoids the
        # slow 403-backoff path. A light delay adds polite spacing + jitter.
        self._proactive_delay = float(os.getenv("CLEANUP_RATELIMIT_DELAY_SECONDS", "1.5"))
        self._rotate_every = int(os.getenv("CLEANUP_CONTEXT_ROTATE_EVERY", "1"))
        self._reqs_since_rotate = 0
        # LinkedIn is hit with an authenticated session (li_at), so a regular
        # cadence reads as a bot and risks the account. Pace it like Indeed
        # (delay + jitter) but WITHOUT context rotation — session continuity
        # matters for an authenticated cookie.
        self._linkedin_delay = float(os.getenv("CLEANUP_LINKEDIN_DELAY_SECONDS", "1.5"))

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        # Indeed/Glassdoor sit behind Cloudflare, which fingerprints headless
        # Chromium and returns 403. A visible (non-headless) browser is blocked
        # far less often. Default to non-headless; set CLEANUP_HEADLESS=true to
        # force headless on a server without a display.
        headless = os.getenv("CLEANUP_HEADLESS", "false").strip().lower() in ("1", "true", "yes")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=headless,
            # Drops the navigator.webdriver flag, the cheapest anti-bot tell.
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.info("Cleanup browser launched (headless=%s)", headless)
        self.li_at_present = bool(os.getenv("LINKEDIN_SESSION_COOKIE", ""))
        if not self.li_at_present:
            logger.warning(
                "LINKEDIN_SESSION_COOKIE not set — LinkedIn closures can't be detected"
            )
        self._open_context()

    def _open_context(self) -> None:
        """(Re)create a fresh browser context + page, re-seeding the li_at cookie."""
        if self._page is not None:
            try:
                self._context.close()
            except Exception:
                pass
        self._context = self._browser.new_context(
            user_agent=_USER_AGENT,
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        # LinkedIn only shows the "no longer accepting applications" banner to an
        # authenticated session; a guest view never reveals the closed state.
        li_at = os.getenv("LINKEDIN_SESSION_COOKIE", "")
        if li_at:
            self._context.add_cookies([{
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }])
        self._page = self._context.new_page()

    def check(self, apply_url: str) -> str:
        if not apply_url:
            return "unknown"
        is_linkedin = "linkedin.com" in apply_url
        if is_linkedin:
            self.linkedin_checked += 1

        # Proactively pace rate-limited hosts so most requests never hit a 403.
        if any(h in apply_url for h in self._RATE_LIMITED_HOSTS):
            if self._rotate_every > 0 and self._reqs_since_rotate >= self._rotate_every:
                self._open_context()
                self._reqs_since_rotate = 0
            if self._proactive_delay > 0:
                # Small jitter to avoid a perfectly regular request cadence.
                time.sleep(self._proactive_delay + random.uniform(0, 1.5))
            self._reqs_since_rotate += 1
        elif is_linkedin and self._linkedin_delay > 0:
            # Pace the authenticated LinkedIn session with delay + jitter (no
            # context rotation — keep the li_at session stable) so the request
            # cadence doesn't look machine-like and risk the account.
            time.sleep(self._linkedin_delay + random.uniform(0, 1.5))

        for attempt in range(self._MAX_ATTEMPTS):
            try:
                resp = self._page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                status = resp.status if resp else None

                # Rate-limited (anti-bot): back off, recreate the context to get a
                # fresh fingerprint, and retry before giving up as "unknown".
                if status in (403, 429) and not is_linkedin:
                    if attempt < self._MAX_ATTEMPTS - 1:
                        wait = self._BACKOFF_SECONDS[min(attempt, len(self._BACKOFF_SECONDS) - 1)]
                        logger.info(
                            "Rate-limited (HTTP %s) for %s — backing off %ds and retrying (attempt %d/%d)",
                            status, apply_url, wait, attempt + 1, self._MAX_ATTEMPTS,
                        )
                        time.sleep(wait)
                        self._open_context()
                        continue
                    logger.warning("Still rate-limited (HTTP %s) after %d attempts: %s",
                                   status, self._MAX_ATTEMPTS, apply_url)
                    return "unknown"

                verdict = _classify_status(status)
                if verdict is not None:
                    return verdict
                # Let client-rendered "expired" banners settle before reading text.
                self._page.wait_for_timeout(self._RENDER_WAIT_MS)
                # Bounced to login/authwall (e.g. expired li_at): we can't read the
                # real state, so don't claim it's active.
                if "authwall" in self._page.url or "/login" in self._page.url:
                    if is_linkedin:
                        self.linkedin_authwall += 1
                    logger.warning("LinkedIn authwall for %s — check LINKEDIN_SESSION_COOKIE", apply_url)
                    return "unknown"
                return _classify_body(self._page.inner_text("body"))
            except Exception as exc:
                logger.debug("Playwright check error for %s: %s", apply_url, exc)
                return "unknown"
        return "unknown"

    def linkedin_auth_invalid(self) -> bool:
        """True if LinkedIn jobs were checked but the li_at cookie is missing or rejected."""
        if self.linkedin_checked == 0:
            return False
        return not self.li_at_present or self.linkedin_authwall > 0

    def stop(self) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass


def check_job_active(apply_url: str) -> str:
    """Fetch apply_url via httpx and classify (fallback when Playwright is unavailable)."""
    if not apply_url:
        return "unknown"
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            resp = client.get(apply_url, headers=_BROWSER_HEADERS)
        verdict = _classify_status(resp.status_code)
        if verdict is not None:
            return verdict
        return _classify_body(resp.text)
    except Exception as exc:
        logger.debug("check_job_active error for %s: %s", apply_url, exc)
        return "unknown"


def run_cleanup() -> dict:
    """Check all active jobs; mark inactive ones. Returns {checked, marked_inactive, errors, duration_ms}."""
    from app.database import SessionLocal
    from app.repository import JobRepository

    start = time.monotonic()
    checked = 0
    marked_inactive = 0
    errors = 0

    with SessionLocal() as session:
        repo = JobRepository(session)
        sources = repo.get_cleanup_sources()  # None = all sources
        cfg = repo.get_scheduler_config()
        limit = cfg.cleanup_limit  # None = no limit
        skip_validated_hours = cfg.cleanup_skip_validated_hours  # None = don't skip
        jobs = repo.list_active_jobs_for_cleanup(
            sources=sources, limit=limit, skip_validated_hours=skip_validated_hours
        )

    logger.info(
        "Cleanup starting: %d active jobs to check (sources=%s, limit=%s, skip_validated_hours=%s)",
        len(jobs),
        sources if sources is not None else "all",
        limit if limit else "none",
        skip_validated_hours if skip_validated_hours else "none",
    )

    # Prefer a single shared Playwright browser (renders JS, survives anti-bot
    # better than raw httpx); fall back to httpx if it can't be started.
    checker: _PlaywrightChecker | None = None
    try:
        checker = _PlaywrightChecker()
        checker.start()
        logger.info("Cleanup using Playwright backend")
    except Exception as exc:
        checker = None
        logger.warning("Playwright unavailable for cleanup, falling back to httpx: %s", exc)

    try:
        for i, job in enumerate(jobs):
            if i > 0 and i % 20 == 0:
                logger.info("Cleanup progress: %d/%d checked", i, len(jobs))

            result = checker.check(job.apply_url) if checker else check_job_active(job.apply_url)
            now = datetime.now(timezone.utc)
            checked += 1

            with SessionLocal() as session:
                repo = JobRepository(session)
                if result == "inactive":
                    # mark_job_inactive stamps last_validated_at (definitive verdict).
                    repo.mark_job_inactive(job.id, checked_at=now)
                    marked_inactive += 1
                    logger.info("Marked inactive: job_id=%d", job.id)
                elif result == "unknown":
                    # Blocked/unreachable — record the check but NOT validation,
                    # so it's retried next batch rather than skipped.
                    errors += 1
                    repo.update_job_checked_at(job.id, checked_at=now, validated=False)
                else:
                    # Confirmed active — definitive verdict, stamp validation.
                    repo.update_job_checked_at(job.id, checked_at=now, validated=True)

            if i < len(jobs) - 1:
                time.sleep(1.0)
    finally:
        if checker is not None:
            checker.stop()

    duration_ms = int((time.monotonic() - start) * 1000)
    summary = {
        "checked": checked,
        "marked_inactive": marked_inactive,
        "errors": errors,
        "duration_ms": duration_ms,
        # Surfaced in the UI so the user knows to refresh LINKEDIN_SESSION_COOKIE.
        "linkedin_auth_invalid": checker.linkedin_auth_invalid() if checker else False,
    }
    logger.info("Cleanup done: %s", summary)
    return summary


def _run_cleanup_task() -> None:
    """Internal: acquire lock, run cleanup, update status, release lock."""
    try:
        _cleanup_status["running"] = True
        result = run_cleanup()
        _cleanup_status["last_result"] = result
        _cleanup_status["last_run_at"] = datetime.now(timezone.utc)
    except Exception as exc:
        logger.error("Cleanup error: %s", exc, exc_info=True)
        _cleanup_status["last_result"] = None
    finally:
        _cleanup_status["running"] = False
        _cleanup_lock.release()


def run_cleanup_now() -> bool:
    """Trigger cleanup in a background thread. Returns False if already running."""
    if not _cleanup_lock.acquire(blocking=False):
        return False
    t = threading.Thread(target=_run_cleanup_task, daemon=True)
    t.start()
    return True


def get_cleanup_status() -> dict:
    return dict(_cleanup_status)
