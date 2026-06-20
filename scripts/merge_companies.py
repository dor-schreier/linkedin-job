"""
Merge Company records whose names are variations of the same company.

Uses fuzzy matching (stdlib difflib + legal-suffix stripping — no extra deps) to
cluster companies like "Acme", "Acme Inc.", "Acme Technologies Ltd" into one group,
picks a canonical record per group, repoints every linked Job to it, rewrites the
Job.company string to the canonical display name, then deletes the duplicate rows.

Canonical pick per cluster (in order): most linked jobs → most enriched
(non-null sector/what_they_do) → longest what_they_do → lowest id.

Usage:
    python scripts/merge_companies.py                  # dry run — show proposed merges, no writes
    python scripts/merge_companies.py --apply          # perform the merges
    python scripts/merge_companies.py --threshold 0.85 # similarity cutoff (0-1, default 0.88)
    python scripts/merge_companies.py --apply --yes    # skip the confirmation prompt
"""
import argparse
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import Company, Job

# Tokens dropped before comparison: legal forms, generic descriptors, filler.
_NOISE_TOKENS = {
    "inc", "incorporated", "llc", "llp", "ltd", "limited", "co", "corp",
    "corporation", "company", "group", "holdings", "holding", "gmbh", "ag",
    "sa", "sas", "srl", "bv", "nv", "plc", "pte", "pvt", "lp", "kk", "oy",
    "ab", "as", "spa", "the", "and", "of",
    "technologies", "technology", "tech", "solutions", "systems", "software",
    "labs", "lab", "global", "international", "intl", "worldwide", "services",
    "industries", "enterprises", "ventures", "partners", "consulting",
    "digital", "studio", "studios", "online",
}


def _core_tokens(display: str) -> list[str]:
    """Reduce a display name to comparable core tokens: lowercased, depunctuated,
    legal-suffix/noise tokens dropped."""
    s = re.sub(r"[^a-z0-9]+", " ", display.lower())   # punctuation/symbols -> space
    tokens = [t for t in s.split() if t and t not in _NOISE_TOKENS]
    # If stripping noise emptied it (e.g. "The Group"), fall back to raw alnum tokens.
    return tokens or [t for t in s.split() if t]


def _is_match(ta: list[str], tb: list[str], threshold: float) -> bool:
    """True if two token cores are variations of the same name.

    Gate on a shared distinctive leading token, then accept when either the
    shorter token list is a prefix of the longer (e.g. "acme" vs "acme payments")
    or the full core strings are fuzzily similar above the threshold. The
    first-token gate is what stops unrelated names chaining together.
    """
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    if ta[0] != tb[0]:
        return False
    # Token-prefix containment: one name is the other plus trailing words.
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if longer[: len(shorter)] == shorter:
        # A single short stem (e.g. "one") must not act as a merge hub that
        # absorbs every name starting with it; require a distinctive stem.
        if len(shorter) == 1:
            return len(shorter[0]) >= 5
        return True
    return SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= threshold


def _cluster(companies, threshold):
    """Union-find clustering of companies by pairwise core-name match."""
    cores = {c.id: _core_tokens(c.name_display) for c in companies}
    parent = {c.id: c.id for c in companies}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    items = list(companies)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if _is_match(cores[a.id], cores[b.id], threshold):
                union(a.id, b.id)

    groups: dict[int, list] = {}
    for c in companies:
        groups.setdefault(find(c.id), []).append(c)
    return [g for g in groups.values() if len(g) > 1]


def _job_counts(session, ids):
    counts = {i: 0 for i in ids}
    for company_id, in (
        session.query(Job.company_id).filter(Job.company_id.in_(ids)).all()
    ):
        if company_id in counts:
            counts[company_id] += 1
    return counts


def _pick_canonical(group, job_counts):
    """Best record to keep: most jobs, then most enriched, then richest, then oldest id."""
    def score(c):
        enriched = sum(1 for v in (c.sector, c.what_they_do, c.company_type) if v)
        return (
            job_counts.get(c.id, 0),
            enriched,
            len(c.what_they_do or ""),
            -c.id,
        )
    return max(group, key=score)


def main():
    parser = argparse.ArgumentParser(description="Merge fuzzy-duplicate Company records.")
    parser.add_argument("--apply", action="store_true", help="Perform merges (default: dry run)")
    parser.add_argument("--threshold", type=float, default=0.88,
                        help="Similarity cutoff 0-1 (default 0.88; lower = more aggressive)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument("--review", action="store_true",
                        help="Confirm each merge group individually (y/n) before applying")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        companies = session.query(Company).all()
        if not companies:
            print("No companies found.")
            return

        clusters = _cluster(companies, args.threshold)
        if not clusters:
            print(f"No fuzzy-duplicate companies found at threshold {args.threshold}.")
            return

        all_ids = [c.id for g in clusters for c in g]
        job_counts = _job_counts(session, all_ids)

        plans = []
        for group in clusters:
            canonical = _pick_canonical(group, job_counts)
            dupes = [c for c in group if c.id != canonical.id]
            plans.append((canonical, dupes))

        total_dupes = sum(len(d) for _, d in plans)
        total_jobs = 0
        print(f"Found {len(plans)} merge group(s), {total_dupes} duplicate record(s) "
              f"to fold in (threshold {args.threshold}):\n")
        for canonical, dupes in plans:
            keep_jobs = job_counts.get(canonical.id, 0)
            print(f"  KEEP  [{canonical.id}] {canonical.name_display!r}  ({keep_jobs} jobs)")
            for d in dupes:
                dj = job_counts.get(d.id, 0)
                total_jobs += dj
                print(f"    <- [{d.id}] {d.name_display!r}  ({dj} jobs -> repointed)")
            print()

        if not args.apply:
            print(f"Dry run. Would merge {total_dupes} record(s) and repoint {total_jobs} job(s). "
                  f"Re-run with --apply to write (add --review to confirm each group).")
            return

        if args.review:
            kept = []
            for canonical, dupes in plans:
                names = ", ".join(f"{d.name_display!r}" for d in dupes)
                resp = input(f"Merge into [{canonical.id}] {canonical.name_display!r}: "
                             f"{names}? [y/N] ").strip().lower()
                if resp in ("y", "yes"):
                    kept.append((canonical, dupes))
            plans = kept
            if not plans:
                print("No groups selected. Aborted.")
                return
        elif not args.yes:
            resp = input(f"Apply these merges? {total_dupes} companies deleted, "
                         f"{total_jobs} jobs repointed. [y/N] ").strip().lower()
            if resp not in ("y", "yes"):
                print("Aborted.")
                return

        merged_jobs = 0
        merged_companies = 0
        for canonical, dupes in plans:
            dupe_ids = [d.id for d in dupes]
            # Repoint linked jobs and unify their company string to the canonical name.
            jobs = session.query(Job).filter(Job.company_id.in_(dupe_ids)).all()
            for job in jobs:
                job.company_id = canonical.id
                job.company = canonical.name_display
                merged_jobs += 1
            # Also unify jobs that match a duplicate only by company string (no FK).
            for d in dupes:
                session.query(Job).filter(
                    Job.company_id.is_(None), Job.company == d.name_display
                ).update(
                    {Job.company_id: canonical.id, Job.company: canonical.name_display},
                    synchronize_session=False,
                )
            for d in dupes:
                session.delete(d)
                merged_companies += 1
        session.commit()
        print(f"\nDone. Merged {merged_companies} duplicate companies into {len(plans)} canonicals; "
              f"repointed {merged_jobs} linked jobs.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
