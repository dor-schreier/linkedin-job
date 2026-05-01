"""Import a LinkedIn official data-export ZIP and generate a CV.

Usage:
  python scripts/import_linkedin_zip.py --zip ~/Downloads/linkedin-data.zip --output cv_output/

The ZIP is downloaded from: LinkedIn → Settings → Data Privacy → Get a copy of your data.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import zipfile
from pathlib import Path

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    """Read a CSV from a ZIP by filename (case-insensitive). Returns [] if missing."""
    candidates = {n.lower(): n for n in zf.namelist()}
    key = name.lower()
    if key not in candidates:
        return []
    with zf.open(candidates[key]) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        return list(reader)


def parse_linkedin_zip(zf: zipfile.ZipFile) -> "LinkedInProfile":
    """Parse a LinkedIn data-export ZIP into a LinkedInProfile."""
    from app.schemas import (
        LinkedInProfile,
        LinkedInExperience,
        LinkedInEducation,
        LinkedInSkill,
        LinkedInCertification,
        LinkedInLanguage,
        LinkedInProject,
        LinkedInPublication,
        LinkedInHonor,
        LinkedInVolunteer,
        LinkedInRecommendation,
        LinkedInCourse,
    )

    # Personal / Profile.csv
    profile_rows = _read_csv(zf, "Profile.csv")
    personal: dict = {}
    if profile_rows:
        row = profile_rows[0]
        personal["full_name"] = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
        personal["headline"] = row.get("Headline") or None
        personal["about"] = row.get("Summary") or None
        personal["profile_url"] = row.get("Public Profile Url") or row.get("Vanity Name") or "linkedin-export"

    # Email address
    email_rows = _read_csv(zf, "Email Addresses.csv")
    if email_rows:
        personal["email"] = email_rows[0].get("Email Address") or None

    # Phone numbers
    phone_rows = _read_csv(zf, "PhoneNumbers.csv")
    if phone_rows:
        personal["phone"] = phone_rows[0].get("Number") or None

    # Experience — Positions.csv
    experience: list[LinkedInExperience] = []
    for row in _read_csv(zf, "Positions.csv"):
        title = row.get("Title", "").strip()
        if not title:
            continue
        end_date = row.get("Finished On", "").strip() or None
        experience.append(LinkedInExperience(
            title=title,
            company=row.get("Company Name", "").strip(),
            location=row.get("Location", "").strip() or None,
            start_date=row.get("Started On", "").strip() or None,
            end_date=end_date,
            is_current=not bool(end_date),
            description=row.get("Description", "").strip() or None,
        ))

    # Education — Education.csv
    education: list[LinkedInEducation] = []
    for row in _read_csv(zf, "Education.csv"):
        school = row.get("School Name", "").strip()
        if not school:
            continue
        education.append(LinkedInEducation(
            school=school,
            degree=row.get("Degree Name", "").strip() or None,
            field_of_study=row.get("Field Of Study", "").strip() or None,
            start_year=row.get("Start Date", "").strip() or None,
            end_year=row.get("End Date", "").strip() or None,
            activities=row.get("Activities and Societies", "").strip() or None,
            description=row.get("Notes", "").strip() or None,
        ))

    # Skills — Skills.csv
    skills: list[LinkedInSkill] = []
    for row in _read_csv(zf, "Skills.csv"):
        name = row.get("Name", "").strip()
        if name:
            skills.append(LinkedInSkill(skill_name=name))

    # Certifications — Certifications.csv
    certifications: list[LinkedInCertification] = []
    for row in _read_csv(zf, "Certifications.csv"):
        name = row.get("Name", "").strip()
        if name:
            certifications.append(LinkedInCertification(
                name=name,
                issuing_org=row.get("Authority", "").strip() or None,
                issue_date=row.get("Started On", "").strip() or None,
                expiry_date=row.get("Finished On", "").strip() or None,
                credential_url=row.get("Url", "").strip() or None,
            ))

    # Languages — Languages.csv
    languages: list[LinkedInLanguage] = []
    for row in _read_csv(zf, "Languages.csv"):
        lang = row.get("Name", "").strip()
        if lang:
            languages.append(LinkedInLanguage(
                language=lang,
                proficiency=row.get("Proficiency", "").strip() or None,
            ))

    # Honors — Honors.csv
    honors: list[LinkedInHonor] = []
    for row in _read_csv(zf, "Honors.csv"):
        title = row.get("Title", "").strip()
        if title:
            honors.append(LinkedInHonor(
                title=title,
                issuer=row.get("Issuer", "").strip() or None,
                date=row.get("Issued On", "").strip() or None,
                description=row.get("Description", "").strip() or None,
            ))

    # Volunteer — Volunteer Causes.csv
    volunteer: list[LinkedInVolunteer] = []
    for row in _read_csv(zf, "Volunteer Causes.csv"):
        role = row.get("Role", "").strip()
        if role:
            volunteer.append(LinkedInVolunteer(
                role=role,
                organization=row.get("Company Name", "").strip() or None,
                cause=row.get("Cause", "").strip() or None,
                description=row.get("Description", "").strip() or None,
            ))

    # Projects — Projects.csv
    projects: list[LinkedInProject] = []
    for row in _read_csv(zf, "Projects.csv"):
        name = row.get("Title", "").strip()
        if name:
            projects.append(LinkedInProject(
                name=name,
                description=row.get("Description", "").strip() or None,
                url=row.get("Url", "").strip() or None,
                start_date=row.get("Started On", "").strip() or None,
                end_date=row.get("Finished On", "").strip() or None,
            ))

    # Publications — Publications.csv
    publications: list[LinkedInPublication] = []
    for row in _read_csv(zf, "Publications.csv"):
        title = row.get("Name", "").strip()
        if title:
            publications.append(LinkedInPublication(
                title=title,
                publisher=row.get("Publisher", "").strip() or None,
                date=row.get("Published On", "").strip() or None,
                description=row.get("Description", "").strip() or None,
                url=row.get("Url", "").strip() or None,
            ))

    # Courses — Courses.csv
    courses: list[LinkedInCourse] = []
    for row in _read_csv(zf, "Courses.csv"):
        name = row.get("Name", "").strip()
        if name:
            courses.append(LinkedInCourse(
                name=name,
                number=row.get("Number", "").strip() or None,
                associated_with=row.get("Associated With", "").strip() or None,
            ))

    # Recommendations received — Recommendations_Received.csv
    recommendations: list[LinkedInRecommendation] = []
    for row in _read_csv(zf, "Recommendations_Received.csv"):
        text = row.get("Text", "").strip() or row.get("Body", "").strip()
        if text:
            recommendations.append(LinkedInRecommendation(
                recommender_name=row.get("First Name", "").strip() + " " + row.get("Last Name", "").strip(),
                text=text,
            ))

    return LinkedInProfile(
        **personal,
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
        honors=honors,
        volunteer=volunteer,
        projects=projects,
        publications=publications,
        courses=courses,
        recommendations=recommendations,
    )


def main():
    parser = argparse.ArgumentParser(description="Import LinkedIn data-export ZIP and generate a CV.")
    parser.add_argument("--zip", required=True, help="Path to LinkedIn data export ZIP file")
    parser.add_argument("--output", default="cv_output", help="Output directory for CV files")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI bullet rewriting")
    args = parser.parse_args()

    zip_path = Path(args.zip).expanduser()
    if not zip_path.exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    from dotenv import load_dotenv
    load_dotenv()

    print(f"Reading ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        profile = parse_linkedin_zip(zf)

    print(f"Parsed profile: {profile.full_name}")

    from app.services.cv_builder import build_cv_from_profile
    cv = build_cv_from_profile(profile, rewrite_bullets=not args.no_ai)

    # Save JSON
    json_path = output_dir / f"{profile.full_name.replace(' ', '_') or 'cv'}_CV.json"
    json_path.write_text(json.dumps(cv.model_dump(), indent=2), encoding="utf-8")
    print(f"JSON saved: {json_path}")

    # Save PDF
    try:
        from app.services.cv_renderer import render_cv_pdf
        pdf_bytes = render_cv_pdf(cv)
        pdf_path = output_dir / f"{profile.full_name.replace(' ', '_') or 'cv'}_CV.pdf"
        pdf_path.write_bytes(pdf_bytes)
        print(f"PDF saved: {pdf_path}")
    except ImportError:
        print("WeasyPrint not installed — PDF skipped. Run: pip install weasyprint")

    # Persist to DB
    try:
        from app.database import SessionLocal
        from app.repository import JobRepository
        with SessionLocal() as session:
            repo = JobRepository(session)
            repo.upsert_profile_raw(profile.profile_url, profile.model_dump())
            repo.save_cv(profile.profile_url, cv.model_dump())
        print("Saved to database.")
    except Exception as exc:
        print(f"DB save skipped: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
