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
