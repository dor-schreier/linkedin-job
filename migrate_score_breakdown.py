"""One-shot migration: add intelligence_json and score_breakdown_json columns to jobs table.

Idempotent — safe to run multiple times.
"""
import sqlite3

DB_PATH = "jobs.db"


def migrate():
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cur.fetchall()}

        for col, definition in [
            ("intelligence_json", "TEXT"),
            ("score_breakdown_json", "TEXT"),
        ]:
            if col in columns:
                print(f"Column '{col}' already exists — skipping.")
            else:
                con.execute(f"ALTER TABLE jobs ADD COLUMN {col} {definition}")
                print(f"Added column '{col}' to jobs table.")

        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    migrate()
