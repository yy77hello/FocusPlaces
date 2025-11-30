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
from urllib.parse import urlencode
import datetime

load_dotenv()
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GOOGLE_PLACES_API_KEY in .env")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

from nlp_review_processor import process_places, process_place_reviews


def geocode_address(address):
    params = {"address": address, "key": API_KEY}
    resp = requests.get(GEOCODE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None
    loc = results[0].get("geometry", {}).get("location")
    return (loc.get("lat"), loc.get("lng")) if loc else None


def make_textsearch_request(params):
    resp = requests.get(TEXT_SEARCH_URL, params=params)
    resp.raise_for_status()
    return resp.json()


def text_search(query, location=None, radius=5000, max_results=10):
    candidates = []
    params = {"query": query, "key": API_KEY}
    if location:
        lat, lng = location
        params["location"] = f"{lat},{lng}"
        params["radius"] = radius
    remaining = max_results
    next_token = None
    while True:
        if next_token:
            params = {"pagetoken": next_token, "key": API_KEY}
        data = make_textsearch_request(params)
        results = data.get("results", [])
        for r in results:
            if remaining <= 0:
                break
            candidates.append({
                "name": r.get("name"),
                "place_id": r.get("place_id"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "location": r.get("geometry", {}).get("location"),
                "formatted_address": r.get("formatted_address"),
            })
            remaining -= 1
        if remaining <= 0:
            break
        next_token = data.get("next_page_token")
        if not next_token:
            break
        time.sleep(2)
    return candidates


def text_search_multi(queries, location=None, radius=5000, max_results_per_query=10):
    # Run text_search for each query and dedupe by place_id
    by_id = {}
    for q in queries:
        cand = text_search(q, location=location, radius=radius, max_results=max_results_per_query)
        for c in cand:
            pid = c.get("place_id")
            if not pid:
                continue
            if pid in by_id:
                # merge some metadata, keep best rating if available
                existing = by_id[pid]
                if c.get("rating") and (not existing.get("rating") or c.get("rating") > existing.get("rating")):
                    existing.update(c)
            else:
                by_id[pid] = c
    return list(by_id.values())


def fetch_place_details(place_id, max_reviews=5):
    params = {
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,formatted_address,geometry,reviews,utc_offset,website",
        "key": API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    reviews = []
    for rev in result.get("reviews", [])[:max_reviews]:
        # Keep 'time' if available
        reviews.append({
            "author_name": rev.get("author_name"),
            "rating": rev.get("rating"),
            "relative_time_description": rev.get("relative_time_description"),
            "text": rev.get("text"),
            "time": rev.get("time"),
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


def top_contributing_review(processed_place):
    per = processed_place.get("per_review", [])
    if not per:
        return None, None, None
    best = max(per, key=lambda r: r.get("score", float("-inf")))
    return best.get("score"), best.get("raw_text"), best.get("index")


def search_and_process(queries, location=None, radius=10000, max_candidates=20, max_reviews_per_place=5, recent_days=365, min_recent_reviews=3):
    # Determine candidates across queries
    candidates = text_search_multi(queries, location=location, radius=radius, max_results_per_query=max_candidates)
    detailed = []
    warnings = []
    for c in candidates:
        pid = c.get("place_id")
        time.sleep(0.1)
        details = fetch_place_details(pid, max_reviews=max_reviews_per_place)
        details["formatted_address"] = details.get("formatted_address") or c.get("formatted_address")
        details["rating"] = details.get("rating") or c.get("rating")
        details["user_ratings_total"] = details.get("user_ratings_total") or c.get("user_ratings_total")
        detailed.append(details)
    processed = process_places(detailed, recent_days=recent_days)
    # attach warning flag for low recent reviews
    for p in processed:
        if p.get("recent_review_count", 0) < min_recent_reviews:
            p["recent_reviews_warning"] = True
            p["recent_reviews_warning_text"] = f"Only {p.get('recent_review_count',0)} recent reviews in the last {recent_days} days (minimum {min_recent_reviews}). Results may be unreliable." 
        else:
            p["recent_reviews_warning"] = False
    return processed


if __name__ == '__main__':
    # quick CLI demo
    q = ["coffee shop", "library", "co-working space"]
    print("Running demo search (set GOOGLE_PLACES_API_KEY in .env)...")
    res = search_and_process(q, location=None, radius=10000, max_candidates=10)
    for r in res[:10]:
        print(r.get('name'), r.get('focus_score_0_100'), r.get('recent_reviews_warning'))