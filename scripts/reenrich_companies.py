"""
Re-enrich all Company records in the DB using the LLM.

Context priority per company:
  1. Job description from a linked job (most specific, no API call needed)
  2. DDGS web snippets (fallback when no job is linked)
  3. LLM training knowledge (always present)

Uses VERTEX_LLM_RECOMMEND_MODEL (or equivalent per provider).

Usage:
    python scripts/reenrich_companies.py              # enrich all companies
    python scripts/reenrich_companies.py --limit 20   # stop after 20
    python scripts/reenrich_companies.py --dry-run    # show what would change, no writes
"""
import argparse
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Show app-level errors on stderr; suppress noisy third-party libraries
logging.basicConfig(level=logging.CRITICAL)
for _lg in ("app.services.llm_service", "app.services"):
    _h = logging.StreamHandler(sys.stderr)
    _h.setLevel(logging.DEBUG)
    logging.getLogger(_lg).setLevel(logging.DEBUG)
    logging.getLogger(_lg).addHandler(_h)

from app.database import SessionLocal, init_db
from app.models import Company, Job
from app.repository import JobRepository
from app.services import llm_service as _llm
from app.services.llm_service import enrich_company


def _enrich_verbose(company_name: str, job_description) -> dict | None:
    """Call enrich_company but print the traceback on failure."""
    try:
        return enrich_company(company_name=company_name, job_description=job_description)
    except Exception:
        traceback.print_exc()
        return None


def _get_job_description(session, company: Company) -> str | None:
    """Return description from one job linked to this company, if any."""
    job = (
        session.query(Job)
        .filter(Job.company_id == company.id, Job.description.isnot(None))
        .first()
    )
    return job.description if job else None


def main():
    parser = argparse.ArgumentParser(description="Re-enrich Company records via LLM.")
    parser.add_argument("--limit", type=int, default=None, help="Max companies to process")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    repo = JobRepository(session)

    try:
        q = session.query(Company).order_by(Company.enriched_at.asc().nullsfirst(), Company.id)
        if args.limit:
            q = q.limit(args.limit)
        companies = q.all()

        if not companies:
            print("No companies found.")
            return

        print(f"Processing {len(companies)} companies{' (dry run)' if args.dry_run else ''}...\n")

        enriched = 0
        failed = 0

        for co in companies:
            job_desc = _get_job_description(session, co)
            source = "job description" if job_desc else "DDGS"
            result = enrich_company(company_name=co.name_display, job_description=job_desc)
            if result is None:
                print(f"  FAILED  {co.name_display!r}  [{source}]")
                failed += 1
                continue

            before = (co.sector, co.company_type, co.what_they_do)
            after = (result.get("sector"), result.get("company_type"), result.get("what_they_do"))

            changed = before != after
            tag = "UPDATE" if changed else "SAME  "
            print(f"  {tag}  {co.name_display!r}  [{source}]")
            print(f"    sector:       {before[0]!r} → {after[0]!r}")
            print(f"    company_type: {before[1]!r} → {after[1]!r}")
            print(f"    what_they_do: {before[2]!r}")
            print(f"                → {after[2]!r}")

            if not args.dry_run and changed:
                repo.upsert_company(
                    name_normalized=co.name_normalized,
                    name_display=co.name_display,
                    sector=result.get("sector"),
                    company_type=result.get("company_type"),
                    what_they_do=result.get("what_they_do"),
                )
            enriched += 1

        print(f"\nDone. enriched={enriched} failed={failed}{' (no writes — dry run)' if args.dry_run else ''}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
