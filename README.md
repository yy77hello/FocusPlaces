# FocusPlaces

<img src="logo.jpg" width="30%">

FocusPlaces helps students find the best spots for focused work (cafes, libraries, co‑working spaces) by combining Google Places data with review text analysis and user preferences to produce a transparent "focus score" and human‑readable explanations.

## Features
- Search for candidate locations via Google Places (search terms like "coffee shop", "library", "co‑working space").
- Compute a "focus score" for each place combining Google rating and frequency of study‑relevant keywords in recent reviews.
- Let users set preference weights that adjust the heuristic.
- Extract review excerpts that contain matched keywords for explainability.
- Streamlit UI with progress feedback and a results page showing scores, explanations, and an embedded clickable map.

## Quick Start
1. Clone the repo:
   git clone https://github.com/yy77hello/FocusPlaces/
2. Create a Google Cloud Project and enable:
   - Places API
   - Maps Embed API
3. Add your API key to a local environment variable located in the .env file
4. Install dependencies:
   pip install -r requirements.txt

