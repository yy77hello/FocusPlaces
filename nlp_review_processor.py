# nlp_review_processor.py
"""
NLP Review Processing for "study suitability" focus score.

Outputs:
 - per-review score in 0..100
 - place average score in 0..100 as 'focus_score_0_100'

Requirements:
   pip install spacy
   python -m spacy download en_core_web_sm
"""

import re
from collections import Counter, defaultdict
import math
import spacy
import datetime

nlp = spacy.load("en_core_web_sm", disable=["ner"])  # small model

KEYWORD_WEIGHTS = {
    "quiet": ("quiet", 3.0), "quietly": ("quiet", 3.0), "noise": ("noise", -2.5), "noisy": ("noise", -3.0),
    "loud": ("noise", -3.0), "calm": ("quiet", 2.0), "peaceful": ("quiet", 2.5),
    "wifi": ("wifi", 3.0), "wi-fi": ("wifi", 3.0), "internet": ("wifi", 2.5), "connection": ("wifi", 1.5),
    "outlet": ("outlet", 3.0), "outlets": ("outlet", 3.0), "plug": ("outlet", 2.5), "power": ("outlet", 1.5),
    "comfortable": ("comfort", 2.5), "comfort": ("comfort", 2.0), "seat": ("comfort", 1.5), "seating": ("comfort", 1.5),
    "chairs": ("comfort", 1.5), "chair": ("comfort", 1.5), "ergonomic": ("comfort", 2.5), "cozy": ("comfort", 1.5),
    "lighting": ("lighting", 2.0), "bright": ("lighting", 1.5), "dim": ("lighting", -1.0), "well-lit": ("lighting", 2.0),
    "dark": ("lighting", -1.5),
    "study": ("study", 3.0), "focused": ("study", 2.5), "focus": ("study", 2.5), "productive": ("study", 2.5),
    "productivity": ("study", 2.0),
    "laptop": ("laptop", 2.5), "laptops": ("laptop", 2.5), "work": ("work", 2.0), "workspace": ("work", 2.5),
    "desk": ("work", 2.0),
    "tables": ("tables", 1.5), "table": ("tables", 1.5), "restroom": ("amenities", 0.5), "bathroom": ("amenities", 0.5),
    "outdoor": ("outdoor", 0.5),
    "friendly": ("staff", 1.0), "helpful": ("staff", 1.0), "rude": ("staff", -1.5),
    "crowded": ("crowded", -2.5), "busy": ("crowded", -1.5), "packed": ("crowded", -2.0), "empty": ("crowded", 1.0),
    "coffee": ("coffee", 0.5), "food": ("food", 0.0), "kids": ("family", -1.5), "children": ("family", -1.5),
    "cold": ("temperature", -0.5), "hot": ("temperature", -0.5),
    "open-late": ("hours", 0.5), "open late": ("hours", 0.5), "24/7": ("hours", 1.0), "hours": ("hours", 0.2),
    "reservations": ("reservations", 0.5), "parking": ("parking", 0.2), "plugged": ("outlet", 2.5),
}

PUNCT_RE = re.compile(r"[^\w\s\-/]")


def normalize_text(text):
    if not text:
        return ""
    t = text.lower()
    t = PUNCT_RE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def excerpt_around(text, start, end, max_chars=120):
    s = max(0, start - max_chars)
    e = min(len(text), end + max_chars)
    excerpt = text[s:e].strip()
    if s > 0:
        excerpt = "..." + excerpt
    if e < len(text):
        excerpt = excerpt + "..."
    return excerpt


def _map_to_0_100(normalized_value, a=0.6):
    sig = 1.0 / (1.0 + math.exp(-a * normalized_value))
    return sig * 100.0


def find_matches(doc, original_text):
    matches = []
    norm = normalize_text(original_text)
    keys_sorted = sorted(KEYWORD_WEIGHTS.keys(), key=lambda k: -len(k))
    for key in keys_sorted:
        key_norm = normalize_text(key)
        pattern = r"\b" + re.escape(key_norm) + r"\b"
        for m in re.finditer(pattern, norm):
            start, end = m.span()
            try:
                orig_start = original_text.lower().index(norm[start:end])
                orig_end = orig_start + (end - start)
            except ValueError:
                orig_start, orig_end = 0, 0
            canon = KEYWORD_WEIGHTS[key][0]
            matches.append((canon, original_text[orig_start:orig_end], orig_start, orig_end, key))
    for token in doc:
        lemma = token.lemma_.lower()
        if lemma in KEYWORD_WEIGHTS:
            canon = KEYWORD_WEIGHTS[lemma][0]
            matches.append((canon, token.text, token.idx, token.idx + len(token.text), lemma))
        surf = token.text.lower()
        if surf in KEYWORD_WEIGHTS:
            canon = KEYWORD_WEIGHTS[surf][0]
            matches.append((canon, token.text, token.idx, token.idx + len(token.text), surf))
    # dedupe
    seen = set()
    uniq = []
    for m in matches:
        key = (m[0], m[2], m[3])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(m)
    return uniq


