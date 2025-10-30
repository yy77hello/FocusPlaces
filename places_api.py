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

# Text Search to find candidate places
def text_search(query, location=None, radius=5000, max_results=10):
