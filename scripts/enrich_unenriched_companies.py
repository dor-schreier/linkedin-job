"""
Enrich companies that were never properly enriched:
  1. Existing Company rows with empty/null sector, company_type, or what_they_do
  2. Jobs with no company_id — creates a Company record and links the job

Usage:
    python scripts/enrich_unenriched_companies.py              # enrich all
    python scripts/enrich_unenriched_companies.py --limit 20   # stop after 20
    python scripts/enrich_unenriched_companies.py --dry-run    # preview without writing
"""
import argparse
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.CRITICAL)
for _lg in ("app.services.llm_service", "app.services"):
    _h = logging.StreamHandler(sys.stderr)
    _h.setLevel(logging.DEBUG)
    logging.getLogger(_lg).setLevel(logging.DEBUG)
    logging.getLogger(_lg).addHandler(_h)

from sqlalchemy import or_

from app.database import SessionLocal, init_db
from app.models import Company, Job
from app.repository import JobRepository
from app.services.llm_service import enrich_company


def _is_empty(val) -> bool:
    return val is None or str(val).strip() == ""


def _get_job_description(session, company_id: int) -> str | None:
    job = (
        session.query(Job)
        .filter(Job.company_id == company_id, Job.description.isnot(None))
        .first()
    )
    return job.description if job else None


def _enrich_and_save(repo, session, name_normalized, name_display, job_desc, dry_run, provider) -> bool:
    grounding = provider == "vertexai" and not job_desc
    source = "job desc" if job_desc else ("vertex grounding" if grounding else "DDGS")
    print(f"  source=[{source}]", end="", flush=True)

    try:
        result = enrich_company(company_name=name_display, job_description=job_desc)
    except Exception:
        print("  FAILED")
        traceback.print_exc()
        return False

    if result is None:
        print("  FAILED (no result)")
        return False

    print(f"\n    sector:       {result.get('sector')!r}")
    print(f"    subsector:    {result.get('subsector')!r}")
    print(f"    company_type: {result.get('company_type')!r}")
    print(f"    what_they_do: {str(result.get('what_they_do', ''))[:120]!r}")

    if not dry_run:
        repo.upsert_company(
            name_normalized=name_normalized,
            name_display=name_display,
            sector=result.get("sector"),
            subsector=result.get("subsector"),
            company_type=result.get("company_type"),
            what_they_do=result.get("what_they_do"),
        )
    return True


def main():
    parser = argparse.ArgumentParser(description="Enrich companies that were never properly enriched.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    provider = os.environ.get("LLM_PROVIDER", "groq").lower()

    init_db()
    session = SessionLocal()
    repo = JobRepository(session)

    enriched = failed = linked = 0

    try:
        # ── Phase 1: existing Company rows with empty/null enrichment fields ──
        incomplete = (
            session.query(Company)
            .filter(
                or_(
                    Company.sector.is_(None), Company.sector == "",
                    Company.company_type.is_(None), Company.company_type == "",
                    Company.what_they_do.is_(None), Company.what_they_do == "",
                )
            )
            .order_by(Company.id)
            .all()
        )
        if args.limit:
            incomplete = incomplete[: args.limit]

        print(f"Provider: {provider}")
        print(f"Phase 1: {len(incomplete)} companies with incomplete enrichment"
              f"{' (dry run)' if args.dry_run else ''}...\n")

        for i, co in enumerate(incomplete, 1):
            job_desc = _get_job_description(session, co.id)
            print(f"  [{i}/{len(incomplete)}] {co.name_display!r}  ", end="")
            ok = _enrich_and_save(repo, session, co.name_normalized, co.name_display,
                                  job_desc, args.dry_run, provider)
            if ok:
                enriched += 1
            else:
                failed += 1

        # ── Phase 2: jobs with no company_id ──
        unlinked_jobs = (
            session.query(Job)
            .filter(Job.company_id.is_(None), Job.company.isnot(None), Job.company != "")
            .order_by(Job.company, Job.id)
            .all()
        )

        # Deduplicate by normalized name, keep one representative job per company
        seen: dict[str, Job] = {}
        for job in unlinked_jobs:
            key = job.company.strip().lower()
            if key not in seen:
                seen[key] = job

        unlinked_companies = list(seen.items())
        if args.limit:
            remaining = (args.limit - len(incomplete)) if args.limit else None
            if remaining is not None:
                unlinked_companies = unlinked_companies[:max(0, remaining)]

        print(f"\nPhase 2: {len(unlinked_jobs)} jobs with no company_id "
              f"({len(unlinked_companies)} distinct companies)"
              f"{' (dry run)' if args.dry_run else ''}...\n")

        for i, (name_norm, rep_job) in enumerate(unlinked_companies, 1):
            name_display = rep_job.company.strip()
            job_desc = rep_job.description

            # Check if a Company row already exists (maybe just not linked)
            existing = repo.get_company_by_normalized_name(name_norm)
            if existing and not _is_empty(existing.sector) and not _is_empty(existing.what_they_do):
                # Already enriched — just link
                if not args.dry_run:
                    for j in session.query(Job).filter(
                        Job.company_id.is_(None), Job.company == rep_job.company
                    ).all():
                        repo.update_job_company_id(j.id, existing.id)
                        linked += 1
                print(f"  [{i}/{len(unlinked_companies)}] LINKED (existing) {name_display!r}")
                continue

            print(f"  [{i}/{len(unlinked_companies)}] {name_display!r}  ", end="")
            ok = _enrich_and_save(repo, session, name_norm, name_display,
                                  job_desc, args.dry_run, provider)
            if ok:
                enriched += 1
                if not args.dry_run:
                    co = repo.get_company_by_normalized_name(name_norm)
                    if co:
                        for j in session.query(Job).filter(
                            Job.company_id.is_(None), Job.company == rep_job.company
                        ).all():
                            repo.update_job_company_id(j.id, co.id)
                            linked += 1
            else:
                failed += 1

        wrote = enriched if not args.dry_run else 0
        print(f"\nDone. enriched={enriched} failed={failed} jobs_linked={linked} wrote={wrote}"
              f"{' (no writes — dry run)' if args.dry_run else ''}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
