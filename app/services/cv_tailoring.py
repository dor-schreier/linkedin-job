"""LLM-driven CV tailoring — adapts a candidate's profile to one specific job."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.models import Job, Profile, UploadedCV
from app.schemas_core import (
    CVData,
    CVMeta,
    LinkedInCertification,
    LinkedInEducation,
    LinkedInExperience,
    LinkedInProfile,
    LinkedInProject,
    LinkedInSkill,
)
from app.services.llm_service import _chat_complete, _get_model

logger = logging.getLogger("app.services.cv_tailoring")


def _load_uploaded_profile(uploaded: Optional[UploadedCV]) -> Optional[LinkedInProfile]:
    if not uploaded:
        return None
    try:
        return LinkedInProfile.model_validate(json.loads(uploaded.parsed_json))
    except Exception as exc:
        logger.warning("Could not parse uploaded CV JSON: %s", exc)
        return None


def _extract_keywords_from_description(description: str) -> list[str]:
    """Cheap fallback: pull capitalized tokens & well-known tech words from JD."""
    if not description:
        return []
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9\+\#\.\-]{1,30}\b", description)
    seen: list[str] = []
    for t in tokens:
        tl = t.lower()
        if tl in {"the", "and", "with", "for", "you", "your", "our", "are", "will", "this", "that"}:
            continue
        if len(t) < 2:
            continue
        if t.lower() not in [s.lower() for s in seen]:
            seen.append(t)
        if len(seen) >= 30:
            break
    return seen


def build_tailoring_inputs(
    profile: Optional[Profile],
    uploaded: Optional[UploadedCV],
    job: Job,
) -> dict[str, Any]:
    """Assemble the data the LLM needs to tailor a CV.

    Prefers the uploaded LinkedIn PDF's full experience over Profile's compact fields.
    """
    linkedin = _load_uploaded_profile(uploaded)

    intel: dict[str, Any] = {}
    if getattr(job, "intelligence_json", None):
        try:
            intel = json.loads(job.intelligence_json)
        except Exception as exc:
            logger.warning("intelligence_json unparseable for job %s: %s", job.id, exc)
            intel = {}

    if not intel:
        logger.warning("job %s has no intelligence block — falling back to JD keywords", job.id)
        intel = {
            "required_skills": _extract_keywords_from_description(job.description or "")[:15],
            "preferred_skills": [],
            "tech_stack": [],
            "seniority_level": None,
            "red_flags": [],
        }

    candidate: dict[str, Any] = {}
    if linkedin:
        candidate = {
            "full_name": linkedin.full_name,
            "headline": linkedin.headline,
            "location": linkedin.location,
            "email": linkedin.email,
            "phone": linkedin.phone,
            "profile_url": linkedin.profile_url,
            "about": linkedin.about,
            "experience": [e.model_dump() for e in linkedin.experience],
            "education": [e.model_dump() for e in linkedin.education],
            "skills": [s.model_dump() for s in linkedin.skills],
            "certifications": [c.model_dump() for c in linkedin.certifications],
            "projects": [p.model_dump() for p in linkedin.projects],
        }
    if profile:
        candidate.setdefault("current_title", profile.current_title)
        candidate.setdefault("target_title", profile.target_title)
        candidate.setdefault("years_experience", profile.years_experience)
        if not candidate.get("skills") and profile.skills:
            candidate["skills"] = [
                {"skill_name": s.strip(), "endorsement_count": 0}
                for s in profile.skills.split(",") if s.strip()
            ]
        if not candidate.get("profile_url") and profile.linkedin_url:
            candidate["profile_url"] = profile.linkedin_url

    job_ctx = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": (job.description or "")[:6000],
        "intelligence": intel,
    }
    return {"candidate": candidate, "job": job_ctx, "linkedin": linkedin}


_SYSTEM = (
    "You are an expert CV writer. Given a candidate's full profile and a target job posting, "
    "you rewrite the CV to maximize relevance to that job. You ALWAYS return valid JSON only."
)

_PROMPT_TEMPLATE = """\
Tailor this candidate's CV for the target job below.

== TARGET JOB ==
Title: {title}
Company: {company}
Location: {location}
Intelligence: {intelligence}
Description (truncated): {description}

== CANDIDATE PROFILE ==
{candidate}

== INSTRUCTIONS ==
Produce JSON with this exact shape (no extra prose, no markdown fences):
{{
  "tailored_summary": "3-4 line professional summary written for THIS job, weaving in relevant achievements and the job's required tech.",
  "prioritized_skills": ["Top 12 skills from the candidate, ordered by relevance to the job", "..."],
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "start_date": "...",
      "end_date": "...",
      "is_current": false,
      "description": "• Bullet 1 (action verb, quantified, weighted toward required skills)\\n• Bullet 2\\n• Bullet 3"
    }}
  ],
  "education": [{{"school":"...","degree":"...","field_of_study":"...","start_year":"...","end_year":"..."}}],
  "certifications": [{{"name":"...","issuing_org":"...","issue_date":"..."}}],
  "projects": [{{"name":"...","description":"...","url":"..."}}]
}}

