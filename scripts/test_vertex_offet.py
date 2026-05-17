




QUERY = "engineer"
RESULTS_PER_PAGE = 20  # Use the actual limit the API is giving you
TOTAL_TO_FETCH = 100   # Your desired total
all_results = []

for current_offset in range(0, TOTAL_TO_FETCH, RESULTS_PER_PAGE):
    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=QUERY,
        page_size=RESULTS_PER_PAGE,
        offset=current_offset,  # Explicitly move the window
    )
    
    response = client.search(request)
    
    # Access the results directly from the response object
    page_results = list(response.results)
    all_results.extend(page_results)
    
    print(f"Fetched offset {current_offset}: Got {len(page_results)} results")
    
    if not page_results:
        break

print(f"\nTotal collected: {len(all_results)}")