"""
Collapse free-form Company.sector values into a fixed 14-group taxonomy.

For each company the current (specific) sector is moved into `subsector` and
`sector` is overwritten with its parent group from the taxonomy below. Companies
whose sector is empty / "unknown" / already one of the 14 group names are left
untouched. Values that don't match any group are reported as UNMAPPED and left
alone so you can extend the taxonomy and re-run.

Matching is case-insensitive and punctuation-insensitive (e.g. "E-commerce",
"e commerce", "E-Commerce." all match).

Usage:
    python scripts/map_company_sectors.py              # dry run — show planned changes
    python scripts/map_company_sectors.py --apply      # write changes
    python scripts/map_company_sectors.py --apply --yes  # skip confirmation prompt
    python scripts/map_company_sectors.py --overwrite-subsector  # replace existing subsector too
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import Company

# Top-level groups -> the specific sector strings that fold into them.
TAXONOMY: dict[str, list[str]] = {
    "Cybersecurity & Privacy": [
        "Cybersecurity", "Cyber", "Industrial Cybersecurity", "Data Security",
        "Identity and Access Management", "Identity & Access Management",
        "Identity Verification", "Security", "Privacy",
    ],
    "Core Software, IT & Infrastructure": [
        "SaaS", "Software", "Technology", "IT Services", "Cloud Computing",
        "Information Technology", "Software Development", "Data Storage",
        "Database Technology", "Quantum Computing", "Infrastructure",
        "Networking", "Data Storage & Management", "Storage", "IT Operations",
        "Software Testing", "AI", "Artificial Intelligence", "Data Analytics",
        "Data & Analytics", "Data Science", "Data", "Data Management",
        "Enterprise Software", "Core", "Core Software", "Telecommunications",
        "Telecommunications Software", "Networking and Telecommunications",
        "Cloud Storage", "Data Center Services", "IT Service Management",
        "Observability", "Online Services", "Web Development", "Mobile Technology",
        "Financial Data", "Smart Cities", "Engineering Software",
    ],
    "Fintech & Financial Services": [
        "Fintech", "Financial Services", "Insurtech", "Insurance", "Blockchain",
        "Banking", "Finance", "Trade Finance Technology", "Payments",
        "Asset Management", "Quant Trading", "Regtech", "Investment Management",
        "Insurance Software", "Fin",
    ],
    "HealthTech, Life Sciences & Healthcare": [
        "Healthcare", "Biotechnology", "Medical Devices", "Clinical Research",
        "Pharmaceuticals", "Life Sciences", "Healthtech", "Healthcare Technology",
        "Health",
    ],
    "Hardware, Semiconductors & DeepTech": [
        "Semiconductors", "Semiconductor", "Semiconductor Design",
        "Semiconductor Manufacturing Equipment", "Semiconductor Design Software",
        "Semiconductor Equipment", "Hardware", "Consumer Electronics", "Robotics",
        "IoT", "Optics",
    ],
    "Aerospace, Defense & GovTech": [
        "Defense", "Aerospace", "Aerospace and Defense", "Aerospace & Defense",
        "Government", "Aer", "Public Safety Technology", "Fire and Safety",
    ],
    "HR Tech & Human Resources": [
        "HR Tech", "Human Resources", "Recruitment", "Human Resources Technology",
        "IT Staffing & Consulting", "Staffing", "Staffing and Recruiting",
        "Staffing and Recruitment",
    ],
    "E-commerce, Retail & Consumer Goods": [
        "E-commerce", "Retail Technology", "Retail", "Consumer Goods",
        "Consumer Packaged Goods", "Home Decor", "Apparel Manufacturing",
        "Cosmetics", "Tobacco", "Cannabis", "Retail Tech", "Apparel & Footwear",
        "Apparel Technology", "Fashion", "Luxury Goods",
    ],
    "Automotive, Mobility & Logistics": [
        "Automotive", "Automotive Technology", "Transportation",
        "Transportation Technology", "Mobility", "Logistics", "Logistics Tech",
        "Fleet Management Software", "Maritime Technology", "Maritime",
        "Supply Chain & Logistics Technology", "Supply Chain Management",
    ],
    "Marketing, Advertising & Social Media": [
        "AdTech", "Advertising Technology", "Marketing", "Marketing Technology",
        "Marketing & Advertising", "Mobile Marketing", "Digital Advertising",
        "Social Media", "Customer Engagement", "Customer Service Software",
        "Advertising", "Marketing and Advertising", "Digital Marketing",
        "Branding", "Market Research",
    ],
    "Media, Entertainment & Gaming": [
        "Gaming", "Mobile Gaming", "Video Games", "Media", "Media & Entertainment",
        "Media and Entertainment", "iGaming", "Sports Media",
    ],
    "Professional Services & Business Tools": [
        "Consulting", "Venture Capital", "Business Services",
        "Business Process Management", "LegalTech", "Legal Services",
        "Professional", "Engineering Services",
    ],
    "Industry, Energy & Sustainability": [
        "Energy", "Renewable Energy", "Construction Tech", "Manufacturing",
        "Industrial Manufacturing", "Industrial", "Industrial Conglomerate",
        "AgriTech", "Agrochemicals", "FoodTech", "Food & Beverage",
        "Water Technology", "Construction", "Industrial Automation",
        "Industrial Technology", "Agriculture", "Agriculture Technology",
        "Food Delivery", "Chemicals", "Chemicals Distribution",
        "Industrial Packaging", "Sustainability", "Engineering",
        "Engineering and Construction", "Printing",
    ],
    "Education & Social Impact": [
        "EdTech", "Humanitarian Aid", "Non-profit", "Education",
    ],
}

# Values that should never be touched (no meaningful sector to collapse).
SKIP_VALUES = {"", "unknown", "unspecified", "unknown / unspecified", "n/a", "none"}


def _norm(value: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace for tolerant matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


# Reverse lookup: normalized specific sector -> parent group.
_LOOKUP: dict[str, str] = {}
for _group, _members in TAXONOMY.items():
    _LOOKUP[_norm(_group)] = _group          # group names map to themselves
    for _m in _members:
        _LOOKUP[_norm(_m)] = _group

_GROUP_NORMS = {_norm(g) for g in TAXONOMY}


def classify(sector: str | None) -> tuple[str, str | None]:
    """Return (action, group). action in: skip, already, mapped, unmapped."""
    n = _norm(sector or "")
    if n in SKIP_VALUES or not n:
        return "skip", None
    if n in _GROUP_NORMS:
        return "already", _LOOKUP[n]
    group = _LOOKUP.get(n)
    return ("mapped", group) if group else ("unmapped", None)


def main():
    parser = argparse.ArgumentParser(description="Collapse Company.sector into 14-group taxonomy.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument("--overwrite-subsector", action="store_true",
                        help="Move sector into subsector even if subsector already has a value")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        companies = session.query(Company).order_by(Company.id).all()
        if not companies:
            print("No companies found.")
            return

        planned = []           # (company, group, new_subsector)
        already = skipped = 0
        unmapped: dict[str, int] = {}

        for co in companies:
            action, group = classify(co.sector)
            if action == "skip":
                skipped += 1
            elif action == "already":
                already += 1
            elif action == "unmapped":
                unmapped[co.sector] = unmapped.get(co.sector, 0) + 1
            else:  # mapped
                if co.subsector and not args.overwrite_subsector:
                    new_sub = co.subsector       # keep richer existing detail
                else:
                    new_sub = co.sector
                planned.append((co, group, new_sub))

        print(f"Companies: {len(companies)} | to map: {len(planned)} | "
              f"already grouped: {already} | skipped (unknown/empty): {skipped} | "
              f"unmapped values: {len(unmapped)}\n")

        # Group the plan by target for a readable summary.
        by_group: dict[str, int] = {}
        for _, g, _ in planned:
            by_group[g] = by_group.get(g, 0) + 1
        for g in TAXONOMY:
            if by_group.get(g):
                print(f"  {by_group[g]:4d} -> {g}")
        print()

        if planned:
            print("Sample of planned changes:")
            for co, g, sub in planned[:25]:
                print(f"  [{co.id}] {co.name_display!r}: sector {co.sector!r} -> {g!r} "
                      f"(subsector -> {sub!r})")
            if len(planned) > 25:
                print(f"  ... and {len(planned) - 25} more")
            print()

        if unmapped:
            print("UNMAPPED sector values (left untouched — add to TAXONOMY and re-run):")
            for val, n in sorted(unmapped.items(), key=lambda kv: -kv[1]):
                print(f"  {n:4d}  {val!r}")
            print()

        if not args.apply:
            print("Dry run. Re-run with --apply to write changes.")
            return

        if not planned:
            print("Nothing to apply.")
            return

        if not args.yes:
            resp = input(f"Apply {len(planned)} sector remappings? [y/N] ").strip().lower()
            if resp not in ("y", "yes"):
                print("Aborted.")
                return

        for co, g, sub in planned:
            co.subsector = sub
            co.sector = g
        session.commit()
        print(f"\nDone. Remapped {len(planned)} companies into the 14-group taxonomy.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
