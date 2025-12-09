# FocusPlaces

[//]: # (<img src="logo.jpg" width="30%">)

FocusPlaces helps students find the best spots for focused work by combining Google Places data with review text analysis to produce a transparent "focus score" and objective explanations.

## Quick Start (Windows)
1. Clone the repo:
   git clone https://github.com/yy77hello/FocusPlaces/
2. Create & activate a Python virtual environment (recommended)
   - Open PowerShell and run:
     python -m venv venv
     .\venv\Scripts\Activate.ps1
   - If using Command Prompt (cmd.exe):
     python -m venv venv
     .\venv\Scripts\activate.bat
   - Python 3.10 is recommended
3. Create a Google Cloud Project and enable:
   - Places API
   - Maps Embed API
   - Geocoding API
4. Add your API key to a local `.env` file in the project root:
   GOOGLE_PLACES_API_KEY=your_api_key_here
5. Install dependencies:
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   (If requirements.txt already includes all packages you can skip the next two extra pip install lines.)
   pip install spacy python-dotenv requests
   pip install requests python-dotenv spacy streamlit
6. Download the spaCy English model:
   python -m spacy download en_core_web_sm
7. Ensure all Python files (nlp_review_processor.py, streamlit_app.py, and the main script) are in the same directory.
8. Run the app:
   streamlit run .\streamlit_app.py
9. A web browser window will open and the app is ready to use. Place preferences and other settings can be configured in the Streamlit UI.

## How it works
- Search for candidate locations via Google Places (search terms like "coffee shop", "library", "co‑working space") with a max candidate counter for users to change.
- Compute a "focus score" for each place combining Google rating and frequency of study‑relevant keywords in recent reviews.
- Settings allow users to define custom query keywords, set how recent reviews must be to be considered, set a minimum number of recent reviews required for a score to be considered reliable, enter a custom location and radius, choose maximum candidates per query (e.g., 5 will return 5 places for "library", 5 places for "co‑working space", etc.), and set the maximum reviews per place to fetch.
- Extract review excerpts that contain matched keywords for explainability.
- UI with progress feedback and a results page showing scores & explanations.
- Allows users to enter a specific address to start from (default = current location)


## Files
- nlp_review_processor.py: computes per‑review and per‑place "focus" scores from review text (requires spaCy/en_core_web_sm).
- <your_second_file>.py: queries Google Places, fetches place details (including reviews), and uses the NLP processor to produce and print results.
- requirements.txt: Python dependency list.
- streamlit_app.py: the UI frontend for the main file.

## Notes
- Ensure your Google Places API key has billing enabled and the necessary APIs turned on.
- Reviews returned by the Places Details endpoint are limited; the script fetches up to a configurable number of recent reviews per place.
