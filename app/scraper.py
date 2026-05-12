"""Scraper service — wraps JobSpy, normalizes rows, deduplicates, and persists jobs."""
from __future__ import annotations
import hashlib
import json
import logging
import re
from typing import Optional

from app.database import SessionLocal
from app.repository import JobRepository

logger = logging.getLogger(__name__)

# Product decision: only full-time roles are relevant for this job search.
JOB_TYPE = "fulltime"

# Title prefixes for each role level track. When role_level is set,
# one scrape_jobs() call is made per prefix and results are merged via url_hash dedup.
ROLE_LEVEL_TERMS: dict[str, list[str]] = {
    "ic_senior": ["Senior", "Staff", "Principal"],
    "team_lead": ["Team Lead", "Tech Lead", "Lead Engineer"],
    "engineering_manager": ["Engineering Manager", "Engineering Lead"],
    "director": ["Director of Engineering", "Director"],
    "vp": ["VP of Engineering", "VP Engineering"],
}


def build_search_terms(config) -> list[str]:
    """Return list of search terms to scrape.

    When role_level is set and recognised, returns one term per title prefix
    from ROLE_LEVEL_TERMS. For ic_senior, experience_level prefix is also applied
    if set (e.g. "Senior software engineer").
    Falls back to a single term built from keywords (and experience_level prefix
    when role_level is absent).
    """
    base = (config.keywords or "").strip()
    role = getattr(config, "role_level", None)

    if role and role in ROLE_LEVEL_TERMS:
        return [f"{prefix} {base}".strip() for prefix in ROLE_LEVEL_TERMS[role]]

    # No role_level — single search term, optionally prefixed with experience_level
    exp = getattr(config, "experience_level", None)
    if exp:
        return [f"{exp} {base}".strip()]
    return [base]


def apply_filters(df, config) -> tuple:
    """Apply post-scrape filters to raw JobSpy DataFrame before row-by-row processing.

    Order: blocked_companies → exclude_keywords → min_salary.
    Returns (filtered_df, drop_counts) where drop_counts is a dict with per-filter counts.
    """
    counts = {"blocked_companies": 0, "exclude_keywords": 0, "min_salary": 0}

    # 1. Blocked companies — case-insensitive exact match against df["company"]
    blocked_csv = getattr(config, "blocked_companies", None)
    if blocked_csv:
        blocked = [c.strip().lower() for c in blocked_csv.split(",") if c.strip()]
        if blocked and "company" in df.columns:
            mask = df["company"].str.lower().isin(blocked)
            counts["blocked_companies"] = int(mask.sum())
            df = df[~mask].copy()
            if counts["blocked_companies"]:
                logger.info("Filter blocked_companies: dropped %d rows", counts["blocked_companies"])

    # 2. Exclude keywords — regex OR across title + description, case-insensitive
    exclude_csv = getattr(config, "exclude_keywords", None)
    if exclude_csv:
        kws = [kw.strip() for kw in exclude_csv.split(",") if kw.strip()]
        if kws:
            pattern = "|".join(re.escape(kw) for kw in kws)
            title_col = df["title"].fillna("") if "title" in df.columns else df.get("title", "")
            desc_col = df["description"].fillna("") if "description" in df.columns else df.get("description", "")
            mask = (
                title_col.str.contains(pattern, case=False, regex=True)
                | desc_col.str.contains(pattern, case=False, regex=True)
            )
            counts["exclude_keywords"] = int(mask.sum())
            df = df[~mask].copy()
            if counts["exclude_keywords"]:
                logger.info("Filter exclude_keywords: dropped %d rows", counts["exclude_keywords"])

    # 3. Min salary — only when set; null salaries are KEPT (we can't rule them out)
    min_salary = getattr(config, "min_salary", None)
    if min_salary and "min_amount" in df.columns:
        has_salary = df["min_amount"].notna()
        below_min = df["min_amount"] < min_salary
        drop_mask = has_salary & below_min
        counts["min_salary"] = int(drop_mask.sum())
        df = df[~drop_mask].copy()
        if counts["min_salary"]:
            logger.info("Filter min_salary: dropped %d rows", counts["min_salary"])

    return df, counts


