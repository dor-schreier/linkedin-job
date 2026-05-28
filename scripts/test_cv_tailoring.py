"""Integration test for cv_tailoring steps 1 (input assembly) and 2 (real LLM call).

Runs against the live SQLite DB and the configured LLM provider (.env).
No mocks. Pulls a real Profile, UploadedCV, and Job row.

Usage:
    python scripts/test_cv_tailoring.py [JOB_ID]

If JOB_ID is omitted, the script picks the most recent job that has
intelligence_json populated.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from textwrap import shorten

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.database import SessionLocal
from app.models import Job
from app.repository import JobRepository
import app.services.cv_tailoring as _cv_tailoring_mod
from app.services.cv_tailoring import build_tailoring_inputs, tailor_cv
from app.services import llm_service as _llm_svc


def pick_job(session, job_id):
    if job_id is not None:
        job = session.get(Job, job_id)
        if not job:
            print(f"ERROR: Job {job_id} not found")
            sys.exit(1)
        return job
    job = (
        session.query(Job)
        .filter(Job.intelligence_json.isnot(None))
        .order_by(Job.id.desc())
        .first()
    )
    if not job:
        print("ERROR: No jobs with intelligence_json. Run a scrape first.")
        sys.exit(1)
    return job


def main():
    job_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    session = SessionLocal()
    try:
        repo = JobRepository(session)
        job = pick_job(session, job_id)
        profile = repo.get_profile()
        uploaded = repo.get_latest_uploaded_cv()

        print(f"\n== Inputs == job_id={job.id} '{job.title}' @ {job.company}")
        print(f"  profile: {'present' if profile else 'MISSING'}")
        print(f"  uploaded CV: {uploaded.original_filename if uploaded else 'MISSING'}")
        print(f"  intelligence_json: {'present' if job.intelligence_json else 'MISSING'}")

        if not profile and not uploaded:
            print("ERROR: need a Profile or UploadedCV to tailor a CV.")
            sys.exit(1)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print("\n== STEP 1 — build_tailoring_inputs ==")
        inputs = build_tailoring_inputs(profile, uploaded, job)
        candidate = inputs["candidate"]
        job_ctx = inputs["job"]
        linkedin = inputs["linkedin"]

        print(f"  candidate.full_name: {candidate.get('full_name')!r}")
        print(f"  candidate.experience count: {len(candidate.get('experience') or [])}")
        print(f"  candidate.skills count: {len(candidate.get('skills') or [])}")
        print(f"  job.description len: {len(job_ctx['description'])} (cap 6000)")
        print(f"  job.intelligence.required_skills: {job_ctx['intelligence'].get('required_skills')}")
        print(f"  job.intelligence.tech_stack: {job_ctx['intelligence'].get('tech_stack')}")
        print(f"  linkedin parsed: {linkedin is not None}")

        assert len(job_ctx["description"]) <= 6000, "description not truncated"
        assert isinstance(job_ctx["intelligence"].get("required_skills"), list)

        # ── Step 2 ────────────────────────────────────────────────────────────
        print(f"\n== STEP 2 — tailor_cv (real LLM, provider={os.getenv('LLM_PROVIDER', 'default')}) ==")
        print("  Calling LLM... may take 10–60s.")

        _raw_response: list[str] = []
        _original_chat_complete = _llm_svc._chat_complete

        def _intercepting_chat_complete(tier, system, user, max_tokens, **kwargs):
            print("\n---- OUTGOING SYSTEM PROMPT ----")
            print(system)
            print("\n---- OUTGOING USER PROMPT ----")
            print(user)
            print("---- END OF PROMPT ----\n")
            raw = _original_chat_complete(tier=tier, system=system, user=user, max_tokens=max_tokens, **kwargs)
            _raw_response.append(raw)
            print("\n---- INCOMING RAW LLM RESPONSE ----")
            print(raw)
            print("---- END OF RESPONSE ----\n")
            return raw

        _cv_tailoring_mod._chat_complete = _intercepting_chat_complete
        try:
            cv, model = tailor_cv(profile, uploaded, job)
        finally:
            _cv_tailoring_mod._chat_complete = _original_chat_complete

        if _raw_response:
            print("\n---- PARSED OUTPUT JSON (pretty) ----")
            try:
                from app.services.llm_service import _load_llm_json
                parsed = _load_llm_json(_raw_response[0])
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"  (could not pretty-print JSON: {e})")
            print("---- END OF JSON ----\n")

        print(f"\n  model_used: {model}")
        print(f"  full_name: {cv.full_name!r}")
        print(f"  headline: {cv.headline!r}")
        print(f"  email: {cv.email!r}")
        print(f"  tailored_for_job_id: {cv.tailored_for_job_id}")
        print(f"  tailored_summary: {shorten(cv.tailored_summary or '', 220)}")
        print(f"  prioritized_skills ({len(cv.prioritized_skills)}): {cv.prioritized_skills}")
        print(f"  experience entries: {len(cv.experience)}")
        for i, exp in enumerate(cv.experience[:3], 1):
            end = "present" if exp.is_current else (exp.end_date or "")
            print(f"    [{i}] {exp.title} @ {exp.company} ({exp.start_date} → {end})")
            for line in (exp.description or "").splitlines()[:3]:
                line = line.strip()
                if line:
                    print(f"        {line}")
        print(f"  education: {len(cv.education)} | certifications: {len(cv.certifications)} | projects: {len(cv.projects)}")

        assert cv.tailored_for_job_id == job.id, "tailored_for_job_id mismatch"
        assert cv.cv_meta.template_name == "tailored", "template_name should be 'tailored'"
        assert 0 < len(cv.prioritized_skills) <= 12, f"prioritized_skills out of bounds ({len(cv.prioritized_skills)})"
        assert cv.tailored_summary, "tailored_summary is empty"
        assert len(cv.experience) >= 1, "no experience returned"
        if linkedin:
            assert cv.full_name == linkedin.full_name, "identity should come from LinkedIn upload, not LLM"

        print("\nOK — all assertions passed.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
