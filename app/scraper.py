"""Scraper service — wraps JobSpy, normalizes rows, deduplicates, and persists jobs."""
import hashlib
import json
import logging
from typing import Optional

from app.database import SessionLocal
from app.repository import JobRepository

logger = logging.getLogger(__name__)

RESULTS_WANTED = 50


def _compute_hash(title: str, company: str, location: str) -> str:
    """Return SHA-256 hex digest of 'title|company|location' (lowercased, stripped)."""
    raw = f"{title.strip()}|{company.strip()}|{location.strip()}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_row(row: dict) -> Optional[dict]:
    """Normalize a raw JobSpy DataFrame row dict into a DB-safe dict.

    Returns None if the job should be filtered out (remote or missing title).
    All .get() access — never dict[] — so missing columns never raise KeyError.
    NaN string fields become ""; NaN numeric fields become None.
    """
    # Remote filter (SRCH-04)
    if row.get("is_remote") is True:
        return None

    # String field helper: coerces None / NaN / "nan" to ""
    def _str(val) -> str:
        s = str(val or "").strip()
        return "" if s.lower() == "nan" else s

    title = _str(row.get("title"))
    if not title:
        return None

    company = _str(row.get("company"))
    location = _str(row.get("location"))
    description = _str(row.get("description"))
    source = _str(row.get("site"))
    apply_url = _str(row.get("job_url"))

    # Currency is a string field
    salary_currency = _str(row.get("currency"))

    # Numeric salary helper: returns float or None
    def _numeric(val) -> Optional[float]:
        if val is None:
            return None
        try:
            f = float(val)
            import math
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    salary_min = _numeric(row.get("min_amount"))
    salary_max = _numeric(row.get("max_amount"))

    job_hash = _compute_hash(title, company, location)

    # date_posted: JobSpy returns a date object or None
    import datetime as _dt
    raw_date = row.get("date_posted")
    date_posted = None
    if raw_date is not None:
        if isinstance(raw_date, _dt.date):
            date_posted = raw_date
        else:
            try:
                date_posted = _dt.date.fromisoformat(str(raw_date))
            except (ValueError, TypeError):
                pass

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "source": source,
        "apply_url": apply_url,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "job_hash": job_hash,
        "date_posted": date_posted,
    }


def run_scrape(
    keywords: str,
    location: str,
    experience_level: Optional[str] = None,
    country_indeed: str = "USA",
    skip_intelligence: bool = False,
) -> dict:
    """Run a full scrape cycle: fetch -> normalize -> dedup -> persist.

    Creates its own DB session; never accepts one from the caller.
    Returns a summary dict: {total_scraped, inserted, skipped, remote_filtered}
    On error returns {error: str}.
    """
    try:
        from jobspy import scrape_jobs  # import inside function for easier mocking

        search_term = keywords
        if experience_level:
            search_term = f"{experience_level} {keywords}"

        logger.info(
            "Scraping jobs: search_term=%r location=%r country_indeed=%r",
            search_term,
            location,
            country_indeed,
        )

        df = scrape_jobs(
            site_name=["linkedin", "indeed", "glassdoor"],
            search_term=search_term,
            location=location,
            country_indeed=country_indeed,
            job_type="fulltime",
            results_wanted=RESULTS_WANTED,
            verbose=0,
            linkedin_fetch_description=True,
        )

        total_scraped = len(df)
        inserted = 0
        skipped = 0
        remote_filtered = 0
        scored = 0
        score_skipped = 0
        score_failed = 0

        with SessionLocal() as session:
            repo = JobRepository(session)
            inserted_ids: list[int] = []
            profile = repo.get_profile()

            for _, row_series in df.iterrows():
                row = row_series.to_dict()
                normalized = _normalize_row(row)

                if normalized is None:
                    # Could be remote or empty title — count remote separately
                    is_remote = row.get("is_remote") is True
                    if is_remote:
                        remote_filtered += 1
                    else:
                        skipped += 1
                    continue

                if repo.get_job_by_hash(normalized["job_hash"]):
                    skipped += 1
                    continue

                created = repo.add_job(**normalized)
                inserted_ids.append(created.id)
                inserted += 1

                if not skip_intelligence:
                    try:
                        from app.services.groq_service import extract_job_intelligence
                        result = extract_job_intelligence(created)
                        if result is not None:
                            import json as _json
                            created.intelligence_json = _json.dumps(result)
                            session.commit()
                    except Exception as _exc:
                        logger.warning(
                            "Intelligence extraction failed for %r at %r: %s",
                            created.title,
                            created.company,
                            _exc,
                        )

                    if profile is None:
                        score_skipped += 1
                    else:
                        try:
                            from app.services.groq_service import get_enhanced_fit_score
                            score_result = get_enhanced_fit_score(created, profile)
                            if score_result is not None:
                                created.fit_score = score_result.get("fit_score")
                                created.fit_summary = score_result.get("fit_summary")
                                created.score_breakdown_json = json.dumps(score_result)
                                created.salary_estimated = score_result.get("salary_estimated")
                                session.commit()
                                scored += 1
                        except Exception as _exc:
                            logger.warning(
                                "Fit scoring failed for %r at %r: %s",
                                created.title,
                                created.company,
                                _exc,
                            )
                            score_failed += 1

            from app.services.watch_service import match_new_jobs_to_watch_rules
            notifications_created = match_new_jobs_to_watch_rules(session, inserted_ids)

        logger.info(
            "Scrape complete: total=%d inserted=%d skipped=%d remote_filtered=%d notifications=%d scored=%d score_skipped=%d score_failed=%d",
            total_scraped,
            inserted,
            skipped,
            remote_filtered,
            notifications_created,
            scored,
            score_skipped,
            score_failed,
        )
        return {
            "total_scraped": total_scraped,
            "inserted": inserted,
            "skipped": skipped,
            "remote_filtered": remote_filtered,
            "notifications_created": notifications_created,
            "scored": scored,
            "score_skipped": score_skipped,
            "score_failed": score_failed,
        }

    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)
        return {"error": str(e)}
