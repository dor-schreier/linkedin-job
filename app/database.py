import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_PATH = "data/jobs.db"

os.makedirs("data", exist_ok=True)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=DELETE")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Generator that yields a database session and closes it after use."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Create all database tables defined in ORM models."""
    from app import models  # noqa: F401 — import models to register with Base.metadata
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    # Phase 4 migration: add ai_recommendations column if not present.
    # SQLite ALTER TABLE ADD COLUMN is idempotent via try/except (no IF NOT EXISTS clause).
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN ai_recommendations TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN linkedin_analysis TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE profile ADD COLUMN linkedin_analyzed_at DATETIME"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN intelligence_json TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN score_breakdown_json TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN date_posted DATE"))
            conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN company_id INTEGER REFERENCES companies(id)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_tech_stack_json TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_qualifications_json TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_experience_needed VARCHAR(200)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_general_description TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN summary_generated_at DATETIME"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN user_rating INTEGER"))
            conn.commit()
        except Exception:
            pass
        # Search Config v2 migrations
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN role_level VARCHAR(50)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN include_remote BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN country VARCHAR(100) NOT NULL DEFAULT 'israel'"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN max_age_hours INTEGER DEFAULT 72"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN exclude_keywords TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN blocked_companies TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN results_wanted INTEGER NOT NULL DEFAULT 50"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN min_salary INTEGER"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE search_configs ADD COLUMN include_comeet BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        # CV feature migrations
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS linkedin_profiles_raw ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "profile_url VARCHAR(500) UNIQUE NOT NULL, "
                "raw_json TEXT NOT NULL, "
                "scraped_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS cv_records ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "profile_url VARCHAR(500) NOT NULL, "
                "cv_json TEXT NOT NULL, "
                "template_name VARCHAR(100) NOT NULL DEFAULT 'default', "
                "generated_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN last_checked_at DATETIME"))
            conn.commit()
        except Exception:
            pass
        # Reject-by feature migrations
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN is_rejected BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN rejected_at DATETIME"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN rejected_by_rule_id INTEGER REFERENCES reject_rules(id) ON DELETE SET NULL"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_reject_rules_type_prop_value "
                "ON reject_rules(rule_type, IFNULL(property_name,''), value)"
            ))
            conn.commit()
        except Exception:
            pass
        # Uploaded CV migration
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS uploaded_cvs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "file_path TEXT NOT NULL, "
                "original_filename TEXT NOT NULL, "
                "parsed_json TEXT NOT NULL, "
                "uploaded_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.commit()
        except Exception:
            pass
        os.makedirs("data/uploads/cv", exist_ok=True)
        # Tailored CV migration
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS tailored_cvs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "job_id INTEGER NOT NULL UNIQUE, "
                "cv_json TEXT NOT NULL, "
                "pdf_path TEXT, "
                "docx_path TEXT, "
                "model_used TEXT, "
                "generated_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.commit()
        except Exception:
            pass
        os.makedirs("data/uploads/tailored_cv", exist_ok=True)
        # Interview tracker migrations
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN applied_at DATETIME"))
            conn.commit()
        except Exception:
            pass
        # Rebuild notifications table to support interview reminders (idempotent: check for 'kind' column)
        try:
            conn.execute(text("SELECT kind FROM notifications LIMIT 1"))
            # Column already exists — just ensure interview_id and message exist
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN interview_id INTEGER"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN message VARCHAR(300)"))
                conn.commit()
            except Exception:
                pass
        except Exception:
            # Rebuild: make watch_rule_id nullable and add new columns
            try:
                conn.execute(text(
                    "CREATE TABLE notifications_new ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "job_id INTEGER NOT NULL, "
                    "watch_rule_id INTEGER, "
                    "is_read BOOLEAN DEFAULT 0, "
                    "kind VARCHAR(30) NOT NULL DEFAULT 'watch_match', "
                    "interview_id INTEGER, "
                    "message VARCHAR(300), "
                    "created_at DATETIME DEFAULT (datetime('now')))"
                ))
                conn.execute(text(
                    "INSERT INTO notifications_new (id, job_id, watch_rule_id, is_read, created_at) "
                    "SELECT id, job_id, watch_rule_id, is_read, created_at FROM notifications"
                ))
                conn.execute(text("DROP TABLE notifications"))
                conn.execute(text("ALTER TABLE notifications_new RENAME TO notifications"))
                conn.commit()
            except Exception:
                pass
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS interviews ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, "
                "scheduled_at DATETIME NOT NULL, "
                "interview_type VARCHAR(20) NOT NULL, "
                "medium VARCHAR(20) NOT NULL, "
                "location VARCHAR(500), "
                "notes TEXT, "
                "created_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_interviews_job_id ON interviews(job_id)"
            ))
            conn.commit()
        except Exception:
            pass
        # Company enriched_at migration
        try:
            conn.execute(text("ALTER TABLE companies ADD COLUMN enriched_at DATETIME"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE companies ADD COLUMN subsector TEXT"))
            conn.commit()
        except Exception:
            pass
        # Similarity engine migrations
        for col in [
            "ALTER TABLE jobs ADD COLUMN is_target BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE jobs ADD COLUMN similarity_score INTEGER",
            "ALTER TABLE jobs ADD COLUMN similarity_breakdown_json TEXT",
        ]:
            try:
                conn.execute(text(col))
                conn.commit()
            except Exception:
                pass
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS similarity_weights ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "weight_title REAL NOT NULL DEFAULT 1.0, "
                "weight_skills REAL NOT NULL DEFAULT 1.0, "
                "weight_seniority REAL NOT NULL DEFAULT 1.0, "
                "weight_sector REAL NOT NULL DEFAULT 1.0, "
                "is_enabled BOOLEAN NOT NULL DEFAULT 1, "
                "min_score_threshold INTEGER, "
                "updated_at DATETIME DEFAULT (datetime('now')))"
            ))
            conn.commit()
        except Exception:
            pass
        # ScrapeLog extended stats migration
        for col in [
            "ALTER TABLE scrape_logs ADD COLUMN trigger VARCHAR(20)",
            "ALTER TABLE scrape_logs ADD COLUMN linkedin_count INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN indeed_count INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN glassdoor_count INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN comeet_count INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN filter_blocked INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN filter_keywords INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN filter_salary INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN filter_remote INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN jobs_scored INTEGER",
            "ALTER TABLE scrape_logs ADD COLUMN score_failed INTEGER",
        ]:
            try:
                conn.execute(text(col))
                conn.commit()
            except Exception:
                pass
        # Per-source cleanup selection (NULL = all sources)
        try:
            conn.execute(text("ALTER TABLE scheduler_config ADD COLUMN cleanup_sources TEXT"))
            conn.commit()
        except Exception:
            pass
        # Max jobs to check per cleanup run (NULL = no limit)
        try:
            conn.execute(text("ALTER TABLE scheduler_config ADD COLUMN cleanup_limit INTEGER"))
            conn.commit()
        except Exception:
            pass
        # Skip jobs validated within the past N hours during cleanup (NULL/0 = don't skip)
        try:
            conn.execute(text("ALTER TABLE scheduler_config ADD COLUMN cleanup_skip_validated_hours INTEGER"))
            conn.commit()
        except Exception:
            pass
        # Timestamp of last definitive cleanup verdict (active/inactive) per job
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN last_validated_at DATETIME"))
            conn.commit()
        except Exception:
            pass
