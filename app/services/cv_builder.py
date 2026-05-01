"""CV Builder — maps a LinkedInProfile into a CVData model, optionally AI-rewriting bullets."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.schemas import (
    CVData,
    CVMeta,
    LinkedInProfile,
    LinkedInExperience,
    LinkedInSkill,
)

logger = logging.getLogger(__name__)


def _ai_rewrite_bullets(text: str) -> str:
    """Rewrite a free-text description into 3 concise CV bullet points via the configured LLM."""
    try:
        from app.services.llm_service import _get_client, _get_model
        client = _get_client()
        model = _get_model()
        prompt = (
            "Rewrite the following work experience description as exactly 3 concise CV bullet points. "
            "Each bullet must start with a strong action verb. Use plain text with '• ' prefix. "
            "Do not add extra explanation.\n\n"
            f"Description:\n{text}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("CV bullet rewrite failed: %s", exc)
        return text


def build_cv_from_profile(
    profile: LinkedInProfile,
    template_name: str = "default",
    rewrite_bullets: Optional[bool] = None,
) -> CVData:
    """Map a LinkedInProfile to a CVData model.

    rewrite_bullets: if None, reads CV_AI_REWRITE env var (default True).
    """
    if rewrite_bullets is None:
        rewrite_bullets = os.getenv("CV_AI_REWRITE", "true").lower() not in ("false", "0", "no")

    # Rewrite experience descriptions if enabled
    experience = []
    for exp in profile.experience:
        description = exp.description
        if rewrite_bullets and description and len(description) > 40:
            description = _ai_rewrite_bullets(description)
        experience.append(LinkedInExperience(
            title=exp.title,
            company=exp.company,
            company_url=exp.company_url,
            location=exp.location,
            start_date=exp.start_date,
            end_date=exp.end_date,
            is_current=exp.is_current,
            description=description,
            employment_type=exp.employment_type,
        ))

    # Deduplicate and sort skills by endorsement count (desc)
    seen: set[str] = set()
    skills: list[LinkedInSkill] = []
    for s in sorted(profile.skills, key=lambda x: x.endorsement_count, reverse=True):
        key = s.skill_name.lower().strip()
        if key and key not in seen:
            seen.add(key)
            skills.append(s)

    meta = CVMeta(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_url=profile.profile_url,
        template_name=template_name,
        language="en",
    )

    return CVData(
        cv_meta=meta,
        full_name=profile.full_name,
        headline=profile.headline,
        location=profile.location,
        email=profile.email,
        phone=profile.phone,
        profile_url=profile.profile_url,
        about=profile.about,
        experience=experience,
        education=profile.education,
        skills=skills,
        certifications=profile.certifications,
        languages=profile.languages,
        projects=profile.projects,
        publications=profile.publications,
        honors=profile.honors,
        volunteer=profile.volunteer,
    )
