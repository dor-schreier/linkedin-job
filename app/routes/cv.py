"""CV router — tailored CV generation, download, and management per job."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.schemas.cv import TailoredCVResponse
from app.schemas_core import CVData
from app.services.cv_renderer import render_tailored_docx, render_tailored_pdf
from app.services.cv_tailoring import tailor_cv

logger = logging.getLogger("app.routes")

router = APIRouter(prefix="/api/jobs", tags=["api/jobs/cv"])

_TAILORED_DIR = "data/uploads/tailored_cv"


def _sanitize_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return text or "cv"


def _atomic_write_bytes(path: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp_cv_", dir=dir_)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def _profile_has_content(profile) -> bool:
    if profile is None:
        return False
    fields = [profile.skills, profile.current_title, profile.target_title, profile.linkedin_url]
    return any(bool(f and str(f).strip()) for f in fields)


def _record_to_response(record, cv: CVData) -> TailoredCVResponse:
    return TailoredCVResponse(
        job_id=record.job_id,
        generated_at=record.generated_at,
        pdf_url=f"/api/jobs/{record.job_id}/cv/pdf",
        docx_url=f"/api/jobs/{record.job_id}/cv/docx",
        model_used=record.model_used,
        cv=cv,
    )


@router.post("/{job_id}/cv/generate", response_model=TailoredCVResponse)
def generate_tailored_cv(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = repo.get_profile()
    uploaded = repo.get_latest_uploaded_cv()
    if not _profile_has_content(profile) and not uploaded:
        raise HTTPException(
            status_code=422,
            detail="Add profile content or upload a LinkedIn PDF on the Profile page first",
        )

    try:
        cv, model_used = tailor_cv(profile, uploaded, job)
    except RuntimeError as exc:
        logger.error("Tailoring failed for job %s: %s", job_id, exc)
        raise HTTPException(status_code=502, detail=f"LLM tailoring failed: {exc}")

    try:
        pdf_bytes = render_tailored_pdf(cv)
        docx_bytes = render_tailored_docx(cv)
    except Exception as exc:
        logger.error("Rendering failed for job %s: %s", job_id, exc)
        raise HTTPException(status_code=502, detail=f"CV rendering failed: {exc}")

    pdf_path = os.path.join(_TAILORED_DIR, f"{job_id}.pdf")
    docx_path = os.path.join(_TAILORED_DIR, f"{job_id}.docx")
    _atomic_write_bytes(pdf_path, pdf_bytes)
    _atomic_write_bytes(docx_path, docx_bytes)

    record = repo.upsert_tailored_cv(
        job_id=job_id,
        cv_json=cv.model_dump_json(),
        pdf_path=pdf_path,
        docx_path=docx_path,
        model_used=model_used,
    )
    return _record_to_response(record, cv)


@router.get("/{job_id}/cv", response_model=TailoredCVResponse)
def get_tailored_cv(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    record = repo.get_tailored_cv(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="No tailored CV generated for this job")
    try:
        cv = CVData.model_validate(json.loads(record.cv_json))
    except Exception as exc:
        logger.warning("Stored tailored CV JSON unparseable for job %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Stored CV is corrupted; regenerate")
    return _record_to_response(record, cv)


def _download(job_id: int, kind: str, repo: JobRepository) -> FileResponse:
    record = repo.get_tailored_cv(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="No tailored CV generated for this job")
    path = record.pdf_path if kind == "pdf" else record.docx_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{kind.upper()} file missing — regenerate")
    job = repo.get_job(job_id)
    company = _sanitize_filename(job.company if job else "")
    title = _sanitize_filename(job.title if job else "")
    fname = f"{company}_{title}_CV.{kind}" if (company or title) else f"job_{job_id}_CV.{kind}"
    media = "application/pdf" if kind == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media, filename=fname)


@router.get("/{job_id}/cv/pdf")
def download_tailored_pdf(job_id: int, db: Session = Depends(get_session)):
    return _download(job_id, "pdf", JobRepository(db))


@router.get("/{job_id}/cv/docx")
def download_tailored_docx(job_id: int, db: Session = Depends(get_session)):
    return _download(job_id, "docx", JobRepository(db))


@router.delete("/{job_id}/cv", status_code=204)
def delete_tailored_cv(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    repo.delete_tailored_cv(job_id)
    return Response(status_code=204)
