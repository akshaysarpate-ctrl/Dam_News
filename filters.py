"""Rule-based relevance filter. Cheap first pass; the optional AI check (classify.py)
refines what passes.

Score: dam word present +40, failure/inundation word present +40, exact query phrase
+20, each 'noise' word -30 (max -60). >=60 -> 'relevant', 40-59 -> 'maybe', else dropped.
A dam word is always required.
"""
import re
import unicodedata
from functools import lru_cache

import config

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh",
]
_STATE_ALIASES = {"orissa": "Odisha", "j&k": "Jammu and Kashmir", "jammu & kashmir": "Jammu and Kashmir"}
_STATE_RE = re.compile(
    r"\b(" + "|".join(re.escape(s.lower()) for s in
                      sorted(INDIAN_STATES + list(_STATE_ALIASES), key=len, reverse=True)) + r")\b"
)
_INDIA_RE = re.compile(r"\bindia\b|\bindian\b")


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").lower()


def _compile(terms):
    """ASCII terms match on word boundaries ('breach*' = prefix); other scripts by substring."""
    latin, other = [], []
    for term in terms:
        term = nfkc(term).strip()
        if not term:
            continue
        if term.isascii():
            if term.endswith("*"):
                latin.append(r"\b" + re.escape(term[:-1]) + r"\w*")
            else:
                latin.append(r"\b" + re.escape(term) + r"\b")
        else:
            other.append(re.escape(term))
    parts = latin + other
    return re.compile("|".join(parts)) if parts else None


@lru_cache(maxsize=None)
def _matchers(lang: str):
    cfg = config.LANGUAGES.get(lang, {})
    en = config.LANGUAGES["en"]
    dam = _compile(cfg.get("dam_terms", []) + en["dam_terms"])
    fail = _compile(cfg.get("failure_terms", []) + en["failure_terms"])
    strong = [nfkc(q) for q in cfg.get("queries", [])]
    return dam, fail, strong


_NEGATIVE = _compile(config.NEGATIVE_TERMS)


def detect_state(text: str) -> str:
    m = _STATE_RE.search(nfkc(text))
    if not m:
        return ""
    found = m.group(1)
    if found in _STATE_ALIASES:
        return _STATE_ALIASES[found]
    return next(s for s in INDIAN_STATES if s.lower() == found)


def evaluate(lang: str, title: str, snippet: str = ""):
    """Return (score, status, state) or None if the item should be dropped."""
    text = nfkc(f"{title} {snippet}")
    dam, fail, strong = _matchers(lang)
    if not (dam and dam.search(text)):
        return None
    score = 40
    if fail and fail.search(text):
        score += 40
    if any(q and q in text for q in strong):
        score += 20
    if _NEGATIVE:
        hits = {m.group(0) for m in _NEGATIVE.finditer(text)}
        score -= min(60, 30 * len(hits))
    state = detect_state(f"{title} {snippet}")
    # English results come from all over the world: without an India hint, cap at 'maybe'.
    if lang == "en" and not (state or _INDIA_RE.search(text)):
        score = min(score, 50)
    score = max(0, min(100, score))
    if score >= 60:
        return score, "relevant", state
    if score >= 40:
        return score, "maybe", state
    return None
