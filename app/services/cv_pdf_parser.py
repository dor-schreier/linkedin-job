"""Parse LinkedIn PDF exports into structured LinkedInProfile data."""
from __future__ import annotations

import io
import logging
from typing import Optional

from app.schemas_core import LinkedInProfile

logger = logging.getLogger("app.services.cv_pdf_parser")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF using pypdf."""
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError("pypdf is not installed — add pypdf>=4.0 to requirements.txt") from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except Exception as exc:
        logger.error("pypdf extraction failed: %s", exc)
        raise ValueError(f"Could not read PDF: {exc}") from exc


def parse_linkedin_pdf(text: str) -> LinkedInProfile:
    """Send extracted PDF text to the LLM and parse into a LinkedInProfile."""
    from app.services.llm_service import parse_linkedin_profile_text

    data = parse_linkedin_profile_text(text)
    if not data:
        raise ValueError("Could not parse profile content — try re-uploading")

    try:
        return LinkedInProfile.model_validate(data)
    except Exception as exc:
        logger.warning("LinkedInProfile validation partial failure: %s — using best-effort result", exc)
        try:
            return LinkedInProfile.model_validate({k: v for k, v in data.items() if v is not None})
        except Exception:
            raise ValueError("Could not parse profile content — try re-uploading") from exc


def parse_pdf_to_profile(file_bytes: bytes) -> LinkedInProfile:
    """Top-level orchestrator: bytes → LinkedInProfile."""
    text = extract_text_from_pdf(file_bytes)
    if len(text.strip()) < 200:
        raise ValueError("PDF appears empty or image-only — re-export from LinkedIn with text layer")
    logger.info("Extracted %d chars from PDF, sending to LLM for parsing", len(text))
    return parse_linkedin_pdf(text)


def _normalize_date_key(date_str: str | None) -> tuple[int, int] | None:
    """Normalize a date string to (year, month) for dedup key comparison."""
    import re
    if not date_str:
        return None
    s = date_str.strip()
    m = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', s, re.IGNORECASE)
    if m:
        month_map = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                     "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
        return (int(m.group(2)), month_map[m.group(1).lower()[:3]])
    m = re.search(r'(\d{4})', s)
    if m:
        return (int(m.group(1)), 1)
    return None


def merge_profiles(profiles: list[LinkedInProfile]) -> LinkedInProfile:
    """Merge multiple LinkedInProfile objects into one.

    - Skills: union by skill_name (case-insensitive), keep highest endorsement_count
    - Experience: union, deduplicate by (company, title, normalized start_date)
    - Education/certifications/languages/projects: union with simple name-based dedup
    - Scalar fields: most-recently-uploaded wins (last non-falsy value in list)
    """
    if not profiles:
        raise ValueError("No profiles to merge")
    if len(profiles) == 1:
        return profiles[0]

    # Skills
    skills_map: dict[str, object] = {}
    for p in profiles:
        for skill in p.skills:
            key = skill.skill_name.lower().strip()
            if not key:
                continue
            existing = skills_map.get(key)
            if existing is None or skill.endorsement_count > existing.endorsement_count:  # type: ignore[union-attr]
                skills_map[key] = skill
    merged_skills = sorted(skills_map.values(), key=lambda s: s.endorsement_count, reverse=True)  # type: ignore[attr-defined]

    # Experience
    seen_exp: set[tuple] = set()
    merged_experience = []
    for p in profiles:
        for exp in p.experience:
            key = (
                (exp.company or "").lower().strip(),
                (exp.title or "").lower().strip(),
                _normalize_date_key(exp.start_date),
            )
            if key not in seen_exp:
                seen_exp.add(key)
                merged_experience.append(exp)

    # Education
    seen_edu: set[tuple] = set()
    merged_education = []
    for p in profiles:
        for edu in p.education:
            key = ((edu.school or "").lower().strip(), (edu.degree or "").lower().strip())
            if key not in seen_edu:
                seen_edu.add(key)
                merged_education.append(edu)

    # Certifications
    seen_cert: set[tuple] = set()
    merged_certifications = []
    for p in profiles:
        for cert in p.certifications:
            key = ((cert.name or "").lower().strip(), (cert.issuing_org or "").lower().strip())
            if key not in seen_cert:
                seen_cert.add(key)
                merged_certifications.append(cert)

    # Languages
    seen_lang: set[str] = set()
    merged_languages = []
    for p in profiles:
        for lang in p.languages:
            key = (lang.language or "").lower().strip()
            if key and key not in seen_lang:
                seen_lang.add(key)
                merged_languages.append(lang)

    # Projects
    seen_proj: set[str] = set()
    merged_projects = []
    for p in profiles:
        for proj in p.projects:
            key = (proj.name or "").lower().strip()
            if key and key not in seen_proj:
                seen_proj.add(key)
                merged_projects.append(proj)

    def last_non_falsy(attr: str):
        val = None
        for p in profiles:
            v = getattr(p, attr, None)
            if v:
                val = v
        return val

    return LinkedInProfile(
        profile_url=last_non_falsy("profile_url") or "",
        full_name=last_non_falsy("full_name") or "",
        headline=last_non_falsy("headline"),
        location=last_non_falsy("location"),
        email=last_non_falsy("email"),
        phone=last_non_falsy("phone"),
        about=last_non_falsy("about"),
        experience=merged_experience,
        education=merged_education,
        skills=merged_skills,  # type: ignore[arg-type]
        certifications=merged_certifications,
        languages=merged_languages,
        projects=merged_projects,
        publications=[pub for p in profiles for pub in p.publications],
        honors=[h for p in profiles for h in p.honors],
        volunteer=[v for p in profiles for v in p.volunteer],
        recommendations=[r for p in profiles for r in p.recommendations],
        courses=[c for p in profiles for c in p.courses],
        test_scores=[t for p in profiles for t in p.test_scores],
        featured=[f for p in profiles for f in p.featured],
    )
