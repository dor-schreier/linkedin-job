"""Smoke-test the Vertex AI LLM backend end-to-end.

Forces LLM_PROVIDER=vertexai, builds a synthetic Job + Profile, and calls
check_llm_health() and get_fit_score_and_salary(). Requires GOOGLE_CLOUD_PROJECT
and ADC (or GOOGLE_APPLICATION_CREDENTIALS) to be set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()
os.environ["LLM_PROVIDER"] = "vertexai"

from app.services.llm_service import check_llm_health, get_fit_score_and_salary

print("== check_llm_health ==")
print(check_llm_health())

job = SimpleNamespace(
    title="Senior Backend Engineer",
    company="Acme Corp",
    location="Remote (US)",
    description=(
        "We are looking for a senior backend engineer with strong Python and "
        "distributed systems experience. Familiarity with FastAPI, PostgreSQL, "
        "and GCP a plus. 5+ years of experience required."
    ),
    salary_min=None,
    salary_max=None,
    salary_currency=None,
)

profile = SimpleNamespace(
    current_title="Backend Engineer",
    target_title="Senior Backend Engineer",
    skills="Python, FastAPI, PostgreSQL, Docker, GCP",
    years_experience=6,
)

print("\n== get_fit_score_and_salary ==")
print(get_fit_score_and_salary(job, profile))