def score_review(review_text):
    norm_text = normalize_text(review_text)
    if not norm_text:
        return {
            "score": 50.0,
            "counts": {},
            "keywords": [],
            "explanations": [],
        }
    doc = nlp(review_text)
    matches = find_matches(doc, review_text)
    if not matches:
        return {
            "score": 50.0,
            "counts": {},
            "keywords": [],
            "explanations": [],
        }
    counts = Counter()
    raw_score = 0.0
    explanations = []
    for canon, span_text, start, end, surf in matches:
        # find any weight for this surface key; fall back to canon mapping
        weight = None
        if surf in KEYWORD_WEIGHTS:
            weight = KEYWORD_WEIGHTS[surf][1]
        else:
            # find first k with matching canonical
            for k, v in KEYWORD_WEIGHTS.items():
                if v[0] == canon:
                    weight = v[1]
                    break
        if weight is None:
            continue
        counts[canon] += 1
        raw_score += weight
        explanations.append({
            "keyword": canon,
            "matched": span_text,
            "surface": surf,
            "weight": weight,
            "excerpt": excerpt_around(review_text, start, end, max_chars=80),
            "span": (start, end),
        })
    word_count = len([t for t in doc if not t.is_punct and not t.is_space])
    length_factor = math.log1p(word_count) if word_count > 0 else 1.0
    normalized = raw_score / length_factor
    score_0_100 = _map_to_0_100(normalized, a=0.6)
    score_0_100 = max(0.0, min(100.0, score_0_100))
    keyword_list = list(counts.items())
    return {
        "score": score_0_100,
        "counts": dict(counts),
        "keywords": keyword_list,
        "explanations": explanations,
    }


def process_place_reviews(place, recent_days=365):
    reviews = place.get("reviews", []) or []
    per_review = []
    total = 0.0
    total_counts = Counter()
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=recent_days)

    for i, rev in enumerate(reviews):
        text = rev.get("text", "") if isinstance(rev, dict) else str(rev)
        # Google's review object may include 'time' (unix epoch)
        review_time = None
        if isinstance(rev, dict):
            t = rev.get("time")
            if isinstance(t, (int, float)):
                try:
                    review_time = datetime.datetime.utcfromtimestamp(int(t))
                except Exception:
                    review_time = None
        # include review if no time provided (conservative: include) or if recent
        is_recent = True if review_time is None else (review_time >= cutoff)
        scored = score_review(text)
        per_review.append({
            "index": i,
            "score": scored.get("score"),
            "counts": scored.get("counts"),
            "keywords": scored.get("keywords"),
            "explanations": scored.get("explanations"),
            "raw_text": text,
            "time": review_time.isoformat() if review_time else None,
            "is_recent": is_recent,
        })
        # aggregate only recent reviews into the place-level score
        if is_recent:
            total += scored.get("score", 50.0)
            total_counts.update(scored.get("counts", {}))

    recent_review_count = sum(1 for r in per_review if r.get("is_recent"))
    review_count = len(reviews)
    review_count_for_average = recent_review_count if recent_review_count > 0 else 1
    average = total / review_count_for_average

    # build explainability summary
    pos = []
    neg = []
    for k, cnt in total_counts.items():
        # find a representative weight for the canonical keyword
        weight = None
        for kk, vv in KEYWORD_WEIGHTS.items():
            if vv[0] == k:
                weight = vv[1]
                break
        if weight is None:
            weight = 0.0
        score_contrib = weight * cnt
        if score_contrib >= 0:
            pos.append((k, cnt, score_contrib))
        else:
            neg.append((k, cnt, score_contrib))
    pos.sort(key=lambda x: -x[2])
    neg.sort(key=lambda x: x[2])

    result = {
        "place_id": place.get("place_id"),
        "name": place.get("name"),
        "focus_raw_score": total,
        "focus_average": average,
        "focus_score_0_100": int(round(max(0.0, min(100.0, average)))),
        "keyword_counts": dict(total_counts),
        "positive_factors": [(k, c) for k, c, s in pos],
        "negative_factors": [(k, c) for k, c, s in neg],
        "per_review": per_review,
        "review_count": review_count,
        "recent_review_count": recent_review_count,
    }
    return result


def process_places(places, recent_days=365):
    processed = []
    for p in places:
        processed.append(process_place_reviews(p, recent_days=recent_days))
    processed.sort(key=lambda x: x.get("focus_score_0_100", 0), reverse=True)
    return processed