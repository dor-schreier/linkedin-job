import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.sectors import SECTOR_CATEGORIES
from app.services.llm_service import enrich_company

logger = logging.getLogger(__name__)
router = APIRouter()


class ReEnrichBody(BaseModel):
    limit: Optional[int] = 20


class CompanySectorUpdate(BaseModel):
    sector: Optional[str] = None
    subsector: Optional[str] = None

    @field_validator("sector")
    @classmethod
    def sector_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in SECTOR_CATEGORIES:
            raise ValueError(f"sector must be one of the 14 taxonomy categories")
        return v or None


@router.get("/companies/overview")
def companies_overview(session: Session = Depends(get_session)):
    repo = JobRepository(session)
    return repo.get_companies_with_active_jobs()


@router.get("/companies/sectors")
def get_sectors(session: Session = Depends(get_session)):
    repo = JobRepository(session)
    return {"sectors": SECTOR_CATEGORIES, "subsectors": repo.get_distinct_subsectors()}


@router.patch("/companies/{company_id}")
def update_company_sector(
    company_id: int,
    body: CompanySectorUpdate,
    session: Session = Depends(get_session),
):
    repo = JobRepository(session)
    company = repo.update_company_sector(company_id, body.sector, body.subsector)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    logger.info("update_company_sector: id=%d sector=%r subsector=%r", company_id, body.sector, body.subsector)
    return {
        "id": company.id,
        "name_display": company.name_display,
        "sector": company.sector,
        "subsector": company.subsector,
    }


@router.post("/companies/re-enrich")
def re_enrich_companies(body: ReEnrichBody = ReEnrichBody(), session: Session = Depends(get_session)):
    repo = JobRepository(session)
    companies = repo.get_companies_for_reenrichment(limit=body.limit or 20)
    enriched = 0
    failed = 0
    for company in companies:
        result = enrich_company(company.name_display)
        if result:
            repo.upsert_company(
                name_normalized=company.name_normalized,
                name_display=company.name_display,
                sector=result.get("sector"),
                subsector=result.get("subsector"),
                company_type=result.get("company_type"),
                what_they_do=result.get("what_they_do"),
            )
            enriched += 1
            logger.info("re_enrich_companies: enriched %r", company.name_display)
        else:
            failed += 1
            logger.warning("re_enrich_companies: failed for %r", company.name_display)
    return {"enriched": enriched, "failed": failed}
