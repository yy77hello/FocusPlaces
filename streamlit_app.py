# streamlit_app.py
import streamlit as st
import os
from dotenv import load_dotenv
from places_api import geocode_address, search_and_process
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if API_KEY:
    st.success("API_KEY loaded")
else:
    st.error("API_KEY not found — please check your .env file and ensure GOOGLE_PLACES_API_KEY is set")

st.set_page_config(page_title="FocusPlaces", layout="wide")
st.title("FocusPlaces")

st.markdown(
    """
    <div style="margin-top:-8px; margin-bottom:18px;">
      <p style="font-size:18px; color:#6b7280; margin:0; max-width:900px;">
        Start your search for the best nearby study spots, ranked from real user reviews to help you focus.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

controls_col, results_col = st.columns([1, 2.2])

with controls_col:
    st.header("Search parameters")
    queries_text = st.text_area(
        "Search queries (comma separated)",
        value="coffee shop, library, co-working space",
    )
    st.caption("If left blank, default queries (coffee shop, library, co‑working space) will be used.")
    location_input = st.text_input("Location (address) — optional", value="")
    st.caption("If left empty, FocusPlaces will attempt to use current location if available.")
    radius_miles = st.number_input(
        "Radius (miles)",
        min_value=0.1,
        max_value=50.0,
        value=7.5,
        step=0.1,
        format="%.1f",
    )
    radius = int(radius_miles * 1609.344)
    recent_days = st.number_input(
        "Recent time window (days)",
        min_value=30,
        max_value=3650,
        value=365,
    )
    st.caption("Only reviews from the last N days are counted as 'recent' when computing recent-review statistics and the focus score.")
    min_recent = st.number_input(
        "Minimum recent reviews (warning threshold)",
        min_value=1,
        max_value=20,
        value=3,
    )
    st.caption("If a place has fewer than this many recent reviews, results may be less reliable.")
    max_candidates = st.number_input("Max candidates per query", min_value=1, max_value=50, value=10)
    max_reviews_per_place = st.number_input("Max reviews per place to fetch", min_value=1, max_value=20, value=5)

    run = st.button("Run search")
    st.markdown("<small style='color:#6b7280;'>Tip: adjust parameters to broaden or narrow your results.</small>", unsafe_allow_html=True)

with results_col:
    st.empty()

queries = [q.strip() for q in queries_text.split(",") if q.strip()]
if not queries:
    queries = ["coffee shop", "library", "co-working space"]

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
        processed = search_and_process(
            queries,
            location=loc,
            radius=radius,
            max_candidates=max_candidates,
            max_reviews_per_place=max_reviews_per_place,
            recent_days=recent_days,
            min_recent_reviews=min_recent,
        )

    if not processed:
        st.info("No places found for those queries/location.")
    else:
        # Render results using a card like style for each place
        st.write(f"Found {len(processed)} places (sorted by focus score)")
        for p in processed:
            cols = st.columns([3,1,1,1])
            name_display = p.get("name") or "Unknown"
            with cols[0]:
                # Card header with subtle divider
                st.markdown(f"### {name_display}")
                st.markdown(f"<div style='color:#6b7280; margin-bottom:6px;'>{p.get('formatted_address') or 'Address: not available'}</div>", unsafe_allow_html=True)
                if p.get("recent_reviews_warning"):
                    st.warning(p.get("recent_reviews_warning_text"))
                st.markdown(f"<div style='margin-top:6px; margin-bottom:6px; color:#374151;'>Rating: <strong>{p.get('rating')}</strong> — Reviews analyzed: <strong>{p.get('review_count')}</strong> (recent: <strong>{p.get('recent_review_count')}</strong>)</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:20px; margin-bottom:6px;'>Focus score: <strong>{p.get('focus_score_0_100')}</strong></div>", unsafe_allow_html=True)
                with st.expander("Explainability & details"):
                    def normalize_pairs(obj):
                        if obj is None:
                            return []
                        if isinstance(obj, dict):
                            return sorted(obj.items(), key=lambda x: -x[1])
                        if isinstance(obj, list):
                            items = []
                            for elem in obj:
                                if isinstance(elem, (list, tuple)) and len(elem) >= 2:
                                    items.append((str(elem[0]), int(elem[1])))
                                elif isinstance(elem, dict):
                                    if "keyword" in elem and "count" in elem:
                                        items.append((str(elem["keyword"]), int(elem["count"])))
                                    else:
                                        keys = list(elem.keys())
                                        if len(keys) >= 2:
                                            items.append((str(elem[keys[0]]), int(elem[keys[1]])))
                            return sorted(items, key=lambda x: -x[1])
                        try:
                            return sorted([(str(k), int(v)) for k, v in obj], key=lambda x: -x[1])
                        except Exception:
                            return []

                    pos = normalize_pairs(p.get("positive_factors"))
                    neg = normalize_pairs(p.get("negative_factors"))
                    total = normalize_pairs(p.get("keyword_counts"))

                    st.write("Top positive factors:")
                    if pos:
                        for kw, cnt in pos:
                            st.write(f"- **{kw}**: {cnt}")
                    else:
                        st.write("_None detected_")

                    st.write("Top negative factors:")
                    if neg:
                        for kw, cnt in neg:
                            st.write(f"- **{kw}**: {cnt}")
                    else:
                        st.write("_None detected_")

                    st.write("Per-review details (recent only shown):")
                    for r in p.get("per_review", []):
                        if not r.get("is_recent"):
                            continue
                        t = r.get("time")
                        pretty_date = ""
                        if isinstance(t, (int, float)):
                            try:
                                pretty_date = datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d")
                            except Exception:
                                pretty_date = str(t)
                        else:
                            try:
                                parsed = datetime.fromisoformat(str(t))
                                pretty_date = parsed.date().isoformat()
                            except Exception:
                                pretty_date = str(t).split("T")[0] if "T" in str(t) else str(t)
                        st.markdown(f"**Review (score: {round(r.get('score',0),1)})** — {pretty_date}")
                        st.write(r.get("raw_text"))
                        if r.get("explanations"):
                            st.write("Evidence:")
                            for e in r.get("explanations"):
                                st.write(f"- {e.get('keyword')} (weight {e.get('weight')}): {e.get('excerpt')}")
            with cols[1]:
                st.metric("Score", p.get("focus_score_0_100"))
            with cols[2]:
                st.write(" ")
            with cols[3]:
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{p.get('place_id')}"
                st.markdown(f"[Open in Google Maps]({maps_url})")
