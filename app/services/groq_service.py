"""Groq SDK wrappers for Phase 4 fit scoring + profile recommendations.

All Groq calls funnel through this module so route handlers stay LLM-agnostic.
Uses sync client to match the existing sync route pattern (JobSpy + SQLAlchemy sync).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from groq import Groq

logger = logging.getLogger(__name__)

FIT_MODEL = "llama-3.1-8b-instant"          # cheap, fast — many calls
RECOMMEND_MODEL = "llama-3.3-70b-versatile"  # higher quality — one call

FIT_SAFE_FALLBACK: dict[str, Any] = {
    "fit_score": None,
    "fit_summary": "Scoring unavailable",
    "salary_estimated": None,
}

FIT_SYSTEM_PROMPT = (
    "You are a job fit analyzer. Respond ONLY with valid JSON, no other text, "
    "no markdown code fences.\n"
    'Schema: {"fit_score": <int 0-100>, "fit_summary": "<1-2 sentence reason>", '
    '"salary_estimated": "<range or null>"}\n'
    "fit_score: how well the candidate matches this job (0=no match, 100=perfect).\n"
    "fit_summary: brief explanation why.\n"
    'salary_estimated: if no salary is listed below, estimate a typical range '
    'for this role and location (e.g. "$90,000 - $120,000/yr"). '
    "If salary is already provided, return null."
)

RECOMMEND_SYSTEM_PROMPT = (
    "You are a career coach. Given a job seeker's profile, return ONLY a JSON object, "
    "no other text, no markdown code fences.\n"
    'Schema: {"recommendations": ["bullet 1", "bullet 2", "bullet 3"]}\n'
    "Provide 3 to 5 concise, actionable suggestions to strengthen their profile "
    "for job searching."
)


def _get_client() -> Groq:
    # Reads GROQ_API_KEY from env automatically; passing explicitly for clarity.
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))


def _strip_code_fence(content: str) -> str:
    s = content.strip()
    if s.startswith("```"):
        # remove leading fence (```json\n or ```\n)
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()


def _parse_json_response(content: str) -> dict[str, Any]:
    try:
        data = json.loads(_strip_code_fence(content))
        return {
            "fit_score": int(data["fit_score"]) if data.get("fit_score") is not None else None,
            "fit_summary": str(data.get("fit_summary") or "Scoring unavailable"),
            "salary_estimated": data.get("salary_estimated"),
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse Groq fit response: %s", e)
        return dict(FIT_SAFE_FALLBACK)


def _parse_recommendations_response(content: str) -> list[str]:
    try:
        data = json.loads(_strip_code_fence(content))
        recs = data.get("recommendations") or []
        return [str(r) for r in recs if r]
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse Groq recommendations response: %s", e)
        return []


def _format_listed_salary(job) -> Optional[str]:
    smin = getattr(job, "salary_min", None)
    smax = getattr(job, "salary_max", None)
    cur = getattr(job, "salary_currency", None) or "$"
    if smin and smax:
        return f"{cur}{int(smin):,} - {cur}{int(smax):,}"
    if smin:
        return f"{cur}{int(smin):,}+"
    return None


def get_fit_score_and_salary(job, profile) -> dict[str, Any]:
    """Score one job against the user's profile. Bundles salary estimation.

    Returns: {"fit_score": int|None, "fit_summary": str, "salary_estimated": str|None}
    Never raises — returns FIT_SAFE_FALLBACK on any error.
    """
    listed = _format_listed_salary(job)
    salary_listed_str = listed if listed else "not listed"

    user_prompt = (
        f"Candidate profile:\n"
        f"- Current title: {getattr(profile, 'current_title', None) or 'n/a'}\n"
        f"- Target title: {getattr(profile, 'target_title', None) or 'n/a'}\n"
        f"- Skills: {getattr(profile, 'skills', None) or 'n/a'}\n"
        f"- Years of experience: {getattr(profile, 'years_experience', None) or 'n/a'}\n\n"
        f"Job:\n"
        f"- Title: {job.title}\n"
        f"- Company: {job.company}\n"
        f"- Location: {job.location or 'n/a'}\n"
        f"- Salary listed: {salary_listed_str}\n"
        f"- Description (first 1500 chars): {(job.description or '')[:1500]}"
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=FIT_MODEL,
            messages=[
                {"role": "system", "content": FIT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
        )
        content = response.choices[0].message.content or ""
        return _parse_json_response(content)
    except Exception as e:
        logger.error("Groq fit score call failed: %s", e)
        return dict(FIT_SAFE_FALLBACK)


def get_profile_recommendations(profile) -> list[str]:
    """Return 3-5 actionable bullets to strengthen the profile.

    Returns [] on any error.
    """
    user_prompt = (
        f"Profile:\n"
        f"- LinkedIn: {getattr(profile, 'linkedin_url', None) or 'not provided'}\n"
        f"- Current title: {getattr(profile, 'current_title', None) or 'n/a'}\n"
        f"- Target title: {getattr(profile, 'target_title', None) or 'n/a'}\n"
        f"- Skills: {getattr(profile, 'skills', None) or 'n/a'}\n"
        f"- Years of experience: {getattr(profile, 'years_experience', None) or 'n/a'}"
    )
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=RECOMMEND_MODEL,
            messages=[
                {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
        )
        content = response.choices[0].message.content or ""
        return _parse_recommendations_response(content)
    except Exception as e:
        logger.error("Groq recommendations call failed: %s", e)
        return []