Rules:
- Keep experiences in reverse chronological order. Include ALL roles, but rewrite each description as exactly 3 bullets.
- Bullets must start with action verbs (Led, Built, Designed, Shipped, etc.) and emphasize required_skills + tech_stack from the job intelligence.
- prioritized_skills: pick up to 12, drop anything irrelevant.
- Filter education/certifications/projects to the most relevant ~5 items each; drop the rest.
- Do not invent experience or credentials the candidate doesn't have.
- Do not use exact wording from job post, paraphrase.
- Return valid JSON ONLY. No commentary.
"""


def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def tailor_cv(
    profile: Optional[Profile],
    uploaded: Optional[UploadedCV],
    job: Job,
) -> tuple[CVData, str]:
    """Run a single LLM call and return (CVData, model_used).

    Raises RuntimeError on LLM/parse failure.
    """
    inputs = build_tailoring_inputs(profile, uploaded, job)
    candidate = inputs["candidate"]
    job_ctx = inputs["job"]
    linkedin: Optional[LinkedInProfile] = inputs["linkedin"]

    prompt = _PROMPT_TEMPLATE.format(
        title=job_ctx["title"] or "",
        company=job_ctx["company"] or "",
        location=job_ctx["location"] or "",
        intelligence=json.dumps(job_ctx["intelligence"], ensure_ascii=False),
        description=job_ctx["description"],
        candidate=json.dumps(candidate, ensure_ascii=False, default=str)[:12000],
    )

    model = _get_model("recommend")
    try:
        raw = _chat_complete(
            tier="recommend",
            system=_SYSTEM,
            user=prompt,
            max_tokens=4096,
            temperature=0.4,
            json_mode=True,
        )
    except Exception as exc:
        logger.error("LLM call failed during CV tailoring (job %s): %s", job.id, exc)
        raise RuntimeError(f"LLM tailoring call failed: {exc}") from exc

    try:
        from app.services.llm_service import _load_llm_json
        data = _load_llm_json(raw)
    except Exception as exc:
        logger.error("Could not parse tailored CV JSON (job %s): %s\nRaw: %s", job.id, exc, raw[:500])
        raise RuntimeError(f"Could not parse tailored CV JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Tailored CV response was not a JSON object")

    full_name = (linkedin.full_name if linkedin else "") or ""
    headline = (linkedin.headline if linkedin else None) or (profile.current_title if profile else None)
    location = (linkedin.location if linkedin else None)
    email = (linkedin.email if linkedin else None)
    phone = (linkedin.phone if linkedin else None)
    profile_url = (linkedin.profile_url if linkedin else None) or (profile.linkedin_url if profile else None)

    def _coerce_list(key: str) -> list[dict]:
        v = data.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
        return []

    exp_items: list[LinkedInExperience] = []
    for e in _coerce_list("experience"):
        try:
            exp_items.append(LinkedInExperience(
                title=_safe_str(e.get("title")) or "",
                company=_safe_str(e.get("company")) or "",
                location=_safe_str(e.get("location")),
                start_date=_safe_str(e.get("start_date")),
                end_date=_safe_str(e.get("end_date")),
                is_current=bool(e.get("is_current") or False),
                description=_safe_str(e.get("description")),
            ))
        except Exception:
            continue

    edu_items: list[LinkedInEducation] = []
    for e in _coerce_list("education"):
        try:
            edu_items.append(LinkedInEducation(
                school=_safe_str(e.get("school")) or "",
                degree=_safe_str(e.get("degree")),
                field_of_study=_safe_str(e.get("field_of_study")),
                start_year=_safe_str(e.get("start_year")),
                end_year=_safe_str(e.get("end_year")),
            ))
        except Exception:
            continue

    cert_items: list[LinkedInCertification] = []
    for c in _coerce_list("certifications"):
        try:
            cert_items.append(LinkedInCertification(
                name=_safe_str(c.get("name")) or "",
                issuing_org=_safe_str(c.get("issuing_org")),
                issue_date=_safe_str(c.get("issue_date")),
            ))
        except Exception:
            continue

    proj_items: list[LinkedInProject] = []
    for p in _coerce_list("projects"):
        try:
            proj_items.append(LinkedInProject(
                name=_safe_str(p.get("name")) or "",
                description=_safe_str(p.get("description")),
                url=_safe_str(p.get("url")),
            ))
        except Exception:
            continue

    prioritized_skills_raw = data.get("prioritized_skills") or []
    if isinstance(prioritized_skills_raw, list):
        prioritized_skills = [str(s) for s in prioritized_skills_raw if s][:12]
    else:
        prioritized_skills = []

    skills_models = [LinkedInSkill(skill_name=s, endorsement_count=0) for s in prioritized_skills]

    cv = CVData(
        cv_meta=CVMeta(
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_url=profile_url or "",
            template_name="tailored",
            language="en",
        ),
        full_name=full_name,
        headline=headline,
        location=location,
        email=email,
        phone=phone,
        profile_url=profile_url,
        about=None,
        experience=exp_items,
        education=edu_items,
        skills=skills_models,
        certifications=cert_items,
        projects=proj_items,
        tailored_for_job_id=job.id,
        tailored_summary=_safe_str(data.get("tailored_summary")),
        prioritized_skills=prioritized_skills,
    )
    return cv, model
