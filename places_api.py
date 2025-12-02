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
    # Return the full response for debugging if needed, but normally return (lat,lng) or None
    results = data.get("results", [])
    if not results:
        # include status in debug via exception-free return
        return None
    loc = results[0].get("geometry", {}).get("location")
    if not loc:
        return None
    try:
        lat = float(loc.get("lat"))
        lng = float(loc.get("lng"))
        return (lat, lng)
    except Exception:
        return None


def make_textsearch_request(params):
    resp = requests.get(TEXT_SEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status")
    if status and status not in ("OK", "ZERO_RESULTS"):
        raise RuntimeError(f"Places Text Search returned status: {status} for params: {params}")
    return data


def text_search(query, location=None, radius=5000, max_results=10):
    candidates = []
    base_params = {
        "query": query,
        "key": API_KEY,
    }
    if location:
        lat, lng = location
        base_params["location"] = f"{float(lat)},{float(lng)}"
        base_params["radius"] = int(radius)

    remaining = max_results
    next_token = None
    # We must preserve the original params for the initial request.
    # For subsequent requests with next_page_token, only pagetoken and key are allowed.
    while True:
        if next_token:
            params = {"pagetoken": next_token, "key": API_KEY}
        else:
            params = base_params.copy()
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
        # According to Google API, need to wait briefly before using next_page_token
        time.sleep(2)
    return candidates


def text_search_multi(queries, location=None, radius=5000, max_results_per_query=10):
    by_id = {}
    for q in queries:
        cand = text_search(q, location=location, radius=radius, max_results=max_results_per_query)
        for c in cand:
            pid = c.get("place_id")
            if not pid:
                continue
            if pid in by_id:
                existing = by_id[pid]
                if c.get("rating") and (not existing.get("rating") or c.get("rating") > existing.get("rating")):
                    existing.update(c)
                for key in ("formatted_address", "user_ratings_total", "location"):
                    if key not in existing or not existing.get(key):
                        existing[key] = c.get(key)
            else:
                by_id[pid] = c.copy()
    return list(by_id.values())


def fetch_place_details(place_id, max_reviews=5):
    params = {
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,formatted_address,geometry,reviews",
        "key": API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    # Normalize fields: explicitly set None when missing
    name = result.get("name") if "name" in result else None
    rating = result.get("rating") if "rating" in result else None
    user_ratings_total = result.get("user_ratings_total") if "user_ratings_total" in result else None
    formatted_address = result.get("formatted_address") if "formatted_address" in result else None
    location = (result.get("geometry", {}).get("location") if result.get("geometry") else None)
    reviews = []
    for rev in result.get("reviews", [])[:max_reviews]:
        reviews.append({
            "author_name": rev.get("author_name"),
            "rating": rev.get("rating"),
            "relative_time_description": rev.get("relative_time_description"),
            "text": rev.get("text"),
            "time": rev.get("time") if "time" in rev else None,
        })
    return {
        "name": name,
        "place_id": place_id,
        "rating": rating,
        "user_ratings_total": user_ratings_total,
        "formatted_address": formatted_address,
        "location": location,
        "reviews": reviews,
    }


def maps_url_for_place(place_id):
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def top_contributing_review(processed_place):
    per = processed_place.get("per_review", [])
    if not per:
        return None, None, None
    best = max(per, key=lambda r: r.get("score", float("-inf")))
    return best.get("score"), best.get("raw_text"), best.get("index")


def search_and_process(queries, location=None, radius=10000, max_candidates=20, max_reviews_per_place=5, recent_days=365, min_recent_reviews=3):
    candidates = text_search_multi(queries, location=location, radius=radius, max_results_per_query=max_candidates)
    detailed = []
    # Build detailed list with explicit fallbacks from text-search candidate 'c'
    for c in candidates:
        pid = c.get("place_id")
        time.sleep(0.1)
        details = fetch_place_details(pid, max_reviews=max_reviews_per_place) or {}
        # Use explicit "is None" checks so falsy but valid values (0) are preserved
        if details.get("formatted_address") is None:
            details["formatted_address"] = c.get("formatted_address")
        if details.get("rating") is None:
            details["rating"] = c.get("rating")
        if details.get("user_ratings_total") is None:
            details["user_ratings_total"] = c.get("user_ratings_total")
        if details.get("location") is None:
            details["location"] = c.get("location")
        # Ensure place_id and name exist
        if details.get("place_id") is None:
            details["place_id"] = pid
        if details.get("name") is None:
            details["name"] = c.get("name")
        detailed.append(details)

    processed = process_places(detailed, recent_days=recent_days) or []

    # Copy core metadata back onto processed entries so streamlit can display them reliably
    # Build map by place_id from detailed list
    detailed_by_id = {d.get("place_id"): d for d in detailed if d.get("place_id")}
    for p in processed:
        pid = p.get("place_id")
        src = detailed_by_id.get(pid, {})
        # Only set if missing in processed or is None
        if p.get("formatted_address") is None:
            p["formatted_address"] = src.get("formatted_address")
        if p.get("rating") is None:
            p["rating"] = src.get("rating")
        if p.get("user_ratings_total") is None:
            p["user_ratings_total"] = src.get("user_ratings_total")
        if p.get("location") is None:
            p["location"] = src.get("location")

        if p.get("recent_review_count", 0) < min_recent_reviews:
            p["recent_reviews_warning"] = True
            p["recent_reviews_warning_text"] = f"Only {p.get('recent_review_count',0)} recent reviews in the last {recent_days} days (minimum {min_recent_reviews}). Results may be unreliable."
        else:
            p["recent_reviews_warning"] = False

    return processed


def example_flow():
    query = "coffee shop"
    location = None
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
        details["formatted_address"] = details.get("formatted_address") or c.get("formatted_address")
        details["rating"] = details.get("rating") or c.get("rating")
        details["user_ratings_total"] = details.get("user_ratings_total") or c.get("user_ratings_total")
        detailed.append(details)

    print("\nProcessing NLP focus scores for each place...")
    processed = process_places(detailed)

    for i, p in enumerate(processed, start=1):
        print(f"\n--- #{i}: {p.get('name')}")
        print("Focus score (0-100):", p.get("focus_score_0_100"))
        print("Average per-review score:", round(p.get("focus_average", 0), 3))
        print("Rating:", p.get("rating"), "(", p.get("review_count"), "reviews analyzed )")
        print("Address:", next((d.get("formatted_address") for d in detailed if d.get("place_id")==p.get("place_id")), "N/A"))
        print("Maps URL:", maps_url_for_place(p["place_id"]))

        score, raw_text, idx = top_contributing_review(p)
        if raw_text:
            print("Top contributing review (score:", round(score, 3), f", review_idx: {idx}):")
            print("  ", raw_text.replace("\n", " ").strip())
            per = p.get("per_review", [])
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
                    print("  Keywords found:")
                    for k, c in kw_list:
                        print(f"    - {k}: {c}")
        else:
            print("No contributing review found.")

    top_n = 5
    print(f"\nTop {top_n} places by study focus score:")
    for rank, top in enumerate(processed[:top_n], start=1):
        score, raw_text, idx = top_contributing_review(top)
        address = next((d.get("formatted_address") for d in detailed if d.get("place_id")==top.get("place_id")), "N/A")
        print(f"{rank}. {top.get('name')} — Score: {top.get('focus_score_0_100')} — Address: {address} — Maps: {maps_url_for_place(top.get('place_id'))}")
        if raw_text:
            print("   Top review (score", round(score,3), "):", raw_text.replace("\n", " ").strip())
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
