"""CLI entrypoint to validate scraper pipeline without the web server."""
import sys
import os

# Add project root to path so app imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db
from app.scraper import run_scrape


def main():
    print("Initializing database...")
    init_db()

    keywords = sys.argv[1] if len(sys.argv) > 1 else "software engineer"
    location = sys.argv[2] if len(sys.argv) > 2 else "New York"

    print(f"Scraping: keywords='{keywords}', location='{location}'")
    result = run_scrape(keywords=keywords, location=location)
    print(f"Result: {result}")

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Inserted {result['inserted']} new jobs, skipped {result['skipped']}")


if __name__ == "__main__":
    main()
