# FocusPlaces

<img src="logo.jpg" width="30%">

FocusPlaces helps students find the best spots for focused work (cafes, libraries, co‑working spaces) by combining Google Places data with review text analysis and user preferences to produce a transparent "focus score" and human‑readable explanations.

## Features
- Search for candidate locations via Google Places (search terms like "coffee shop", "library", "co‑working space").
- Compute a "focus score" for each place combining Google rating and frequency of study‑relevant keywords in recent reviews.
- Let users set preference weights that adjust the heuristic.
- Extract review excerpts that contain matched keywords for explainability.
- Streamlit UI with progress feedback and a results page showing scores, explanations, and an embedded clickable map.

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
3. Create a Google Cloud Project and enable:
   - Places API
   - Maps Embed API
4. Add your API key to a local `.env` file in the project root:
   GOOGLE_PLACES_API_KEY=your_api_key_here
5. Install dependencies:
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install spacy python-dotenv requests
   (If requirements.txt already includes all packages you can skip the extra pip install line.)
6. Download the spaCy English model:
   python -m spacy download en_core_web_sm
   (Alternatively, for offline environments install a model wheel:
   pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.5.0/en_core_web_sm-3.5.0-py3-none-any.whl)
7. Ensure both Python files (nlp_review_processor.py and the main script) are in the same directory, then run:
   python your_second_file.py

## Configuration
- Place preferences and weighting adjustments can be configured in the preferences section of the Streamlit UI or by editing the config file (if provided).

## Files
- nlp_review_processor.py: computes per‑review and per‑place "focus" scores from review text (requires spaCy/en_core_web_sm).
- <your_second_file>.py: queries Google Places, fetches place details (including reviews), and uses the NLP processor to produce and print results.
- requirements.txt: Python dependency list.

## Notes
- Ensure your Google Places API key has billing enabled and the necessary APIs turned on.
- Reviews returned by the Places Details endpoint are limited; the script fetches up to a small number of recent reviews per place.
