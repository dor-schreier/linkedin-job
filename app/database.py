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
    cursor.execute("PRAGMA journal_mode=WAL")
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
