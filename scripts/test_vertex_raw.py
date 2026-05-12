"""Inspect raw Vertex AI Search response — total_size, page_size honored, pagination tokens."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from google.cloud import discoveryengine_v1

project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
location = os.getenv("VERTEX_AI_LOCATION", "global")
data_store_id = os.getenv("VERTEX_AI_DATA_STORE_ID", "")
engine_id = os.getenv("VERTEX_AI_ENGINE_ID", "")

if engine_id:
    serving_config = (
        f"projects/{project}/locations/{location}"
        f"/collections/default_collection/engines/{engine_id}"
        f"/servingConfigs/default_search"
    )
else:
    serving_config = (
        f"projects/{project}/locations/{location}"
        f"/collections/default_collection/dataStores/{data_store_id}"
        f"/servingConfigs/default_search"
    )

print(f"Serving config: {serving_config}\n")

client = discoveryengine_v1.SearchServiceClient()

QUERY = "engineer"
PAGE_SIZE = 100

request = discoveryengine_v1.SearchRequest(
    serving_config=serving_config,
    query=QUERY,
    page_size=PAGE_SIZE,
)

print(f"Querying {QUERY!r} with page_size={PAGE_SIZE}\n")

pager = client.search(request)

# Walk through all pages explicitly
page_num = 0
total_results = 0
for page in pager.pages:
    page_num += 1
    page_results = list(page.results)
    total_results += len(page_results)
    print(f"  Page {page_num}: {len(page_results)} results returned")
    print(f"            total_size reported by API: {page.total_size}")
    print(f"            next_page_token present:    {bool(page.next_page_token)}")
    if page_num >= 5:
        print("  (stopping after 5 pages)")
        break

print(f"\nTotal results collected: {total_results}")
