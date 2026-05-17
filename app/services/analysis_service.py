"""Keyword gap analysis — aggregates job intelligence data against user profile skills."""
from __future__ import annotations

import json
import logging
import os
from collections import Counter

from app.schemas import KeywordGap

logger = logging.getLogger(__name__)


def compute_keyword_gaps(jobs: list, profile_skills: str) -> list[dict]:
    """
    Parse intelligence_json from jobs, compute keyword frequency, and compare
    against profile skills. Returns list of KeywordGap dicts sorted by frequency.

    Args:
        jobs: list of Job ORM objects with intelligence_json field
        profile_skills: comma-separated skills string from user profile

    Returns:
        list of KeywordGap.model_dump() dicts, keywords appearing in >20% of jobs,
        sorted by frequency_pct descending (gaps first, then covered).
    """
    if not jobs:
        return []

    keyword_counts: Counter = Counter()
    total = 0

    for job in jobs:
        if not job.intelligence_json:
            continue
        try:
            intel = json.loads(job.intelligence_json)
        except (json.JSONDecodeError, ValueError):
            continue

        keywords: set[str] = set()
        for skill in intel.get("required_skills", []):
            if skill:
                keywords.add(skill.strip().lower())
        for tech in intel.get("tech_stack", []):
            if tech:
                keywords.add(tech.strip().lower())

        for kw in keywords:
            keyword_counts[kw] += 1
        total += 1

    if total == 0:
        return []

    profile_set: set[str] = set()
    if profile_skills:
        for s in profile_skills.split(","):
            s = s.strip().lower()
            if s:
                profile_set.add(s)

    gaps: list[KeywordGap] = []
    for keyword, count in keyword_counts.items():
        freq_pct = count / total * 100
        if freq_pct <= 20:
            continue
        in_profile = keyword in profile_set
        gaps.append(KeywordGap(keyword=keyword, count=count, frequency_pct=round(freq_pct, 1), in_profile=in_profile))

    # Sort: missing skills first (actionable), then covered; within each group by frequency desc
    gaps.sort(key=lambda g: (g.in_profile, -g.frequency_pct))
    return [g.model_dump() for g in gaps]


def get_gap_recommendations(gaps: list[dict]) -> str | None:
    """
    Call Groq to generate a natural-language paragraph recommending top missing skills.
    Returns string or None on error / missing API key.
    """
    missing = [g for g in gaps if not g["in_profile"]][:5]
    if not missing:
        return None

    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "groq" and not os.environ.get("GROQ_API_KEY"):
        return None

    try:
        from app.services.llm_service import _chat_complete

        skill_lines = "\n".join(
            f"- {g['keyword']} (appears in {g['frequency_pct']}% of matched jobs)"
            for g in missing
        )
        prompt = (
            "You are a career coach. Based on the following skills that appear frequently in the user's "
            "target jobs but are missing from their profile, write a concise 2-3 sentence recommendation "
            "paragraph. Be specific and actionable.\n\nMissing skills:\n" + skill_lines
        )

        content = _chat_complete(
            tier="recommend",
            system=None,
            user=prompt,
            max_tokens=200,
            temperature=0.5,
            json_mode=False,
        )
        return content.strip()
    except Exception as exc:
        logger.warning("get_gap_recommendations failed: %s", exc)
        return None