def _compute_hash(title: str, company: str, location: str) -> str:
    """Return SHA-256 hex digest of 'title|company|location' (lowercased, stripped)."""
    raw = f"{title.strip()}|{company.strip()}|{location.strip()}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_row(row: dict) -> Optional[dict]:
    """Normalize a raw JobSpy DataFrame row dict into a DB-safe dict.

    Returns None if the job should be skipped (missing title).
    Remote filtering is handled upstream in run_scrape() based on config.include_remote.
    All .get() access — never dict[] — so missing columns never raise KeyError.
    NaN string fields become ""; NaN numeric fields become None.
    """
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


class LinkedInAuthError(Exception):
    """Raised when LinkedIn redirects to the login wall."""


def scrape_linkedin_profile(profile_url: str) -> "LinkedInProfile":  # noqa: F821 — imported inside function body
    """Scrape a LinkedIn profile page and return a populated LinkedInProfile.

    Requires LINKEDIN_SESSION_COOKIE set in the environment.
    Raises LinkedInAuthError if redirected to the login wall.
    """
    import os
    import time
    from app.schemas import (
        LinkedInProfile,
        LinkedInExperience,
        LinkedInEducation,
        LinkedInSkill,
        LinkedInCertification,
        LinkedInLanguage,
        LinkedInProject,
        LinkedInPublication,
        LinkedInHonor,
        LinkedInVolunteer,
        LinkedInCourse,
    )

    session_cookie = os.getenv("LINKEDIN_SESSION_COOKIE", "")
    delay_ms = int(os.getenv("LINKEDIN_SCRAPE_DELAY_MS", "2000"))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError("playwright is required for LinkedIn scraping. Run: pip install playwright && playwright install chromium") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        if session_cookie:
            context.add_cookies([{
                "name": "li_at",
                "value": session_cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }])

        page = context.new_page()
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(delay_ms / 1000)

        # Detect auth wall
        if "authwall" in page.url or "login" in page.url:
            browser.close()
            raise LinkedInAuthError(f"LinkedIn redirected to login page. Set LINKEDIN_SESSION_COOKIE in .env. Redirected to: {page.url}")

        html = page.content()
        browser.close()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    def _text(el) -> str:
        return el.get_text(separator=" ", strip=True) if el else ""

    def _parse_personal(s) -> dict:
        data: dict = {"profile_url": profile_url}
        name_el = s.select_one("h1.text-heading-xlarge, h1[class*='top-card-layout__title']")
        data["full_name"] = _text(name_el)
        headline_el = s.select_one(".text-body-medium.break-words, .top-card-layout__headline")
        data["headline"] = _text(headline_el) or None
        loc_el = s.select_one(".text-body-small.inline.t-black--light.break-words, .top-card__subline-item")
        data["location"] = _text(loc_el) or None
        pic_el = s.select_one("img.pv-top-card-profile-picture__image, img[class*='profile-photo']")
        data["profile_picture_url"] = pic_el.get("src") if pic_el else None
        about_el = s.select_one("#about ~ div .inline-show-more-text, .pv-about__summary-text, div[data-generated-suggestion-target='urn:li:fs_aboutPromptContribution'] span")
        data["about"] = _text(about_el) or None
        return data

    def _parse_experience(s) -> list[LinkedInExperience]:
        items = []
        section = s.find("section", {"id": "experience"}) or s.find("div", {"id": "experience-section"})
        if not section:
            return items
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            title_el = li.select_one("span[aria-hidden='true']") or li.select_one(".mr1.t-bold span")
            company_el = li.select_one("span.t-14.t-normal span[aria-hidden='true']") or li.select_one(".pv-entity__secondary-title")
            date_el = li.select_one("span.t-14.t-normal.t-black--light span[aria-hidden='true']")
            desc_el = li.select_one(".pv-entity__description, .jobs-box__html-content span[aria-hidden='true']")
            date_str = _text(date_el)
            start_date = end_date = None
            is_current = False
            if " – " in date_str:
                parts = date_str.split(" – ")
                start_date = parts[0].strip()
                end_str = parts[1].strip() if len(parts) > 1 else ""
                if "Present" in end_str or "present" in end_str:
                    is_current = True
                    end_date = None
                else:
                    end_date = end_str
            items.append(LinkedInExperience(
                title=_text(title_el),
                company=_text(company_el),
                start_date=start_date,
                end_date=end_date,
                is_current=is_current,
                description=_text(desc_el) or None,
            ))
        return items

    def _parse_education(s) -> list[LinkedInEducation]:
        items = []
        section = s.find("section", {"id": "education"}) or s.find("div", {"id": "education-section"})
        if not section:
            return items
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            els = li.select("span[aria-hidden='true']")
            school = _text(els[0]) if len(els) > 0 else ""
            degree_field = _text(els[1]) if len(els) > 1 else ""
            degree = field_of_study = None
            if ", " in degree_field:
                d, f = degree_field.split(", ", 1)
                degree, field_of_study = d.strip(), f.strip()
            elif degree_field:
                degree = degree_field
            dates = _text(els[2]) if len(els) > 2 else ""
            start_year = end_year = None
            if " – " in dates:
                parts = dates.split(" – ")
                start_year = parts[0].strip()
                end_year = parts[1].strip() if len(parts) > 1 else None
            items.append(LinkedInEducation(
                school=school,
                degree=degree,
                field_of_study=field_of_study,
                start_year=start_year,
                end_year=end_year,
            ))
        return items

    def _parse_skills(s) -> list[LinkedInSkill]:
        items = []
        section = s.find("section", {"id": "skills"}) or s.find("div", {"id": "skills-section"})
        if not section:
            return items
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            name_el = li.select_one("span[aria-hidden='true']")
            name = _text(name_el)
            if name:
                items.append(LinkedInSkill(skill_name=name))
        return items

    def _parse_certifications(s) -> list[LinkedInCertification]:
        items = []
        section = s.find("section", {"id": "certifications"}) or s.find("div", {"id": "certifications-section"})
        if not section:
            return items
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            els = li.select("span[aria-hidden='true']")
            name = _text(els[0]) if els else ""
            org = _text(els[1]) if len(els) > 1 else None
            date = _text(els[2]) if len(els) > 2 else None
            if name:
                items.append(LinkedInCertification(name=name, issuing_org=org, issue_date=date))
        return items

    def _parse_languages(s) -> list[LinkedInLanguage]:
        items = []
        section = s.find("section", {"id": "languages"})
        if not section:
            return items
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            els = li.select("span[aria-hidden='true']")
            lang = _text(els[0]) if els else ""
            prof = _text(els[1]) if len(els) > 1 else None
            if lang:
                items.append(LinkedInLanguage(language=lang, proficiency=prof))
        return items

    def _parse_section_items(s, section_id: str) -> list[dict]:
        section = s.find("section", {"id": section_id})
        if not section:
            return []
        results = []
        for li in section.select("li.artdeco-list__item, li[class*='pvs-list__item']"):
            els = li.select("span[aria-hidden='true']")
            results.append([_text(e) for e in els])
        return results

    personal = _parse_personal(soup)
    profile = LinkedInProfile(
        **personal,
        experience=_parse_experience(soup),
        education=_parse_education(soup),
        skills=_parse_skills(soup),
        certifications=_parse_certifications(soup),
        languages=_parse_languages(soup),
    )

    # Volunteer, projects, honors — best-effort
    for row in _parse_section_items(soup, "volunteer-experience"):
        if row:
            profile.volunteer.append(LinkedInVolunteer(role=row[0], organization=row[1] if len(row) > 1 else None))
    for row in _parse_section_items(soup, "projects"):
        if row:
            profile.projects.append(LinkedInProject(name=row[0], description=row[1] if len(row) > 1 else None))
    for row in _parse_section_items(soup, "honors-awards"):
        if row:
            profile.honors.append(LinkedInHonor(title=row[0], issuer=row[1] if len(row) > 1 else None))
    for row in _parse_section_items(soup, "publications"):
        if row:
            profile.publications.append(LinkedInPublication(title=row[0], publisher=row[1] if len(row) > 1 else None))
    for row in _parse_section_items(soup, "courses"):
        if row:
            profile.courses.append(LinkedInCourse(name=row[0]))

    return profile


