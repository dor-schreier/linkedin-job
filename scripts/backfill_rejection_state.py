"""
Backfill existing jobs to enforce co-dependent rejection field consistency.

Rule: if status=REJECTED OR is_rejected=True → status=REJECTED, is_rejected=True, is_active=False
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_
from app.database import SessionLocal, init_db
from app.models import Job, JobStatus


def main():
    init_db()
    session = SessionLocal()
    try:
        inconsistent = (
            session.query(Job)
            .filter(
                or_(
                    Job.status == JobStatus.REJECTED,
                    Job.is_rejected == True,
                )
            )
            .all()
        )

        if not inconsistent:
            print("No jobs need updating.")
            return

        print(f"Found {len(inconsistent)} jobs to normalize.")
        for job in inconsistent:
            before = (job.status, job.is_rejected, job.is_active)
            job.status = JobStatus.REJECTED
            job.is_rejected = True
            job.is_active = False
            after = (job.status, job.is_rejected, job.is_active)
            if before != after:
                print(f"  job {job.id:>6}: {before} → {after}")

        session.commit()
        print("Done.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
