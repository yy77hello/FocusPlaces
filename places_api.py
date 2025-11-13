"""
 - Loads GOOGLE_PLACES_API_KEY from .env
 - Runs a Text Search for a query near a location (or by text)
 - Fetches Place Details (including reviews) for top candidates
 - Uses nlp_review_processor.py to compute a "study focus" score for each place
 - Prints a short summary for each place and then prints the top 5 places by focus score,
   including the single review that contributed most to each place's focus score and the
   keywords detected in that review.
 - Requires nlp_review_processor.py in same directory (the file you were provided)
 - Requires python-dotenv, requests, and spaCy (with en_core_web_sm)
"""

import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables from .env in project root
load_dotenv()
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GOOGLE_PLACES_API_KEY in .env")

# https://developers.google.com/maps/documentation/places/web-service/legacy/search-text
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json" # Find candidates; text search for places by query, returns a list of place results with summary fields per place
# https://developers.google.com/maps/documentation/places/web-service/legacy/details
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json" # Fetch detail info for a single place by place_id, we will use after we get candidate place_id's

# Call Text Search endpoint and return parsed json
def make_textsearch_request(params):
    resp = requests.get(TEXT_SEARCH_URL, params=params)
    resp.raise_for_status()
    return resp.json()

# Text Search to find candidate places
def text_search(query, location=None, radius=5000, max_results=10):
    """
    query: string, e.g., "coffee shop" or "library near Penn State"
    location: optional tuple (lat, lng)
    radius: meters
    max_results: total number of place results to gather across pages (default 10)
    """
    candidates = []
    params = {
        "query": query,
        "key": API_KEY,
    }

    # If a location is provided, include location and radius to bias results nearby.
    if location:
        lat, lng = location
        params["location"] = f"{lat},{lng}"
        params["radius"] = radius

    remaining = max_results
    next_token = None
    while True:
        # If we have a next_page_token the API expects only the token + api key for that request.
        if next_token:
            params = {"pagetoken": next_token, "key": API_KEY}
        data = make_textsearch_request(params)
        results = data.get("results", [])
        # Iterate over results and add them to candidates until we reached max_results.
        for r in results:
            if remaining <= 0:
                break
            # Extract only the fields we need
            candidates.append({
                "name": r.get("name"),
                "place_id": r.get("place_id"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "location": r.get("geometry", {}).get("location"),
                "formatted_address": r.get("formatted_address"),
            })
            remaining -= 1
        # Enough candidates collected so stop paging
        if remaining <= 0:
            break
        next_token = data.get("next_page_token")
        # No more pages available from the API
        if not next_token:
            break
        time.sleep(2)
    return candidates

# Place details, single place reviews
def fetch_place_details(place_id, max_reviews=5):
    """
    Fetch detailed information for a single place using its place_id
    Parameters
      - place_id: Google Place ID string
      - max_reviews: how many of the place's reviews to return (API may return more)
    Returns
      - dict containing name, place_id, rating, formatted_address, location, and a 'reviews' list.

    We request a small set of fields from the Places Details API to reduce payload
    """
    params = {
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,formatted_address,geometry,reviews",
        "key": API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    # Normalize the reviews structure
    reviews = []
    for rev in result.get("reviews", [])[:max_reviews]:
        reviews.append({
            "author_name": rev.get("author_name"),
            "rating": rev.get("rating"),
            "relative_time_description": rev.get("relative_time_description"),
            "text": rev.get("text"),
        })
    return {
        "name": result.get("name"),
        "place_id": place_id,
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "formatted_address": result.get("formatted_address"),
        "location": result.get("geometry", {}).get("location"),
        "reviews": reviews,
    }

# Small utility to make a Google Maps URL (clickable) for a place
def maps_url_for_place(place_id):
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

# NLP Processor
from nlp_review_processor import process_place_reviews, process_places

# Helper: pick the review that contributed most to focus score for a processed place
def top_contributing_review(processed_place):
    """
    processed_place: output from process_place_reviews (contains 'per_review' list with 'score' and 'raw_text')
    Returns tuple (score, raw_text, index) or (None, None, None) if none.
    """
    per = processed_place.get("per_review", [])
    if not per:
        return None, None, None
    # find the review with the max score
    best = max(per, key=lambda r: r.get("score", float("-inf")))
    return best.get("score"), best.get("raw_text"), best.get("index")

# example flow: search -> fetch details -> print summary -> compute focus scores and print top 5
def example_flow():
    query = "coffee shop"             # place type / query
    location = None                   # auto-detect, alternatively provide lat long e.g., (40.7128, -74.0060)
    radius = 10000
    max_candidates = 20

    print("Searching for:", query)
    candidates = text_search(query, location=location, radius=radius, max_results=max_candidates)
    print(f"Found {len(candidates)} candidates")

    detailed = []
    for c in candidates:
        pid = c["place_id"]
        time.sleep(0.1)
        details = fetch_place_details(pid, max_reviews=5)
        # include basic summary fields from candidate
        details["formatted_address"] = details.get("formatted_address") or c.get("formatted_address")
        details["rating"] = details.get("rating") or c.get("rating")
        details["user_ratings_total"] = details.get("user_ratings_total") or c.get("user_ratings_total")
        detailed.append(details)

    # Print readable summaries and compute NLP scores
    print("\nProcessing NLP focus scores for each place...")
    processed = process_places(detailed)  # returns list sorted by focus_score_0_100 desc

    # Print short summary for each processed place including the top contributing review and keywords found in it
    for i, p in enumerate(processed, start=1):
        print(f"\n--- #{i}: {p.get('name')}")
        print("Focus score (0-100):", p.get("focus_score_0_100"))
        print("Average per-review score:", round(p.get("focus_average", 0), 3))
        print("Rating:", p.get("rating"), "(", p.get("review_count"), "reviews analyzed )")
        print("Address:", next((d.get("formatted_address") for d in detailed if d.get("place_id")==p.get("place_id")), "N/A"))
        print("Maps URL:", maps_url_for_place(p["place_id"]))

        # top contributing review
        score, raw_text, idx = top_contributing_review(p)
        if raw_text:
            print("Top contributing review (score:", round(score, 3), f", review_idx: {idx}):")
            # print raw review text (single line)
            print("  ", raw_text.replace("\n", " ").strip())
            # print keywords found in that review (from per_review counts or keywords)
            per = p.get("per_review", [])
            rev_info = next((r for r in per if r.get("index") == idx), None)
            if rev_info:
                kw_list = None
                # prefer explicit 'keywords' field if processor provides it, otherwise use counts
                if "keywords" in rev_info:
                    kw_list = rev_info.get("keywords")
                    # keywords might be list of (kw, count) or dict; normalize to list of tuples
                    if isinstance(kw_list, dict):
                        kw_list = list(kw_list.items())
                else:
                    counts = rev_info.get("counts", {}) or {}
                    kw_list = list(counts.items())
                if kw_list:
                    print("  Keywords found:")
                    for k, c in kw_list:
                        print(f"    - {k}: {c}")
        else:
            print("No contributing review found.")

    # Print top 5 by focus score, include their top contributing review and keywords found in that review
    top_n = 5
    print(f"\nTop {top_n} places by study focus score:")
    for rank, top in enumerate(processed[:top_n], start=1):
        score, raw_text, idx = top_contributing_review(top)
        address = next((d.get("formatted_address") for d in detailed if d.get("place_id")==top.get("place_id")), "N/A")
        print(f"{rank}. {top.get('name')} — Score: {top.get('focus_score_0_100')} — Address: {address} — Maps: {maps_url_for_place(top.get('place_id'))}")
        if raw_text:
            print("   Top review (score", round(score,3), "):", raw_text.replace("\n", " ").strip())
            # print keywords for this top review as well
            per = top.get("per_review", [])
            rev_info = next((r for r in per if r.get("index") == idx), None)
            if rev_info:
                kw_list = None
                if "keywords" in rev_info:
                    kw_list = rev_info.get("keywords")
                    if isinstance(kw_list, dict):
                        kw_list = list(kw_list.items())
                else:
                    counts = rev_info.get("counts", {}) or {}
                    kw_list = list(counts.items())
                if kw_list:
                    print("   Keywords found:")
                    for k, c in kw_list:
                        print(f"     - {k}: {c}")

if __name__ == "__main__":
    example_flow()
