"""Provider-agnostic LLM wrappers for fit scoring, profile analysis, and enrichment.

Supports Groq (cloud) and Ollama (local) via the OpenAI-compatible API, and Vertex AI
(Gemini on GCP) via the google-genai SDK. Set LLM_PROVIDER=ollama, groq, or vertexai in
.env to switch providers. All LLM calls funnel through this module so route handlers
stay LLM-agnostic. Uses sync client to match the existing sync route pattern (JobSpy +
SQLAlchemy sync).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

try:
    from json_repair import loads as _json_repair_loads
    _HAS_JSON_REPAIR = True
except ImportError:
    _HAS_JSON_REPAIR = False

from openai import OpenAI

logger = logging.getLogger(__name__)


# ── Fallback / prompt constants ───────────────────────────────────────────────

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

JOB_INTELLIGENCE_SYSTEM_PROMPT = (
    "You are a job description analyst. Extract structured intelligence from the job posting and "
    "respond ONLY with valid JSON, no other text, no markdown code fences.\n"
    "Schema: {\n"
    '  "required_skills": ["<str>", ...],\n'
    '  "preferred_skills": ["<str>", ...],\n'
    '  "seniority_level": "<str>",\n'
    '  "remote_policy": "<onsite|hybrid|remote>",\n'
    '  "tech_stack": ["<str>", ...],\n'
    '  "team_size_signals": "<str or null>",\n'
    '  "salary_signals": "<str or null>",\n'
    '  "red_flags": ["<str>", ...]\n'
    "}\n"
    "Red flag heuristics: 'fast-paced' → understaffed, 'wear many hats' → under-resourced, "
    "'rockstar/ninja' → unrealistic expectations, 'family' culture → boundary issues.\n"
    "Return empty lists for list fields and null for optional string fields if not determinable."
)

JOB_INTELLIGENCE_SAFE_FALLBACK: dict[str, Any] = {
    "required_skills": [],
    "preferred_skills": [],
    "seniority_level": None,
    "remote_policy": None,
    "tech_stack": [],
    "team_size_signals": None,
    "salary_signals": None,
    "red_flags": [],
}

ENHANCED_FIT_SYSTEM_PROMPT = (
    "You are a job fit analyzer. Respond ONLY with valid JSON, no other text, "
    "no markdown code fences.\n"
    "Schema: {\n"
    '  "overall_score": <int 0-100>,\n'
    '  "matching_qualifications": ["<str>", ...],\n'
    '  "missing_qualifications": ["<str>", ...],\n'
    '  "experience_alignment": "<str — seniority match assessment>",\n'
    '  "red_flags": ["<str>", ...],\n'
    '  "application_priority": "<High|Medium|Low>",\n'
    '  "summary": "<2-3 sentence recommendation>",\n'
    '  "job_summary": {\n'
    '    "tech_stack": ["<str>", ...],\n'
    '    "qualifications": ["<str>", ...],\n'
    '    "experience_needed": "<str>",\n'
    '    "general_description": "<2-4 sentences>"\n'
    '  }\n'
    "}\n"
    "overall_score: 0=no match, 100=perfect fit.\n"
    "application_priority rules: High = score >= 75 AND posted < 7 days ago; "
    "Medium = score >= 50 OR posted < 14 days ago; Low = otherwise.\n"
    "job_summary: structured description of the role — tech_stack = technologies/tools mentioned; "
    "qualifications = required degrees/certifications/hard skills; "
    "experience_needed = years and seniority e.g. '3-5 years, mid-level'; "
    "general_description = 2-4 sentences on the role and day-to-day work.\n"
    "When jd_intelligence is provided, use its structured fields for both the fit assessment "
    "and the job_summary tech_stack/qualifications.\n"
    "Jobs older than 14 days should have lower priority.\n"
    "Never raises — return all fields even if uncertain."
)

LINKEDIN_ANALYSIS_SYSTEM_PROMPT = (
    "You are a LinkedIn profile optimization coach. Analyze the profile across exactly 8 sections "
    "and return ONLY valid JSON, no other text, no markdown code fences.\n"
    'Schema: {"sections": [{"name": "<section>", "score": <int 0-100>, "tasks": ["<task>", ...]}, ...], '
    '"overall_score": <int 0-100>, "top_priority": "<single most impactful change>"}\n'
    "The 8 sections MUST be: Headline, About / Summary, Experience Bullets, Skills Section, "
    "Featured Section, Recommendations, Keyword Density, Profile Completeness.\n"
    "Each section: score 0-100, 2-4 concrete actionable tasks.\n"
    "overall_score: weighted average across sections.\n"
    "top_priority: the single most impactful change to make first."
)

LINKEDIN_ANALYSIS_SAFE_FALLBACK: dict[str, Any] = {
    "sections": [],
    "overall_score": None,
    "top_priority": None,
}

COMPANY_ENRICHMENT_SYSTEM_PROMPT = (
    "You are a company research analyst. Given a company name and any available metadata, "
    "respond ONLY with valid JSON, no other text, no markdown code fences.\n"
    'Schema: {"sector": "<str>", "company_type": "<corporate|startup|scaleup|agency|non-profit|government|unknown>", '
    '"what_they_do": "<1-3 sentences>"}\n'
    "sector: industry sector (e.g. 'Fintech', 'Healthcare', 'Cybersecurity', 'E-commerce', 'SaaS', 'EdTech', 'Defense', 'Consulting').\n"
    "company_type: one of the exact enum values — corporate=large established company, startup=early-stage venture, "
    "scaleup=growing startup, agency=consulting/services firm, non-profit=NGO/charity, government=public sector, unknown=unclear.\n"
    "what_they_do: concise plain-language description of the company product/service/business model. "
    "If you have no reliable information, use empty string \"\".\n"
    "sector: if unknown use \"unknown\".\n"
    "NEVER write apologies, explanations, or 'I cannot find' text — use empty string or 'unknown' instead.\n"
    "If a <web_context> block is present, treat it as primary evidence and reference specific products, services, or "
    "details from it. Only fall back to training knowledge when the snippets are silent on a field."
)

JOB_SUMMARY_SYSTEM_PROMPT = (
    "You are a job description analyst. Extract a structured summary from the job posting and "
    "respond ONLY with valid JSON, no other text, no markdown code fences.\n"
    "Schema: {\n"
    '  "tech_stack": ["<str>", ...],\n'
    '  "qualifications": ["<str>", ...],\n'
    '  "experience_needed": "<str>",\n'
    '  "general_description": "<2-4 sentences>"\n'
    "}\n"
    "tech_stack: technologies, languages, frameworks, and tools explicitly mentioned.\n"
    "qualifications: required degrees, certifications, and hard skills.\n"
    "experience_needed: years and seniority level (e.g. '3-5 years, mid-level').\n"
    "general_description: plain-language summary of the role and day-to-day work.\n"
    "Return empty lists for list fields and empty string for string fields if not determinable."
)

LINKEDIN_PDF_SYSTEM_PROMPT = (
    "You are a professional profile data extractor. Given the text of a LinkedIn 'Save to PDF' export "
    "or any CV/resume PDF, respond ONLY with valid JSON matching exactly this schema — no markdown fences, no extra text.\n\n"
    "Schema:\n"
    "{\n"
    '  "profile_url": "<str — linkedin.com/in/... URL if found, else empty string>",\n'
    '  "full_name": "<str>",\n'
    '  "headline": "<str or null — job title or professional tagline>",\n'
    '  "location": "<str or null>",\n'
    '  "email": "<str or null>",\n'
    '  "phone": "<str or null>",\n'
    '  "about": "<str or null — Summary, Objective, or About section text>",\n'
    '  "experience": [\n'
    '    {"title": "<str>", "company": "<str>", "location": "<str or null>",\n'
    '     "start_date": "<str or null, e.g. Jan 2020>", "end_date": "<str or null, use Present if current>",\n'
    '     "is_current": <bool>, "description": "<str or null>", "employment_type": "<str or null>"}\n'
    '  ],\n'
    '  "education": [\n'
    '    {"school": "<str>", "degree": "<str or null>", "field_of_study": "<str or null>",\n'
    '     "start_year": "<str or null>", "end_year": "<str or null>", "description": "<str or null>"}\n'
    '  ],\n'
    '  "skills": [\n'
    '    {"skill_name": "<str>", "endorsement_count": <int, 0 if unknown>}\n'
    '  ],\n'
    '  "certifications": [\n'
    '    {"name": "<str>", "issuing_org": "<str or null>", "issue_date": "<str or null>"}\n'
    '  ],\n'
    '  "languages": [{"language": "<str>", "proficiency": "<str or null>"}],\n'
    '  "projects": [{"name": "<str>", "description": "<str or null>", "url": "<str or null>"}],\n'
    '  "honors": [{"title": "<str>", "issuer": "<str or null>", "date": "<str or null>"}],\n'
    '  "volunteer": [{"role": "<str>", "organization": "<str or null>", "cause": "<str or null>"}]\n'
    "}\n"
    "Rules:\n"
    "- Extract ONLY what is explicitly in the text. Use empty string for required str fields when not found.\n"
    "- Use null for all optional fields not present. Never hallucinate data.\n"
    "- Skills without endorsement counts: set endorsement_count to 0.\n"
    "- Experience: most recent first. is_current=true only if end_date is 'Present' or marked current.\n"
    "- Omit publications, recommendations, courses, test_scores, featured — leave them as empty lists.\n"
)

COMEET_JOB_EXTRACTION_SYSTEM_PROMPT = (
    "You are a job posting data extractor. Extract structured fields from the visible text of "
    "a Comeet job posting page and respond ONLY with valid JSON, no other text, no markdown code fences.\n"
    "Schema: {\n"
    '  "title": "<str — the job title>",\n'
    '  "company": "<str or null — company name if present>",\n'
    '  "location": "<str or null — city/country>",\n'
    '  "description": "<str or null — full job description text>",\n'
    '  "date_posted": "<YYYY-MM-DD or null>",\n'
    '  "salary_min": <float or null>,\n'
    '  "salary_max": <float or null>,\n'
    '  "salary_currency": "<str or null>",\n'
    '  "is_remote": <bool>,\n'
    '  "company_industry": "<str or null>",\n'
    '  "company_description": "<str or null — brief description of the company from the posting>"\n'
    "}\n"
    "Rules:\n"
    "- salary_min / salary_max: raw numeric values only (e.g. 80000.0), no symbols; null if not listed.\n"
    "- salary_currency: ISO code or symbol (e.g. 'USD', '$') when salary is present; null otherwise.\n"
    "- is_remote: true ONLY when the posting explicitly uses 'remote' language; false otherwise.\n"
    "- date_posted: ISO YYYY-MM-DD if a posting date appears; null if absent.\n"
    "- company: null if not determinable from the text.\n"
)


# ── Rate limiting (Groq only) ─────────────────────────────────────────────────

_last_llm_call: float = 0.0
_groq_min_interval: float = float(os.environ.get("GROQ_MIN_INTERVAL_SECONDS", "2.0"))


def _rate_limit() -> None:
    """Apply rate limiting for Groq. No-op when using Ollama or Vertex AI (no fixed inter-call delay needed)."""
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider in ("ollama", "vertexai"):
        return
    global _last_llm_call
    now = time.monotonic()
    elapsed = now - _last_llm_call
    if elapsed < _groq_min_interval:
        time.sleep(_groq_min_interval - elapsed)
    _last_llm_call = time.monotonic()


# ── Client / model factory ────────────────────────────────────────────────────

_vertex_client: Any = None


def _get_vertex_client() -> Any:
    """Lazy-init the google-genai client bound to Vertex AI."""
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client
    from google import genai  # lazy import so non-vertex deployments don't pay the cost

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT must be set when LLM_PROVIDER=vertexai")
    location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
    _vertex_client = genai.Client(vertexai=True, project=project, location=location)
    return _vertex_client


def _get_client() -> OpenAI:
    """Return an OpenAI-compatible client. Only valid for Groq/Ollama providers."""
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "ollama":
        return OpenAI(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",  # Ollama ignores this but OpenAI SDK requires a value
        )
    if provider == "vertexai":
        raise RuntimeError("_get_client() is not valid for vertexai; use _chat_complete()")
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    )


def _get_model(tier: str = "default") -> str:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "ollama":
        return os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
    if provider == "vertexai":
        if tier == "recommend":
            return os.environ.get("VERTEX_LLM_RECOMMEND_MODEL", "gemini-2.5-flash")
        return os.environ.get("VERTEX_LLM_FIT_MODEL", "gemini-2.5-flash-lite")
    if tier == "recommend":
        return os.environ.get("GROQ_RECOMMEND_MODEL", "llama-3.3-70b-versatile")
    return os.environ.get("GROQ_FIT_MODEL", "llama-3.1-8b-instant")


# ── Unified chat dispatcher (single seam for all public functions) ────────────

def _chat_complete(
    tier: str,
    system: str | None,
    user: str,
    max_tokens: int,
    *,
    temperature: float | None = None,
    json_mode: bool = True,
) -> str:
    """Issue a chat completion against the configured provider and return the raw text.

    Branches on LLM_PROVIDER: Vertex AI uses google-genai's generate_content; Groq/Ollama
    use the OpenAI-compatible chat.completions API. json_mode hints the model to emit
    application/json (Vertex only — OpenAI-path callers already strip code fences).
    """
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    model = _get_model(tier)
    if provider == "vertexai":
        client = _get_vertex_client()
        config: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system:
            config["system_instruction"] = system
        if json_mode:
            config["response_mime_type"] = "application/json"
        if temperature is not None:
            config["temperature"] = temperature
        response = client.models.generate_content(
            model=model,
            contents=user,
            config=config,
        )
        return response.text or ""

    client = _get_client()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_code_fence(content: str) -> str:
    s = content.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()


def _load_llm_json(content: str) -> Any:
    """Parse LLM JSON output, tolerating common malformations (invalid escapes, trailing commas, etc.)."""
    stripped = _strip_code_fence(content)
    if _HAS_JSON_REPAIR:
        return _json_repair_loads(stripped)
    return json.loads(stripped)


def _parse_json_response(content: str) -> dict[str, Any]:
    try:
        data = _load_llm_json(content)
        return {
            "fit_score": int(data["fit_score"]) if data.get("fit_score") is not None else None,
            "fit_summary": str(data.get("fit_summary") or "Scoring unavailable"),
            "salary_estimated": data.get("salary_estimated"),
        }
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse LLM fit response: %s", e)
        return dict(FIT_SAFE_FALLBACK)


def _parse_recommendations_response(content: str) -> list[str]:
    try:
        data = _load_llm_json(content)
        recs = data.get("recommendations") or []
        return [str(r) for r in recs if r]
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse LLM recommendations response: %s", e)
        return []


def _parse_linkedin_analysis_response(content: str) -> dict[str, Any]:
    try:
        data = _load_llm_json(content)
        sections = data.get("sections")
        if not isinstance(sections, list):
            raise ValueError("sections is not a list")
        for s in sections:
            if not isinstance(s.get("name"), str):
                raise ValueError("section missing name")
            if not isinstance(s.get("score"), int):
                raise ValueError("section score not int")
            if not isinstance(s.get("tasks"), list):
                raise ValueError("section tasks not list")
        overall = data.get("overall_score")
        if overall is not None:
            overall = int(overall)
        top = data.get("top_priority")
        if top is not None:
            top = str(top)
        return {"sections": sections, "overall_score": overall, "top_priority": top}
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Failed to parse LLM LinkedIn analysis response: %s", e)
        return dict(LINKEDIN_ANALYSIS_SAFE_FALLBACK)


def _format_listed_salary(job) -> Optional[str]:
    smin = getattr(job, "salary_min", None)
    smax = getattr(job, "salary_max", None)
    cur = getattr(job, "salary_currency", None) or "$"
    if smin and smax:
        return f"{cur}{int(smin):,} - {cur}{int(smax):,}"
    if smin:
        return f"{cur}{int(smin):,}+"
    return None


# ── Health check ──────────────────────────────────────────────────────────────

def check_llm_health() -> dict[str, Any]:
    """Send a tiny prompt to verify the LLM connection works.

    Returns {"ok": bool, "provider": str, "model": str, "error": str|None}.
    Never raises.
    """
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    model = _get_model()
    try:
        content = _chat_complete(
            tier="default",
            system=None,
            user="Reply with the word OK.",
            max_tokens=10,
            json_mode=False,
        ).strip()
        return {"ok": bool(content), "provider": provider, "model": model, "error": None}
    except Exception as e:
        logger.warning("LLM health check failed (%s): %s", provider, e)
        return {"ok": False, "provider": provider, "model": model, "error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

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
        _rate_limit()
        content = _chat_complete(
            tier="default",
            system=FIT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=512,
        )
        return _parse_json_response(content)
    except Exception as e:
        logger.error("LLM fit score call failed: %s", e)
        return dict(FIT_SAFE_FALLBACK)


def get_enhanced_fit_score(job, profile, jd_intelligence: dict | None = None) -> dict | None:
    """Return a FitScoreBreakdown dict or None on failure. Never raises."""
    from datetime import datetime, timezone

    from app.schemas import FitScoreBreakdown

    age_days: int | None = None
    ref_date = getattr(job, "scraped_at", None)
    if ref_date:
        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - ref_date).days

    listed = _format_listed_salary(job)
    salary_str = listed if listed else "not listed"

    parts = [
        "Candidate profile:",
        f"- Current title: {getattr(profile, 'current_title', None) or 'n/a'}",
        f"- Target title: {getattr(profile, 'target_title', None) or 'n/a'}",
        f"- Skills: {getattr(profile, 'skills', None) or 'n/a'}",
        f"- Years of experience: {getattr(profile, 'years_experience', None) or 'n/a'}",
        "",
        "Job:",
        f"- Title: {job.title}",
        f"- Company: {job.company}",
        f"- Location: {job.location or 'n/a'}",
        f"- Salary listed: {salary_str}",
        f"- Age: {age_days if age_days is not None else 'unknown'} days since scraped",
    ]

    if jd_intelligence:
        parts += [
            "",
            "JD Intelligence (structured):",
            f"- Required skills: {', '.join(jd_intelligence.get('required_skills', []))}",
            f"- Preferred skills: {', '.join(jd_intelligence.get('preferred_skills', []))}",
            f"- Seniority level: {jd_intelligence.get('seniority_level', 'n/a')}",
            f"- Remote policy: {jd_intelligence.get('remote_policy', 'n/a')}",
            f"- Tech stack: {', '.join(jd_intelligence.get('tech_stack', []))}",
            f"- Red flags: {', '.join(jd_intelligence.get('red_flags', []))}",
        ]
    else:
        parts += [
            "",
            f"Description (first 1500 chars): {(job.description or '')[:1500]}",
        ]

    user_prompt = "\n".join(parts)

    try:
        _rate_limit()
        content = _chat_complete(
            tier="default",
            system=ENHANCED_FIT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1500,
        )
        data = _load_llm_json(content)
        validated = FitScoreBreakdown.model_validate(data)
        return validated.model_dump()
    except Exception as e:
        logger.error("LLM enhanced fit score call failed: %s", e)
        return None


def get_linkedin_profile_analysis(profile) -> dict[str, Any]:
    """Analyze the user's LinkedIn profile across 8 sections and return structured improvement tasks.

    Returns: dict with sections, overall_score, top_priority — or LINKEDIN_ANALYSIS_SAFE_FALLBACK on error.
    """
    user_prompt = (
        f"LinkedIn URL: {getattr(profile, 'linkedin_url', None) or 'not provided'}\n"
        f"Current Title: {getattr(profile, 'current_title', None) or 'n/a'}\n"
        f"Target Title: {getattr(profile, 'target_title', None) or 'n/a'}\n"
        f"Years of Experience: {getattr(profile, 'years_experience', None) or 'n/a'}\n"
        f"Profile Content (skills/about): {getattr(profile, 'skills', None) or 'n/a'}"
    )
    try:
        _rate_limit()
        content = _chat_complete(
            tier="recommend",
            system=LINKEDIN_ANALYSIS_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2048,
        )
        return _parse_linkedin_analysis_response(content)
    except Exception as e:
        logger.error("LLM LinkedIn analysis call failed: %s", e)
        return dict(LINKEDIN_ANALYSIS_SAFE_FALLBACK)


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
        _rate_limit()
        content = _chat_complete(
            tier="recommend",
            system=RECOMMEND_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=512,
        )
        return _parse_recommendations_response(content)
    except Exception as e:
        logger.error("LLM recommendations call failed: %s", e)
        return []


def extract_job_intelligence(job) -> dict[str, Any] | None:
    """Extract structured intelligence from a job description via LLM.

    Returns a JobIntelligence-shaped dict on success, None on any failure.
    Never raises.
    """
    from app.schemas import JobIntelligence

    description = (job.description or "")[:3000]
    user_prompt = (
        f"Job Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location or 'n/a'}\n\n"
        f"Job Description:\n{description}"
    )

    try:
        _rate_limit()
        content = _chat_complete(
            tier="default",
            system=JOB_INTELLIGENCE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1024,
        )
        data = _load_llm_json(content)
        validated = JobIntelligence.model_validate(data)
        return validated.model_dump()
    except Exception as e:
        logger.error(
            "extract_job_intelligence failed for job %r at %r: %s",
            getattr(job, "title", "?"),
            getattr(job, "company", "?"),
            e,
        )
        return None


def parse_linkedin_profile_text(text: str) -> Optional[dict[str, Any]]:
    """Call LLM to extract LinkedInProfile JSON from raw PDF text. Returns dict or None on failure. Never raises."""
    user_prompt = f"LinkedIn PDF text:\n\n{text[:12000]}"
    try:
        _rate_limit()
        content = _chat_complete(
            tier="recommend",
            system=LINKEDIN_PDF_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
        )
        data = _load_llm_json(content)
        if not isinstance(data, dict):
            logger.warning("parse_linkedin_profile_text: LLM returned non-dict: %s", type(data))
            return None
        return data
    except Exception as exc:
        logger.error("parse_linkedin_profile_text failed: %s", exc)
        return None


def fetch_company_web_snippets(company_name: str) -> str | None:
    """Search the web for company snippets to ground LLM enrichment. Returns formatted string or None on any error."""
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(f'"{company_name}" company about', max_results=5)
        if not results:
            return None
        parts: list[str] = []
        total = 0
        for r in results:
            snippet = f"[{r.get('title', '')}] {r.get('body', '')}".strip()
            remaining = 1500 - total
            if remaining <= 0:
                break
            if len(snippet) > remaining:
                snippet = snippet[:remaining]
            parts.append(snippet)
            total += len(snippet)
        return "\n\n".join(parts) if parts else None
    except Exception as exc:
        logger.debug("fetch_company_web_snippets failed for %r: %s", company_name, exc)
        return None


def enrich_company(
    company_name: str,
    company_industry: Optional[str] = None,
    company_description: Optional[str] = None,
    job_description: Optional[str] = None,
) -> dict[str, Any] | None:
    """Enrich company info via LLM. Uses job description text as primary context; falls back to DDGS web snippets when absent. Returns {sector, company_type, what_they_do} or None. Never raises."""
    from app.schemas import CompanyEnrichment

    parts = [f"Company name: {company_name}"]
    if company_industry:
        parts.append(f"Industry: {company_industry}")
    if company_description:
        parts.append(f"Company description: {company_description[:500]}")

    _COMPANY_SECTION_MARKERS = (
        "who we are", "what we do", "about us", "about the company", "about the team",
        "our mission", "our vision", "we are a ", "we're a ", "we build", "we develop",
        "we help", "we provide", "we offer", "founded in", "our company",
    )
    desc_has_company = job_description and any(
        m in job_description.lower() for m in _COMPANY_SECTION_MARKERS
    )
    if desc_has_company:
        parts.append(f"\n<web_context>\n{job_description[:2000]}\n</web_context>")
        logger.debug("enrich_company: using job description for %r (%d chars)", company_name, len(job_description))
    else:
        if job_description:
            logger.debug("enrich_company: job description present but no company mention for %r — trying DDGS", company_name)
        snippets = fetch_company_web_snippets(company_name)
        if snippets:
            parts.append(f"\n<web_context>\n{snippets}\n</web_context>")
            logger.debug("enrich_company: web snippets fetched for %r (%d chars)", company_name, len(snippets))

    user_prompt = "\n".join(parts)

    try:
        _rate_limit()
        content = _chat_complete(
            tier="recommend",
            system=COMPANY_ENRICHMENT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=256,
        )
        data = _load_llm_json(content)
        if not isinstance(data, dict):
            logger.warning("enrich_company: LLM returned non-dict for %r: %r", company_name, content[:100])
            return None
        validated = CompanyEnrichment.model_validate(data)
        result = validated.model_dump()
        _apology_prefixes = (
            "i am sorry", "i'm sorry", "i cannot", "i could not", "i don't have",
            "i do not have", "no information", "unfortunately", "i was unable",
        )
        if result.get("what_they_do", "").lower().startswith(_apology_prefixes):
            result["what_they_do"] = ""
        return result
    except Exception as e:
        logger.error("enrich_company failed for %r: %s", company_name, e)
        return None


def extract_comeet_job_fields(page_text: str, url: str) -> dict[str, Any] | None:
    """Extract structured fields from a Comeet job page via LLM. Returns dict or None. Never raises."""
    from app.schemas import ComeetJobExtraction

    user_prompt = f"URL: {url}\n\nPage text:\n{page_text}"

    try:
        _rate_limit()
        content = _chat_complete(
            tier="default",
            system=COMEET_JOB_EXTRACTION_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1024,
        )
        data = _load_llm_json(content)
        validated = ComeetJobExtraction.model_validate(data)
        return validated.model_dump()
    except Exception as e:
        logger.warning("extract_comeet_job_fields failed for %r: %s", url, e)
        return None


def extract_job_summary(job) -> dict[str, Any] | None:
    """Extract structured job summary from description via LLM. Returns JobSummary-shaped dict or None. Never raises."""
    from app.schemas import JobSummary

    description = (job.description or "")[:3000]
    user_prompt = (
        f"Job Title: {job.title}\n"
        f"Company: {job.company}\n\n"
        f"Job Description:\n{description}"
    )

    try:
        _rate_limit()
        content = _chat_complete(
            tier="default",
            system=JOB_SUMMARY_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=512,
        )
        data = _load_llm_json(content)
        validated = JobSummary.model_validate(data)
        return validated.model_dump()
    except Exception as e:
        logger.error(
            "extract_job_summary failed for job %r at %r: %s",
            getattr(job, "title", "?"),
            getattr(job, "company", "?"),
            e,
        )
        return None
