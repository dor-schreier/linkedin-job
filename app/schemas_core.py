"""Pydantic models for AI analysis pipeline data structures."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator

from app.sectors import SECTOR_CATEGORIES


# ── LinkedIn Profile Schema ───────────────────────────────────────────────────


class LinkedInExperience(BaseModel):
    title: str = ""
    company: str = ""
    company_url: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    employment_type: Optional[str] = None


class LinkedInEducation(BaseModel):
    school: str = ""
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    grade: Optional[str] = None
    activities: Optional[str] = None
    description: Optional[str] = None


class LinkedInSkill(BaseModel):
    skill_name: str = ""
    endorsement_count: int = 0


class LinkedInCertification(BaseModel):
    name: str = ""
    issuing_org: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None


class LinkedInLanguage(BaseModel):
    language: str = ""
    proficiency: Optional[str] = None


class LinkedInProject(BaseModel):
    name: str = ""
    description: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    associated_with: Optional[str] = None


class LinkedInPublication(BaseModel):
    title: str = ""
    publisher: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class LinkedInHonor(BaseModel):
    title: str = ""
    issuer: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None


class LinkedInVolunteer(BaseModel):
    role: str = ""
    organization: Optional[str] = None
    cause: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class LinkedInRecommendation(BaseModel):
    recommender_name: str = ""
    recommender_title: Optional[str] = None
    date: Optional[str] = None
    text: Optional[str] = None


class LinkedInCourse(BaseModel):
    name: str = ""
    number: Optional[str] = None
    associated_with: Optional[str] = None


class LinkedInTestScore(BaseModel):
    name: str = ""
    score: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = None


class LinkedInFeatured(BaseModel):
    title: str = ""
    subtitle: Optional[str] = None
    url: Optional[str] = None
    media_type: Optional[str] = None


class LinkedInProfile(BaseModel):
    """All extractable fields from a LinkedIn profile page."""

    profile_url: str = ""
    full_name: str = ""
    headline: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_picture_url: Optional[str] = None
    about: Optional[str] = None
    connections_count: Optional[int] = None
    follower_count: Optional[int] = None

    experience: list[LinkedInExperience] = []
    education: list[LinkedInEducation] = []
    skills: list[LinkedInSkill] = []
    certifications: list[LinkedInCertification] = []
    languages: list[LinkedInLanguage] = []
    projects: list[LinkedInProject] = []
    publications: list[LinkedInPublication] = []
    honors: list[LinkedInHonor] = []
    volunteer: list[LinkedInVolunteer] = []
    recommendations: list[LinkedInRecommendation] = []
    courses: list[LinkedInCourse] = []
    test_scores: list[LinkedInTestScore] = []
    featured: list[LinkedInFeatured] = []


# ── CV Schema ─────────────────────────────────────────────────────────────────


class CVMeta(BaseModel):
    generated_at: str = ""
    source_url: str = ""
    template_name: str = "default"
    language: str = "en"


class CVData(BaseModel):
    """Renderer-agnostic CV schema built from a LinkedInProfile."""

    cv_meta: CVMeta

    full_name: str = ""
    headline: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_url: Optional[str] = None
    about: Optional[str] = None

    experience: list[LinkedInExperience] = []
    education: list[LinkedInEducation] = []
    skills: list[LinkedInSkill] = []
    certifications: list[LinkedInCertification] = []
    languages: list[LinkedInLanguage] = []
    projects: list[LinkedInProject] = []
    publications: list[LinkedInPublication] = []
    honors: list[LinkedInHonor] = []
    volunteer: list[LinkedInVolunteer] = []

    # Optional tailoring fields populated by cv_tailoring service
    tailored_for_job_id: Optional[int] = None
    tailored_summary: Optional[str] = None
    prioritized_skills: list[str] = []


class JobIntelligence(BaseModel):
    """Structured fields extracted from a raw job description via Groq."""

    required_skills: list[str]
    preferred_skills: list[str]
    seniority_level: Optional[str] = None
    remote_policy: Optional[str] = None  # onsite / hybrid / remote
    tech_stack: list[str]
    team_size_signals: Optional[str] = None
    salary_signals: Optional[str] = None
    red_flags: list[str]


class KeywordGap(BaseModel):
    """A keyword found in job intelligence data, with profile coverage info."""

    keyword: str
    count: int
    frequency_pct: float  # % of matched jobs containing this keyword
    in_profile: bool


class JobSummary(BaseModel):
    """AI-extracted structured summary of a job posting."""

    tech_stack: list[str]
    qualifications: list[str]
    experience_needed: str = ""
    general_description: str = ""


class CompanyEnrichment(BaseModel):
    """AI-generated company profile."""

    sector: str = ""
    subsector: Optional[str] = None
    company_type: str = "unknown"
    what_they_do: str = ""

    @field_validator("sector")
    @classmethod
    def sector_must_be_valid(cls, v: str) -> str:
        if v and v not in SECTOR_CATEGORIES:
            return ""
        return v


class FitScoreBreakdown(BaseModel):
    """Structured fit scoring result returned by the enhanced scoring prompt."""

    overall_score: int  # 0-100
    matching_qualifications: list[str]
    missing_qualifications: list[str]
    experience_alignment: str  # seniority match assessment
    red_flags: list[str]
    application_priority: str  # High / Medium / Low
    summary: str  # 2-3 sentence recommendation
    job_summary: Optional[JobSummary] = None  # co-extracted during scoring


class ComeetJobExtraction(BaseModel):
    """Fields extracted from a Comeet job-post page via LLM."""

    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    date_posted: Optional[str] = None  # ISO YYYY-MM-DD
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    is_remote: bool = False
    company_industry: Optional[str] = None
    company_description: Optional[str] = None
