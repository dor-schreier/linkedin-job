"""Try to unlock more results from Vertex AI Search.

Two strategies:
  A) Lower the relevance threshold (LOWEST) so weakly-relevant docs are still served.
  B) Use explicit offset pagination to walk past the 20-result cliff.
"""
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
engine_id = os.getenv("VERTEX_AI_ENGINE_ID", "")
data_store_id = os.getenv("VERTEX_AI_DATA_STORE_ID", "")

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

client = discoveryengine_v1.SearchServiceClient()
QUERY = "engineer"

print("=" * 60)
print("STRATEGY A: relevance_threshold=LOWEST")
print("=" * 60)
try:
    RT = discoveryengine_v1.SearchRequest.RelevanceThreshold
    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=QUERY,
        page_size=100,
        relevance_threshold=RT.LOWEST,
    )
    pager = client.search(request)
    page_num = 0
    total = 0
    for page in pager.pages:
        page_num += 1
        n = len(list(page.results))
        total += n
        print(f"  Page {page_num}: {n} results | total_size={page.total_size} | "
              f"next_token={bool(page.next_page_token)}")
        if page_num >= 5:
            break
    print(f"  → Strategy A total: {total}\n")
except AttributeError:
    print("  RelevanceThreshold not available in this SDK version — skipping\n")
except Exception as e:
    print(f"  Error: {e}\n")

print("=" * 60)
print("STRATEGY B: explicit offset pagination")
print("=" * 60)
total = 0
seen = set()
for offset in (0, 20, 40, 60, 100, 200, 500, 1000):
    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=QUERY,
        page_size=100,
        offset=offset,
    )
    try:
        pager = client.search(request)
        first_page = next(iter(pager.pages), None)
        if first_page is None:
            print(f"  offset={offset}: no pages")
            continue
        urls = [r.document.derived_struct_data.get("link", "") for r in first_page.results]
        new = sum(1 for u in urls if u and u not in seen)
        seen.update(u for u in urls if u)
        print(f"  offset={offset:4d}: {len(urls)} returned, {new} new (total unique so far: {len(seen)})")
    except Exception as e:
        print(f"  offset={offset}: error — {e}")
        break

print(f"\n  → Strategy B unique URLs: {len(seen)}")
