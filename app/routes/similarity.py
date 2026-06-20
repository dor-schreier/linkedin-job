from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository

router = APIRouter()


def _weights_to_dict(w) -> dict:
    return {
        "weight_title": w.weight_title,
        "weight_skills": w.weight_skills,
        "weight_seniority": w.weight_seniority,
        "weight_sector": w.weight_sector,
        "is_enabled": w.is_enabled,
        "min_score_threshold": w.min_score_threshold,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


@router.get("/similarity/weights", tags=["similarity"])
def get_similarity_weights(db: Session = Depends(get_session)):
    repo = JobRepository(db)
    return JSONResponse(_weights_to_dict(repo.get_similarity_weights()))


class WeightsUpdate(BaseModel):
    weight_title: Optional[float] = None
    weight_skills: Optional[float] = None
    weight_seniority: Optional[float] = None
    weight_sector: Optional[float] = None
    is_enabled: Optional[bool] = None
    min_score_threshold: Optional[int] = None


@router.put("/similarity/weights", tags=["similarity"])
def update_similarity_weights(body: WeightsUpdate, db: Session = Depends(get_session)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    repo = JobRepository(db)
    weights = repo.update_similarity_weights(**fields)
    return JSONResponse(_weights_to_dict(weights))


@router.get("/similarity/targets", tags=["similarity"])
def get_target_jobs(db: Session = Depends(get_session)):
    from app.routes.jobs import _job_to_response_dict
    repo = JobRepository(db)
    targets = repo.list_target_jobs()
    return JSONResponse([_job_to_response_dict(j) for j in targets])


@router.post("/similarity/recompute", tags=["similarity"])
def recompute_similarity(db: Session = Depends(get_session)):
    from app.services.similarity_service import recompute_all
    count = recompute_all(db)
    return JSONResponse({"updated": count})
