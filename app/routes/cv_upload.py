"""Routes for uploading and managing LinkedIn PDF profiles (supports multiple files)."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.schemas.profile import (
    MultiUploadCVResponse,
    MultiUploadedCVStatusResponse,
    ProfileEducationItem,
    ProfileExperienceItem,
    ProposedProfileFields,
    UploadedFileResult,
)
from app.schemas_core import LinkedInExperience, LinkedInProfile
from app.services.cv_pdf_parser import merge_profiles, parse_pdf_to_profile

logger = logging.getLogger("app.routes")

router = APIRouter(prefix="/api/profile", tags=["api/profile"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_FILES = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_year_month(s: Optional[str]) -> Optional[tuple[int, int]]:
    if not s:
        return None
    s = s.strip()
    if s.lower() in ("present", "current", "now"):
        today = date.today()
        return (today.year, today.month)
    m = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', s, re.IGNORECASE)
    if m:
        month_map = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                     "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
        return (int(m.group(2)), month_map[m.group(1).lower()[:3]])
    m = re.search(r'(\d{4})', s)
    if m:
        return (int(m.group(1)), 1)
    return None


def _compute_years_experience(experience: list[LinkedInExperience]) -> Optional[int]:
    total_months = 0
    for exp in experience:
        start = _parse_year_month(exp.start_date)
        end_str = "present" if exp.is_current else exp.end_date
        end = _parse_year_month(end_str)
        if start and end:
            months = (end[0] - start[0]) * 12 + (end[1] - start[1])
            total_months += max(0, months)
    return max(1, total_months // 12) if total_months > 0 else None


def _year_to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return None


def _build_proposed_fields(profile: LinkedInProfile) -> ProposedProfileFields:
    url = profile.profile_url or None
    current_exp = next((e for e in profile.experience if e.is_current), None)
    if current_exp is None and profile.experience:
        current_exp = profile.experience[0]
    current_title = current_exp.title if current_exp else None

    sorted_skills = sorted(profile.skills, key=lambda s: s.endorsement_count, reverse=True)
    skills_str = ", ".join(s.skill_name for s in sorted_skills[:20]) if sorted_skills else None

    experiences = [
        ProfileExperienceItem(
            title=exp.title or None,
            company=exp.company or None,
            location=exp.location,
            start_date=exp.start_date,
            end_date=exp.end_date,
            is_current=exp.is_current,
            description=exp.description,
        )
        for exp in profile.experience
    ] or None

    educations = [
        ProfileEducationItem(
            school=edu.school or None,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            start_year=_year_to_int(edu.start_year),
            end_year=_year_to_int(edu.end_year),
            grade=edu.grade,
            description=edu.description,
        )
        for edu in profile.education
    ] or None

    return ProposedProfileFields(
        linkedin_url=url,
        current_title=current_title,
        skills=skills_str,
        target_title=None,
        years_experience=_compute_years_experience(profile.experience),
        experiences=experiences,
        educations=educations,
    )


def _record_to_file_result(record, profile: LinkedInProfile) -> UploadedFileResult:
    return UploadedFileResult(
        id=record.id,
        uploaded_at=record.uploaded_at,
        original_filename=record.original_filename,
        parsed=profile,
        proposed=_build_proposed_fields(profile),
    )


def _load_all_file_results(repo: JobRepository) -> tuple[list[UploadedFileResult], list[LinkedInProfile]]:
    records = repo.get_all_uploaded_cvs()
    file_results: list[UploadedFileResult] = []
    profiles: list[LinkedInProfile] = []
    for record in records:
        try:
            profile = LinkedInProfile.model_validate(json.loads(record.parsed_json))
            file_results.append(_record_to_file_result(record, profile))
            profiles.append(profile)
        except Exception as exc:
            logger.warning("Could not deserialize stored CV JSON for id=%d: %s", record.id, exc)
    return file_results, profiles


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/cv-upload", response_model=MultiUploadCVResponse)
async def upload_cv(files: list[UploadFile] = File(...), db: Session = Depends(get_session)):
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "groq" and not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="LLM credentials not configured — set GROQ_API_KEY in .env")

    if len(files) > _MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Too many files — maximum {_MAX_FILES} PDFs per upload")

    repo = JobRepository(db)
    errors: list[dict] = []
    upload_dir = "data/uploads/cv"
    os.makedirs(upload_dir, exist_ok=True)

    for file in files:
        if file.content_type != "application/pdf":
            errors.append({"filename": file.filename or "unknown", "message": "Only PDF files are accepted"})
            continue

        file_bytes = await file.read()
        if len(file_bytes) > _MAX_FILE_SIZE:
            errors.append({"filename": file.filename or "unknown", "message": "File exceeds 10 MB limit"})
            continue

        try:
            profile = parse_pdf_to_profile(file_bytes)
        except ValueError as exc:
            errors.append({"filename": file.filename or "unknown", "message": str(exc)})
            continue
        except Exception as exc:
            logger.error("PDF parsing failed for %s: %s", file.filename, exc)
            errors.append({"filename": file.filename or "unknown", "message": "Could not parse profile content — try re-uploading"})
            continue

        file_path = f"{upload_dir}/{uuid.uuid4()}.pdf"
        with open(file_path, "wb") as fh:
            fh.write(file_bytes)

        repo.save_uploaded_cv(
            file_path=file_path,
            original_filename=file.filename or "upload.pdf",
            parsed_json=profile.model_dump_json(),
        )

    all_files, all_profiles = _load_all_file_results(repo)

    if not all_files:
        msg = errors[0]["message"] if errors else "No files could be processed"
        raise HTTPException(status_code=422, detail=msg)

    merged_profile = merge_profiles(all_profiles) if len(all_profiles) > 1 else all_profiles[0]

    return MultiUploadCVResponse(
        files=all_files,
        merged=_build_proposed_fields(merged_profile),
        errors=errors,
    )


@router.post("/cv-extract", response_model=MultiUploadCVResponse)
def extract_from_uploaded_cvs(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    all_files, all_profiles = _load_all_file_results(repo)
    if not all_files:
        raise HTTPException(status_code=422, detail="No uploaded CVs found — please upload a CV or LinkedIn PDF first")
    merged_profile = merge_profiles(all_profiles) if len(all_profiles) > 1 else all_profiles[0]
    return MultiUploadCVResponse(
        files=all_files,
        merged=_build_proposed_fields(merged_profile),
        errors=[],
    )


@router.get("/cv-upload", response_model=MultiUploadedCVStatusResponse)
def get_cv_upload_status(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    all_files, all_profiles = _load_all_file_results(repo)
    if not all_files:
        return MultiUploadedCVStatusResponse(files=[], merged=None)
    merged_profile = merge_profiles(all_profiles) if len(all_profiles) > 1 else all_profiles[0]
    return MultiUploadedCVStatusResponse(
        files=all_files,
        merged=_build_proposed_fields(merged_profile),
    )


@router.delete("/cv-upload/{cv_id}", status_code=204)
def delete_cv_upload_by_id(cv_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    record = repo.get_uploaded_cv_by_id(cv_id)
    if not record:
        return
    try:
        if os.path.exists(record.file_path):
            os.remove(record.file_path)
    except Exception as exc:
        logger.warning("Could not delete CV file %s: %s", record.file_path, exc)
    repo.delete_uploaded_cv_by_id(cv_id)


@router.delete("/cv-upload", status_code=204)
def delete_all_cv_uploads(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    records = repo.get_all_uploaded_cvs()
    for record in records:
        try:
            if os.path.exists(record.file_path):
                os.remove(record.file_path)
        except Exception as exc:
            logger.warning("Could not delete CV file %s: %s", record.file_path, exc)
        repo.delete_uploaded_cv_by_id(record.id)
