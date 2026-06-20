"""Similarity engine — computes job-to-target similarity across 4 dimensions."""
from __future__ import annotations

import json
import re
from typing import Optional

SENIORITY_SCALE = ["intern", "junior", "mid", "senior", "staff", "principal", "lead", "manager", "director", "vp"]

_SENIORITY_ALIASES: dict[str, str] = {
    "entry": "junior",
    "entry level": "junior",
    "associate": "junior",
    "sr": "senior",
    "sr.": "senior",
    "tech lead": "lead",
    "team lead": "lead",
    "engineering manager": "manager",
    "em": "manager",
    "engineering lead": "lead",
    "vp of engineering": "vp",
    "vp engineering": "vp",
    "director of engineering": "director",
}


def _normalize_tokens(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into tokens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return {t for t in text.split() if len(t) > 1}


def _extract_seniority(job) -> Optional[str]:
    """Return the canonical seniority level for a job, or None."""
    level = None
    if job.intelligence_json:
        try:
            intel = json.loads(job.intelligence_json)
            level = intel.get("seniority_level") or None
        except (json.JSONDecodeError, ValueError):
            pass
    if not level:
        return None
    level_lower = level.strip().lower()
    if level_lower in _SENIORITY_ALIASES:
        level_lower = _SENIORITY_ALIASES[level_lower]
    if level_lower in SENIORITY_SCALE:
        return level_lower
    # Try partial match
    for token in level_lower.split():
        if token in SENIORITY_SCALE:
            return token
    return None


def _extract_skills(job) -> set[str]:
    """Union of required_skills, preferred_skills, tech_stack from intelligence_json."""
    skills: set[str] = set()
    if job.intelligence_json:
        try:
            intel = json.loads(job.intelligence_json)
            for key in ("required_skills", "preferred_skills", "tech_stack"):
                for item in intel.get(key) or []:
                    skills.add(item.strip().lower())
        except (json.JSONDecodeError, ValueError):
            pass
    if job.summary_tech_stack_json:
        try:
            for item in json.loads(job.summary_tech_stack_json) or []:
                skills.add(item.strip().lower())
        except (json.JSONDecodeError, ValueError):
            pass
    if job.summary_qualifications_json:
        try:
            for item in json.loads(job.summary_qualifications_json) or []:
                skills.add(item.strip().lower())
        except (json.JSONDecodeError, ValueError):
            pass
    return skills


class TargetProfile:
    def __init__(
        self,
        title_tokens: set[str],
        skill_union: set[str],
        seniority_levels: set[str],
        sector_pairs: set[tuple[Optional[str], Optional[str]]],
    ):
        self.title_tokens = title_tokens
        self.skill_union = skill_union
        self.seniority_levels = seniority_levels
        self.sector_pairs = sector_pairs


def build_target_profile(session) -> Optional[TargetProfile]:
    """Aggregate all is_target jobs into a normalized feature bundle."""
    from app.repository import JobRepository
    repo = JobRepository(session)
    targets = repo.list_target_jobs()
    if not targets:
        return None

    title_tokens: set[str] = set()
    skill_union: set[str] = set()
    seniority_levels: set[str] = set()
    sector_pairs: set[tuple] = set()

    for job in targets:
        title_tokens |= _normalize_tokens(job.title or "")
        skill_union |= _extract_skills(job)
        seniority = _extract_seniority(job)
        if seniority:
            seniority_levels.add(seniority)
        sector = job.company_info.sector if job.company_info else None
        ctype = job.company_info.company_type if job.company_info else None
        sector_pairs.add((
            sector.strip().lower() if sector else None,
            ctype.strip().lower() if ctype else None,
        ))

    return TargetProfile(
        title_tokens=title_tokens,
        skill_union=skill_union,
        seniority_levels=seniority_levels,
        sector_pairs=sector_pairs,
    )


def title_sim(job_title: str, profile: TargetProfile) -> float:
    """Jaccard similarity of job title tokens vs the target title-token union."""
    if not profile.title_tokens:
        return 0.0
    job_tokens = _normalize_tokens(job_title)
    if not job_tokens:
        return 0.0
    intersection = job_tokens & profile.title_tokens
    union = job_tokens | profile.title_tokens
    return len(intersection) / len(union)


def skills_sim(job, profile: TargetProfile) -> float:
    """Jaccard overlap of job's skill set vs target union skill set."""
    if not profile.skill_union:
        return 0.0
    job_skills = _extract_skills(job)
    if not job_skills:
        return 0.0
    intersection = job_skills & profile.skill_union
    union = job_skills | profile.skill_union
    return len(intersection) / len(union)


def seniority_sim(job, profile: TargetProfile) -> Optional[float]:
    """Ordinal match: exact=1.0, adjacent=0.5, else 0.0. Best over target seniorities."""
    if not profile.seniority_levels:
        return None
    job_level = _extract_seniority(job)
    if job_level is None:
        return None
    if job_level not in SENIORITY_SCALE:
        return None
    job_idx = SENIORITY_SCALE.index(job_level)
    best = 0.0
    for target_level in profile.seniority_levels:
        if target_level not in SENIORITY_SCALE:
            continue
        target_idx = SENIORITY_SCALE.index(target_level)
        diff = abs(job_idx - target_idx)
        if diff == 0:
            best = 1.0
            break
        elif diff == 1:
            best = max(best, 0.5)
    return best


def sector_sim(job, profile: TargetProfile) -> Optional[float]:
    """Average of sector-match and company_type-match against all target (sector, ctype) pairs."""
    if not profile.sector_pairs:
        return None
    sector = job.company_info.sector if job.company_info else None
    ctype = job.company_info.company_type if job.company_info else None
    if sector is None and ctype is None:
        return None

    sector_norm = sector.strip().lower() if sector else None
    ctype_norm = ctype.strip().lower() if ctype else None

    best = 0.0
    for (t_sector, t_ctype) in profile.sector_pairs:
        score = 0.0
        count = 0
        if t_sector is not None or sector_norm is not None:
            score += 1.0 if sector_norm == t_sector else 0.0
            count += 1
        if t_ctype is not None or ctype_norm is not None:
            score += 1.0 if ctype_norm == t_ctype else 0.0
            count += 1
        if count > 0:
            best = max(best, score / count)
    return best


def compute_similarity(job, profile: TargetProfile, weights) -> dict:
    """Weighted sum of per-dimension similarities, scaled to 0–100.

    Dimensions with missing data are excluded and weights are renormalized.
    Returns {"score": int, "breakdown": {dim: {raw, weight, contribution}}}.
    """
    dims = {
        "title": (title_sim(job.title or "", profile), weights.weight_title),
        "skills": (skills_sim(job, profile), weights.weight_skills),
        "seniority": (seniority_sim(job, profile), weights.weight_seniority),
        "sector": (sector_sim(job, profile), weights.weight_sector),
    }

    breakdown = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for dim, (raw, w) in dims.items():
        if raw is None:
            continue
        contribution = raw * w
        breakdown[dim] = {"raw": round(raw, 4), "weight": w, "contribution": round(contribution, 4)}
        total_weight += w
        weighted_sum += contribution

    if total_weight == 0:
        return {"score": 0, "breakdown": breakdown}

    score = int(round((weighted_sum / total_weight) * 100))
    return {"score": max(0, min(100, score)), "breakdown": breakdown}


def derive_search_terms_from_targets(session, base_config) -> list[str]:
    """Extract top title keywords from target jobs as extra scrape search terms."""
    from collections import Counter
    from app.repository import JobRepository
    from app.scraper import build_search_terms

    repo = JobRepository(session)
    targets = repo.list_target_jobs()
    if not targets:
        return []

    base_terms = set(t.lower() for t in build_search_terms(base_config))

    token_counts: Counter = Counter()
    for job in targets:
        token_counts.update(_normalize_tokens(job.title or ""))

    stopwords = {"and", "or", "the", "of", "in", "at", "for", "to", "a", "an", "with", "senior", "junior", "lead"}
    top_tokens = [
        tok for tok, _ in token_counts.most_common(10)
        if tok not in stopwords and len(tok) > 2
    ]

    new_terms = []
    for tok in top_tokens[:3]:
        if tok not in base_terms:
            new_terms.append(tok)

    return new_terms


def recompute_all(session) -> int:
    """Recompute similarity_score and similarity_breakdown_json for all active jobs."""
    from app.repository import JobRepository
    repo = JobRepository(session)
    weights = repo.get_similarity_weights()

    if not weights.is_enabled:
        return 0

    profile = build_target_profile(session)
    if profile is None:
        # No targets — clear scores
        session.query(__import__('app.models', fromlist=['Job']).Job).filter(
            __import__('app.models', fromlist=['Job']).Job.similarity_score.isnot(None)
        ).update({"similarity_score": None, "similarity_breakdown_json": None})
        session.commit()
        return 0

    from app.models import Job
    jobs = session.query(Job).filter(Job.is_active == True, Job.is_rejected == False).all()  # noqa: E712
    count = 0
    for job in jobs:
        result = compute_similarity(job, profile, weights)
        job.similarity_score = result["score"]
        job.similarity_breakdown_json = json.dumps(result["breakdown"])
        count += 1

    session.commit()
    return count
