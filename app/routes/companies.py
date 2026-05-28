import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.repository import JobRepository
from app.services.llm_service import enrich_company

logger = logging.getLogger(__name__)
router = APIRouter()


class ReEnrichBody(BaseModel):
    limit: Optional[int] = 20


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
                company_type=result.get("company_type"),
                what_they_do=result.get("what_they_do"),
            )
            enriched += 1
            logger.info("re_enrich_companies: enriched %r", company.name_display)
        else:
            failed += 1
            logger.warning("re_enrich_companies: failed for %r", company.name_display)
    return {"enriched": enriched, "failed": failed}
