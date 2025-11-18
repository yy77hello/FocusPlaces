# streamlit_app.py (simple)
import streamlit as st
import os
from dotenv import load_dotenv
from places_api import geocode_address, search_and_process

st.write("Running Streamlit app…")

st.write(f"API_KEY loaded? {bool(os.getenv('GOOGLE_PLACES_API_KEY'))}")

load_dotenv()

st.set_page_config(page_title="Study Focus Finder", layout="wide")
st.title("Study Focus Finder — simple UI")

with st.sidebar:
    st.header("Search parameters")
    queries_text = st.text_area("Search queries (comma separated)", value="coffee shop, library, co-working space")
    location_input = st.text_input("Location (address) — optional", value="")
    latlng = None
    radius = st.slider("Radius (meters)", min_value=500, max_value=50000, value=10000, step=500)
    min_recent = st.number_input("Minimum recent reviews (keep but warn if less)", min_value=1, max_value=20, value=3)
    recent_days = st.number_input("Recent time window (days)", min_value=30, max_value=3650, value=365)
    max_candidates = st.number_input("Max candidates per query", min_value=1, max_value=50, value=10)
    max_reviews_per_place = st.number_input("Max reviews per place to fetch", min_value=1, max_value=20, value=5)
    run = st.button("Run search")

queries = [q.strip() for q in queries_text.split(",") if q.strip()]

if run:
    loc = None
    if location_input:
        try:
            g = geocode_address(location_input)
            if g:
                loc = g
                st.success(f"Geocoded to: {g[0]:.6f}, {g[1]:.6f}")
            else:
                st.warning("Could not geocode address; searches will be global/broad")
        except Exception as e:
            st.error(f"Geocoding failed: {e}")
    with st.spinner("Searching and processing (this may take a moment)..."):
        processed = search_and_process(queries, location=loc, radius=radius, max_candidates=max_candidates, max_reviews_per_place=max_reviews_per_place, recent_days=recent_days, min_recent_reviews=min_recent)
    if not processed:
        st.info("No places found for those queries/location.")
    else:
        st.write(f"Found {len(processed)} places (sorted by focus score)")
        for p in processed:
            cols = st.columns([3,1,1,1])
            name_display = p.get('name') or 'Unknown'
            with cols[0]:
                st.markdown(f"### {name_display}")
                st.write(p.get('formatted_address'))
                if p.get('recent_reviews_warning'):
                    st.warning(p.get('recent_reviews_warning_text'))
                st.write(f"Rating: {p.get('rating')} — Reviews analyzed: {p.get('review_count')} (recent: {p.get('recent_review_count')})")
                st.write(f"Focus score: **{p.get('focus_score_0_100')}**")
                with st.expander("Explainability & details"):
                    st.write("Top positive factors:", p.get('positive_factors'))
                    st.write("Top negative factors:", p.get('negative_factors'))
                    st.write("Keyword counts:", p.get('total_counts'))
                    st.write("Per-review details (recent only shown):")
                    for r in p.get('per_review', []):
                        if not r.get('is_recent'):
                            continue
                        st.markdown(f"**Review (score: {round(r.get('score',0),1)})** — {r.get('time')}")
                        st.write(r.get('raw_text'))
                        if r.get('explanations'):
                            st.write("Evidence:")
                            for e in r.get('explanations'):
                                st.write(f"- {e.get('keyword')} (weight {e.get('weight')}): {e.get('excerpt')}")
            with cols[1]:
                st.metric("Score", p.get('focus_score_0_100'))
            with cols[2]:
                st.write(" ")
            with cols[3]:
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{p.get('place_id')}"
                st.markdown(f"[Open in Google Maps]({maps_url})")