def run_scrape(config, skip_intelligence: bool = False, sites: Optional[list[str]] = None, stop_event=None, progress_callback=None) -> dict:
    """Run a full scrape cycle: fetch -> filter -> normalize -> dedup -> persist.

    config: SearchConfig ORM object (may be detached from a session — scalar
            attributes are read directly, no lazy loading required).
    Creates its own DB session; never accepts one from the caller.
    Returns a summary dict: {total_scraped, inserted, skipped, remote_filtered, ...}
    On error returns {error: str}.
    """
    try:
        import pandas as pd
        from jobspy import scrape_jobs  # import inside function for easier mocking

        search_terms = build_search_terms(config)
        country = getattr(config, "country", None) or "israel"
        max_age_hours = getattr(config, "max_age_hours", None) or 72
        results_wanted = getattr(config, "results_wanted", None) or 50
        include_remote = bool(getattr(config, "include_remote", False))
        # Pass is_remote=True to JobSpy when remote is included; False = no filter
        is_remote_param = True if include_remote else False

        # Determine which providers to run
        _GLASSDOOR_COUNTRIES = {"usa", "canada", "uk", "australia", "germany", "france", "india", "singapore", "netherlands"}
        _JOBSPY_PROVIDERS = {"linkedin", "indeed", "glassdoor"}
        if sites is not None:
            jobspy_sites = [s for s in sites if s in _JOBSPY_PROVIDERS]
            run_comeet = "comeet" in sites
        else:
            jobspy_sites = ["linkedin", "indeed"]
            if country.lower() in _GLASSDOOR_COUNTRIES:
                jobspy_sites.append("glassdoor")
            run_comeet = bool(getattr(config, "include_comeet", False))

        def _cb(state: dict) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(state)
                except Exception:
                    pass

        _cb({"phase": "fetching", "fetch_sources": {}})

        all_dfs = []
        if jobspy_sites:
            for search_term in search_terms:
                logger.info(
                    "Scraping jobs: search_term=%r location=%r country=%r hours_old=%r results_wanted=%r sites=%r",
                    search_term,
                    getattr(config, "location", "") or "",
                    country,
                    max_age_hours,
                    results_wanted,
                    jobspy_sites,
                )
                df_part = scrape_jobs(
                    site_name=jobspy_sites,
                    search_term=search_term,
                    location=getattr(config, "location", "") or "",
                    country_indeed=country,
                    is_remote=is_remote_param,
                    hours_old=max_age_hours,
                    job_type=JOB_TYPE,
                    results_wanted=results_wanted,
                    verbose=0,
                    linkedin_fetch_description=True,
                )
                all_dfs.append(df_part)

        # Comeet integration
        comeet_discovered = 0
        comeet_parsed = 0
        comeet_failed = 0
        if run_comeet:
            try:
                from app.scrapers.comeet import comeet_search
                comeet_df, comeet_stats = comeet_search(search_terms)
                comeet_discovered = comeet_stats.get("discovered", 0)
                comeet_parsed = comeet_stats.get("parsed", 0)
                comeet_failed = comeet_stats.get("failed", 0)
                if not comeet_df.empty:
                    all_dfs.append(comeet_df)
            except Exception as _comeet_exc:
                logger.warning("Comeet scrape failed, continuing without Comeet results: %s", _comeet_exc, exc_info=True)

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            # DataFrame-level dedup by job_url before DB hash check
            if "job_url" in df.columns:
                df = df.drop_duplicates(subset=["job_url"]).copy()
        else:
            df = pd.DataFrame()

        total_scraped = len(df)
        fetch_sources: dict = {}
        if not df.empty and "site" in df.columns:
            fetch_sources = {k: int(v) for k, v in df["site"].value_counts().to_dict().items()}
        _cb({"phase": "fetching_done", "fetch_sources": fetch_sources, "rows_total": total_scraped})

        # Apply post-scrape filter pipeline (blocked companies → exclude keywords → min salary)
        df, filter_counts = apply_filters(df, config)

        rows_total_filtered = len(df)
        inserted = 0
        skipped = 0
        remote_filtered = 0
        scored = 0
        score_skipped = 0
        score_failed = 0
        rows_done = 0

        def _row_cb() -> None:
            _cb({
                "phase": "processing",
                "fetch_sources": fetch_sources,
                "rows_total": rows_total_filtered,
                "rows_done": rows_done,
                "inserted": inserted,
                "skipped": skipped,
                "scored": scored,
                "score_failed": score_failed,
            })

        _cb({
            "phase": "processing",
            "fetch_sources": fetch_sources,
            "rows_total": rows_total_filtered,
            "rows_done": 0,
            "inserted": 0,
            "skipped": 0,
            "scored": 0,
            "score_failed": 0,
        })

        with SessionLocal() as session:
            repo = JobRepository(session)
            inserted_ids: list[int] = []
            profile = repo.get_profile()

            stopped = False
            for _, row_series in df.iterrows():
                if stop_event is not None and stop_event.is_set():
                    logger.info("Scrape stop requested — breaking out of per-row loop.")
                    stopped = True
                    break
                rows_done += 1
                row = row_series.to_dict()

                # Remote filter: drop remote rows when config says no remote
                if not include_remote and row.get("is_remote") is True:
                    remote_filtered += 1
                    _row_cb()
                    continue

                normalized = _normalize_row(row)

                if normalized is None:
                    skipped += 1
                    _row_cb()
                    continue

                if repo.get_job_by_hash(normalized["job_hash"]):
                    skipped += 1
                    _row_cb()
                    continue

                created = repo.add_job(**normalized)
                inserted_ids.append(created.id)
                inserted += 1

                # Reject-by evaluation (prospective). Runs before company enrichment so
                # property=company/source rules are checked; sector/company_type rules
                # are also re-evaluated below after company_id is set.
                try:
                    from app.services.reject_service import evaluate_job_on_insert
                    evaluate_job_on_insert(session, created)
                except Exception as _exc:
                    logger.warning("Reject rule evaluation failed for job_id=%s: %s", created.id, _exc)

                # Company enrichment (cached per normalized company name)
                _company_name = normalized.get("company", "")
                if _company_name:
                    _name_norm = _company_name.strip().lower()
                    try:
                        _co = repo.get_company_by_normalized_name(_name_norm)
                        if _co is None:
                            from app.services.llm_service import enrich_company as _enrich_co

                            def _to_str(v):
                                s = str(v or "").strip()
                                return "" if s.lower() == "nan" else s

                            _industry = _to_str(row.get("company_industry")) or None
                            _co_desc = _to_str(row.get("company_description")) or None
                            _enrichment = _enrich_co(
                                company_name=_company_name,
                                company_industry=_industry,
                                company_description=_co_desc,
                            )
                            if _enrichment:
                                _co = repo.upsert_company(
                                    name_normalized=_name_norm,
                                    name_display=_company_name,
                                    sector=_enrichment.get("sector"),
                                    company_type=_enrichment.get("company_type"),
                                    what_they_do=_enrichment.get("what_they_do"),
                                )
                        if _co:
                            created.company_id = _co.id
                            session.commit()
                            # Re-evaluate reject rules now that sector/company_type are known
                            if not created.is_rejected:
                                try:
                                    from app.services.reject_service import evaluate_job_on_insert
                                    evaluate_job_on_insert(session, created)
                                except Exception as _re_exc:
                                    logger.warning("Reject rule re-evaluation failed: %s", _re_exc)
                    except Exception as _exc:
                        logger.warning("Company enrichment failed for %r: %s", _company_name, _exc)

                if created.is_rejected:
                    inserted -= 1
                    inserted_ids.remove(created.id)
                    _row_cb()
                    continue

                if not skip_intelligence:
                    try:
                        from app.services.llm_service import extract_job_intelligence
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
                            from app.services.llm_service import get_enhanced_fit_score
                            score_result = get_enhanced_fit_score(created, profile)
                            if score_result is not None:
                                import datetime as _dt_mod
                                _job_summary = score_result.get("job_summary")
                                _score_to_store = {k: v for k, v in score_result.items() if k != "job_summary"}
                                created.fit_score = score_result.get("overall_score")
                                created.fit_summary = score_result.get("summary")
                                created.score_breakdown_json = json.dumps(_score_to_store)
                                created.salary_estimated = score_result.get("salary_estimated")
                                if _job_summary:
                                    created.summary_tech_stack_json = json.dumps(_job_summary.get("tech_stack", []))
                                    created.summary_qualifications_json = json.dumps(_job_summary.get("qualifications", []))
                                    created.summary_experience_needed = _job_summary.get("experience_needed")
                                    created.summary_general_description = _job_summary.get("general_description")
                                    created.summary_generated_at = _dt_mod.datetime.now(_dt_mod.timezone.utc)
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

                _row_cb()

            _cb({
                "phase": "done",
                "fetch_sources": fetch_sources,
                "rows_total": rows_total_filtered,
                "rows_done": rows_done,
                "inserted": inserted,
                "skipped": skipped,
                "scored": scored,
                "score_failed": score_failed,
            })

            from app.services.watch_service import match_new_jobs_to_watch_rules
            notifications_created = match_new_jobs_to_watch_rules(session, inserted_ids)

        logger.info(
            "Scrape complete: total=%d inserted=%d skipped=%d remote_filtered=%d "
            "blocked_companies=%d exclude_keywords=%d min_salary=%d "
            "notifications=%d scored=%d score_skipped=%d score_failed=%d "
            "comeet_discovered=%d comeet_parsed=%d comeet_failed=%d",
            total_scraped,
            inserted,
            skipped,
            remote_filtered,
            filter_counts["blocked_companies"],
            filter_counts["exclude_keywords"],
            filter_counts["min_salary"],
            notifications_created,
            scored,
            score_skipped,
            score_failed,
            comeet_discovered,
            comeet_parsed,
            comeet_failed,
        )
        return {
            "total_scraped": total_scraped,
            "inserted": inserted,
            "skipped": skipped,
            "remote_filtered": remote_filtered,
            "filter_blocked_companies": filter_counts["blocked_companies"],
            "filter_exclude_keywords": filter_counts["exclude_keywords"],
            "filter_min_salary": filter_counts["min_salary"],
            "notifications_created": notifications_created,
            "scored": scored,
            "score_skipped": score_skipped,
            "score_failed": score_failed,
            "comeet_discovered": comeet_discovered,
            "comeet_parsed": comeet_parsed,
            "comeet_failed": comeet_failed,
            "stopped": stopped,
        }

    except Exception as e:
        logger.error("Scrape failed: %s", e, exc_info=True)
        return {"error": str(e)}
