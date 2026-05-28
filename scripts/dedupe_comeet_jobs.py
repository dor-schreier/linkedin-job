"""Merge duplicate Comeet job rows that were created before URL-derived dedup was in place.

Usage:
    python scripts/dedupe_comeet_jobs.py            # dry-run (safe, prints plan only)
    python scripts/dedupe_comeet_jobs.py --apply    # commit merges and deletes to DB

For each group of Comeet rows that share the same URL-derived identity:
  - Keep the oldest row (lowest id).
  - Migrate non-default fields from newer duplicates onto the survivor when the
    survivor is still at its default: status (NEW), intelligence_json, score_breakdown_json,
    fit_score, fit_summary, user_rating, user_notes, is_rejected.
  - Rewrite survivor's job_hash to the new URL-derived value (sha256("comeet|<identity>")).
  - Delete the duplicate rows.

Prints a summary: groups found, rows merged, rows deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _comeet_identity_from_url(url: str):
    from app.scrapers.comeet import _comeet_identity
    return _comeet_identity(url)


def _new_hash(identity: str) -> str:
    return hashlib.sha256(f"comeet|{identity}".encode()).hexdigest()


def _migrate_field(survivor, duplicate, field: str, default) -> bool:
    """Copy field from duplicate onto survivor if survivor still has the default value."""
    dup_val = getattr(duplicate, field, None)
    surv_val = getattr(survivor, field, None)
    if surv_val == default and dup_val != default and dup_val is not None:
        setattr(survivor, field, dup_val)
        return True
    return False


def run(apply: bool) -> None:
    from app.database import SessionLocal, init_db
    from app.models import Job, JobStatus

    init_db()

    with SessionLocal() as session:
        comeet_jobs = (
            session.query(Job)
            .filter(Job.source == "comeet")
            .order_by(Job.id)
            .all()
        )

    print(f"Found {len(comeet_jobs)} Comeet rows in DB.")

    # Group by URL-derived identity
    groups: dict[str, list] = {}
    no_identity: list = []

    for job in comeet_jobs:
        identity = _comeet_identity_from_url(job.apply_url or "")
        if identity is None:
            no_identity.append(job)
            continue
        groups.setdefault(identity, []).append(job)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Rows with unparseable URL (skipped): {len(no_identity)}")

    if not duplicate_groups:
        print("Nothing to do.")
        return

    total_merged = 0
    total_deleted = 0

    with SessionLocal() as session:
        for identity, jobs in duplicate_groups.items():
            # Jobs are already sorted by id (ascending) from the query above
            survivor_id = jobs[0].id
            duplicate_ids = [j.id for j in jobs[1:]]

            # Re-fetch within this session
            survivor = session.get(Job, survivor_id)
            duplicates = [session.get(Job, did) for did in duplicate_ids]

            fields_changed: list[str] = []

            for dup in duplicates:
                if dup is None:
                    continue
                for field, default in [
                    ("status", JobStatus.NEW),
                    ("intelligence_json", None),
                    ("score_breakdown_json", None),
                    ("fit_score", None),
                    ("fit_summary", None),
                    ("user_rating", None),
                    ("is_rejected", False),
                ]:
                    if _migrate_field(survivor, dup, field, default):
                        fields_changed.append(field)

            new_hash = _new_hash(identity)
            hash_changed = survivor.job_hash != new_hash

            print(
                f"\nGroup identity={identity!r}\n"
                f"  survivor id={survivor_id} (job_hash={'unchanged' if not hash_changed else 'will update'})\n"
                f"  duplicates to delete: {duplicate_ids}\n"
                f"  fields migrated: {fields_changed or 'none'}"
            )

            if apply:
                if hash_changed:
                    survivor.job_hash = new_hash
                for dup in duplicates:
                    if dup is not None:
                        session.delete(dup)
                total_merged += 1
                total_deleted += len(duplicate_ids)

        if apply:
            session.commit()

    print(f"\n{'Applied' if apply else 'Dry-run'} summary:")
    print(f"  Duplicate groups found : {len(duplicate_groups)}")
    if apply:
        print(f"  Groups merged          : {total_merged}")
        print(f"  Rows deleted           : {total_deleted}")
    else:
        print("  Run with --apply to commit changes.")


def main():
    parser = argparse.ArgumentParser(description="Deduplicate Comeet jobs by URL identity.")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Commit merges and deletes. Without this flag, only a dry-run is performed.",
    )
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
