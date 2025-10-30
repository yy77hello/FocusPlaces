"""

 - Loads GOOGLE_PLACES_API_KEY from .env
 - Runs a Text Search for a query near a location (or by text)
 - Fetches Place Details (including reviews) for top candidates
 - Prints a short summary for each place

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

# Basic endpoints
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json" # Find candidates; text search for places by query, returns a list of place results with summary fields per place
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json" # Fetch detail info for a single place by place_id, we will use after we get candidate place_id's

# We'll need to run the search below multiple times and create a set of places

# Text Search to find candidate places
def text_search(query, location=None, radius=5000, max_results=10):
    """
    query: string, e.g., "coffee shop" or "library near Penn State"
    location: optional tuple (lat, lng)
    radius: meters
    max_results: number of place results to return (client-side limit)
    """
    params = { # included in api call to maps api endpoint
        "query": query,
        "key": API_KEY,
    }
    # If location provided, include location & radius to bias results
    if location:
        lat, lng = location
        params["location"] = f"{lat},{lng}"
        params["radius"] = radius

    resp = requests.get(TEXT_SEARCH_URL, params=params) # api call
    resp.raise_for_status() # check api response status
    data = resp.json() # store json response

    results = data.get("results", [])[:max_results] # Limit results to our limit of max results
    # Return info for each result
    candidates = []
    for r in results:
        candidates.append({ # transfer json inputs for each candidate into, list of dictionaries
            "name": r.get("name"),
            "place_id": r.get("place_id"),
            "rating": r.get("rating"),
            "user_ratings_total": r.get("user_ratings_total"),
            "location": r.get("geometry", {}).get("location"),
            "formatted_address": r.get("formatted_address"),
        })
    return candidates

# Place details, single place reviews
def fetch_place_details(place_id, max_reviews=5):
    """
    place_id: Google Place ID
    returns: dict with basic fields plus 'reviews' (list) if available
    """
    params = { # included in api call to maps api endpoint
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,formatted_address,geometry,reviews",
        "key": API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params) # api call
    resp.raise_for_status() # check api response status
    data = resp.json() # store json response
    result = data.get("result", {})
    reviews = []
    # Limit reviews to max_reviews and keep essential fields
    # Add each review to review list
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

# example flow: search -> fetch details -> print summary
def example_flow():
    query = "coffee shop"             # place type / query
    location = None                   # auto-detect, alternatively provide lat long
    radius = 10000                    # overwrite method parameter
    max_candidates = 5

    print("Searching for:", query)
    # call api through text_search
    candidates = text_search(query, location=location, radius=radius, max_results=max_candidates)
    print(f"Found {len(candidates)} candidates")

    # iterate over each candidate place to fetch detailed info and store into "detailed"
    detailed = []
    for c in candidates:
        pid = c["place_id"] # extract google place id
        time.sleep(0.1) # small pause to avoid hitting rate limits
        details = fetch_place_details(pid, max_reviews=3)
        detailed.append(details)

    # Print readable summaries
    for i, d in enumerate(detailed, start=1):
        print(f"\n--- #{i}: {d.get('name')}")
        print("Rating:", d.get("rating"), "(", d.get("user_ratings_total"), "ratings )")
        print("Address:", d.get("formatted_address"))
        print("Maps URL:", maps_url_for_place(d["place_id"]))
        if d.get("reviews"):
            print("Sample review excerpt:")
            # print the first review text truncated
            txt = d["reviews"][0].get("text", "")
            print("  ", (txt[:300] + "...") if len(txt) > 300 else "  " + txt)
        else:
            print("No reviews available.")

if __name__ == "__main__":
    example_flow()
