"""Diagnose Vertex AI Search result counts for different query shapes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.scrapers.search_backends import VertexAiSearchBackend

backend = VertexAiSearchBackend()

QUERIES = [
    "engineer",
    "software engineer",
    '"Team Lead"',
    "site:comeet.com/jobs/ engineer",
    'site:comeet.com/jobs/ "Team Lead" OR "Tech Lead" OR "Lead Engineer" OR "staff engineer" OR "engineering manager"',
    '"Team Lead"',
    '"Tech Lead"',
    '"Lead Engineer"',
    '"staff engineer"',
    '"engineering manager"',
]

for q in QUERIES:
    try:
        urls = backend.search(q, 200)
        print(f"{len(urls):4d} results | {q!r}")
    except Exception as e:
        print(f"ERROR | {q!r} | {e}")
