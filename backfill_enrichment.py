#!/usr/bin/env python3
"""One-shot backfill: enriches existing jobs with job summaries and company profiles.

Run once after deploying the added-info feature:
    python backfill_enrichment.py

Both operations are idempotent — already-enriched jobs/companies are skipped.
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.database import SessionLocal, init_db
    init_db()

    from app.models import Job
    from app.repository import JobRepository
    from app.services.llm_service import enrich_company, extract_job_summary

    with SessionLocal() as session:
        repo = JobRepository(session)

        # ── 1. Job summaries ────────────────────────────────────────────────
        jobs_needing_summary = (
            session.query(Job)
            .filter(Job.summary_generated_at.is_(None))
            .filter(Job.description.isnot(None))
            .all()
        )
        logger.info("Jobs needing summary: %d", len(jobs_needing_summary))

        for i, job in enumerate(jobs_needing_summary, 1):
            logger.info("[%d/%d] Summarising: %s @ %s", i, len(jobs_needing_summary), job.title, job.company)
            result = extract_job_summary(job)
            if result:
                repo.update_job_summary(
                    job_id=job.id,
                    tech_stack_json=json.dumps(result.get("tech_stack", [])),
                    qualifications_json=json.dumps(result.get("qualifications", [])),
                    experience_needed=result.get("experience_needed"),
                    general_description=result.get("general_description"),
                )
                logger.info("  ✓ done")
            else:
                logger.warning("  ✗ failed")

        # ── 2. Company enrichment ────────────────────────────────────────────
        jobs_without_company = (
            session.query(Job)
            .filter(Job.company_id.is_(None))
            .all()
        )
        unique_names = list({j.company for j in jobs_without_company if j.company})
        logger.info("Unique companies needing enrichment: %d", len(unique_names))

        for i, name in enumerate(unique_names, 1):
            name_norm = name.strip().lower()
            logger.info("[%d/%d] Enriching: %s", i, len(unique_names), name)

            co = repo.get_company_by_normalized_name(name_norm)
            if co is None:
                enrichment = enrich_company(company_name=name)
                if enrichment:
                    co = repo.upsert_company(
                        name_normalized=name_norm,
                        name_display=name,
                        sector=enrichment.get("sector"),
                        company_type=enrichment.get("company_type"),
                        what_they_do=enrichment.get("what_they_do"),
                    )
                    logger.info("  ✓ %s / %s", enrichment.get("sector"), enrichment.get("company_type"))
                else:
                    logger.warning("  ✗ enrichment failed")
            else:
                logger.info("  ↩ already in DB")

            if co:
                for job in jobs_without_company:
                    if job.company and job.company.strip().lower() == name_norm:
                        job.company_id = co.id
                session.commit()

    logger.info("Backfill complete.")


if __name__ == "__main__":
    main()
