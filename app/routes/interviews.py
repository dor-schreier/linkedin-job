"""Interview CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Interview, InterviewMedium, InterviewType, Job, JobStatus
from app.repository import JobRepository
from app.schemas.interviews import InterviewCreate, InterviewUpdate

router = APIRouter()

VALID_INTERVIEW_TYPES = {e.value for e in InterviewType}
VALID_MEDIUMS = {e.value for e in InterviewMedium}


def _interview_to_dict(iv) -> dict:
    return {
        "id": iv.id,
        "job_id": iv.job_id,
        "scheduled_at": iv.scheduled_at.isoformat() if iv.scheduled_at else None,
        "interview_type": iv.interview_type.value if hasattr(iv.interview_type, 'value') else iv.interview_type,
        "medium": iv.medium.value if hasattr(iv.medium, 'value') else iv.medium,
        "location": iv.location,
        "notes": iv.notes,
        "created_at": iv.created_at.isoformat() if iv.created_at else None,
    }


@router.get("/jobs/{job_id}/interviews", tags=["interviews"])
def list_interviews(job_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    interviews = repo.list_interviews_for_job(job_id)
    return JSONResponse([_interview_to_dict(iv) for iv in interviews])


@router.post("/jobs/{job_id}/interviews", tags=["interviews"], status_code=201)
def create_interview(job_id: int, body: InterviewCreate, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    job = repo.session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if body.interview_type not in VALID_INTERVIEW_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid interview_type: {body.interview_type}")
    if body.medium not in VALID_MEDIUMS:
        raise HTTPException(status_code=422, detail=f"Invalid medium: {body.medium}")

    iv_type = InterviewType(body.interview_type)
    medium = InterviewMedium(body.medium)

    interview = repo.create_interview(
        job_id=job_id,
        scheduled_at=body.scheduled_at.replace(tzinfo=None),  # store naive UTC
        interview_type=iv_type,
        medium=medium,
        location=body.location,
        notes=body.notes,
    )

    # Auto-promote applied → interviewing
    if job.status == JobStatus.APPLIED:
        job.status = JobStatus.INTERVIEWING
        repo.session.commit()

    return JSONResponse(_interview_to_dict(interview), status_code=201)


@router.patch("/interviews/{interview_id}", tags=["interviews"])
def update_interview(interview_id: int, body: InterviewUpdate, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    if not repo.get_interview(interview_id):
        raise HTTPException(status_code=404, detail="Interview not found")

    kwargs = {}
    if body.scheduled_at is not None:
        kwargs['scheduled_at'] = body.scheduled_at.replace(tzinfo=None)
    if body.interview_type is not None:
        if body.interview_type not in VALID_INTERVIEW_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid interview_type: {body.interview_type}")
        kwargs['interview_type'] = InterviewType(body.interview_type)
    if body.medium is not None:
        if body.medium not in VALID_MEDIUMS:
            raise HTTPException(status_code=422, detail=f"Invalid medium: {body.medium}")
        kwargs['medium'] = InterviewMedium(body.medium)
    if body.location is not None:
        kwargs['location'] = body.location
    if body.notes is not None:
        kwargs['notes'] = body.notes

    interview = repo.update_interview(interview_id, **kwargs)
    return JSONResponse(_interview_to_dict(interview))


@router.delete("/interviews/{interview_id}", status_code=204, tags=["interviews"])
def delete_interview(interview_id: int, db: Session = Depends(get_session)):
    repo = JobRepository(db)
    if not repo.delete_interview(interview_id):
        raise HTTPException(status_code=404, detail="Interview not found")
    return Response(status_code=204)


