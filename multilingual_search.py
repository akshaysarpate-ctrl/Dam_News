"""Multilingual search engine for dam names and keywords.
Converts English names into all supported Indian languages and performs
>= 75% similarity matching across regional newspaper articles.
"""
import concurrent.futures
import difflib
import json
import logging
import re
import urllib.parse
import urllib.request
from functools import lru_cache

import config
import deep_search

log = logging.getLogger("multilingual_search")

# Google Input Tools Transliteration Codes for all supported languages
ITC_CODES = {
    "hi": "hi-t-i0-und",  # Hindi
    "mr": "mr-t-i0-und",  # Marathi
    "gu": "gu-t-i0-und",  # Gujarati
    "te": "te-t-i0-und",  # Telugu
    "ta": "ta-t-i0-und",  # Tamil
    "kn": "kn-t-i0-und",  # Kannada
    "ml": "ml-t-i0-und",  # Malayalam
    "bn": "bn-t-i0-und",  # Bengali
    "pa": "pa-t-i0-und",  # Punjabi
    "ur": "ur-t-i0-und",  # Urdu
    "or": "or-t-i0-und",  # Odia
    "as": "bn-t-i0-und",  # Assamese (uses Eastern Indic / Bengali script)
}

# Unicode Block base offsets from Devanagari (0x0900)
SCRIPT_OFFSETS = {
    "bn": 0x080,
    "as": 0x080,
    "pa": 0x100,
    "gu": 0x180,
    "or": 0x200,
    "ta": 0x280,
    "te": 0x300,
    "kn": 0x380,
    "ml": 0x400,
}

# Basic phonetic mapping to Devanagari for offline fallback
_PHONETIC_VOWELS = [
    ("aa", "\u093e"), ("ee", "\u0940"), ("ii", "\u0940"), ("oo", "\u0942"),
    ("uu", "\u0942"), ("ai", "\u0948"), ("au", "\u094c"), ("ou", "\u094c"),
    ("a", ""), ("i", "\u093f"), ("u", "\u0941"), ("e", "\u0947"), ("o", "\u094b"),
]

_PHONETIC_CONSONANTS = [
    ("kh", "\u0916"), ("gh", "\u0918"), ("ch", "\u091a"), ("chh", "\u091b"),
    ("jh", "\u091d"), ("th", "\u0925"), ("dh", "\u0927"), ("ph", "\u092b"),
    ("bh", "\u092d"), ("sh", "\u0936"), ("k", "\u0915"), ("g", "\u0917"),
    ("j", "\u091c"), ("t", "\u0924"), ("d", "\u0926"), ("n", "\u0928"),
    ("p", "\u092a"), ("f", "\u092b"), ("b", "\u092c"), ("m", "\u092e"),
    ("y", "\u092f"), ("r", "\u0930"), ("l", "\u0932"), ("v", "\u0935"),
    ("w", "\u0935"), ("s", "\u0938"), ("h", "\u0939")
]


def _offline_transliterate_devanagari(word: str) -> str:
    """Simple rule-based phonetic transliteration from Latin script to Devanagari."""
    w = word.lower().strip()
    if not w:
        return ""
    res = []
    i = 0
    n = len(w)
    while i < n:
        # Match consonant
        matched_c = None
        for pat, char in _PHONETIC_CONSONANTS:
            if w.startswith(pat, i):
                matched_c = char
                i += len(pat)
                break
        if matched_c:
            res.append(matched_c)
            # Check following vowel
            matched_v = None
            for pat, char in _PHONETIC_VOWELS:
                if w.startswith(pat, i):
                    matched_v = char
                    i += len(pat)
                    break
            if matched_v is not None:
                if matched_v:
                    res.append(matched_v)
            else:
                # Inherent schwa or virama at end
                if i < n and w[i].isalpha():
                    res.append("\u094d")  # virama
            continue

        # Standalone vowel
        matched_v = None
        for pat, _ in _PHONETIC_VOWELS:
            if w.startswith(pat, i):
                matched_v = pat
                i += len(pat)
                break
        if matched_v:
            # Standalone initial vowels
            init_map = {
                "a": "\u0905", "aa": "\u0906", "i": "\u0907", "ii": "\u0908", "ee": "\u0908",
                "u": "\u0909", "uu": "\u090a", "oo": "\u090a", "e": "\u090f", "ai": "\u0910",
                "o": "\u0913", "au": "\u0914", "ou": "\u0914"
            }
            res.append(init_map.get(matched_v, "\u0905"))
            continue

        # Skip non-alpha
        if not w[i].isalpha():
            res.append(w[i])
        i += 1

    return "".join(res)


def _devanagari_to_script(dev_text: str, offset: int) -> str:
    """Shift Devanagari Unicode characters to another Indic Unicode block."""
    out = []
    for ch in dev_text:
        c = ord(ch)
        if 0x0900 <= c <= 0x097F:
            out.append(chr(c + offset))
        else:
            out.append(ch)
    return "".join(out)


def _fetch_inputtools(word: str, code: str, itc: str) -> tuple[str, list[str]]:
    """Fetch transliteration from Google Input Tools API."""
    try:
        url = "https://inputtools.google.com/request?" + urllib.parse.urlencode({
            "text": word, "itc": itc, "num": "3", "cp": "0", "cs": "1",
            "ie": "utf-8", "oe": "utf-8", "app": "demopage"
        })
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data[0] == "SUCCESS" and len(data) > 1 and data[1]:
                variants = data[1][0][1]
                return code, variants
    except Exception as e:
        log.debug("Inputtools fetch error for %s (%s): %s", word, code, e)
    return code, []


# Memory cache for converted names
_CONVERSION_CACHE: dict[str, dict[str, list[str]]] = {}


def convert_name_to_all_languages(raw_name: str) -> dict[str, list[str]]:
    """Convert an English dam/place name into representations across all 12 supported languages.
    Returns: { 'en': ['Kalyani'], 'hi': ['कल्याणी', ...], 'mr': ['कल्याणी', ...], ... }
    """
    clean = " ".join(raw_name.strip().split())
    if not clean:
        return {}

    base_name, _ = deep_search.clean_search_name(clean)
    cache_key = base_name.lower()
    if cache_key in _CONVERSION_CACHE:
        return _CONVERSION_CACHE[cache_key]

    results: dict[str, list[str]] = {
        "en": [base_name]
    }
    if clean.lower() != base_name.lower():
        results["en"].append(clean)

    # 1. Fetch via Google Input Tools in parallel
    words = base_name.split()
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for code, itc in ITC_CODES.items():
            tasks.append(pool.submit(_fetch_inputtools, base_name, code, itc))
        for f in concurrent.futures.as_completed(tasks):
            code, variants = f.result()
            if variants:
                results[code] = variants

    # 2. Offline fallback for any language that didn't return
    dev_fallback = _offline_transliterate_devanagari(base_name)
    if dev_fallback:
        if "hi" not in results:
            results["hi"] = [dev_fallback]
        if "mr" not in results:
            results["mr"] = [dev_fallback]
        for code, offset in SCRIPT_OFFSETS.items():
            if code not in results:
                script_form = _devanagari_to_script(dev_fallback, offset)
                if script_form:
                    results[code] = [script_form]

    _CONVERSION_CACHE[cache_key] = results
    return results


def get_all_search_tokens(converted: dict[str, list[str]]) -> list[str]:
    """Extract unique search tokens/phrases across all languages for query matching."""
    tokens = []
    seen = set()
    for lang, variants in converted.items():
        for v in variants:
            v_clean = v.strip()
            if v_clean and v_clean.lower() not in seen:
                seen.add(v_clean.lower())
                tokens.append(v_clean)
    return tokens


def calculate_75_match(converted: dict[str, list[str]], text: str) -> tuple[float, bool, str]:
    """Check if the text (e.g. title + snippet) matches the converted name by at least 75%.
    Returns (score_pct, is_match, matched_term).
    """
    if not text or not converted:
        return 0.0, False, ""

    text_lower = text.lower()
    best_score = 0.0
    best_term = ""

    # Tokenize words from text (including Latin and Indic Unicode scripts)
    text_words = re.findall(r"[\w\u0900-\u0d7f]+", text, flags=re.UNICODE)
    text_words_lower = [w.lower() for w in text_words]

    for lang, variants in converted.items():
        for target in variants:
            t_clean = target.strip()
            if not t_clean:
                continue
            t_lower = t_clean.lower()

            # 1. Exact substring match in text -> 100%
            if t_lower in text_lower:
                return 100.0, True, t_clean

            target_words = t_lower.split()
            # If multi-word target (e.g. 'सरदार सरोवर' or 'sardar sarovar')
            if len(target_words) > 1:
                # Check sliding window of same length
                win_len = len(target_words)
                for i in range(len(text_words_lower) - win_len + 1):
                    window = " ".join(text_words_lower[i : i + win_len])
                    ratio = difflib.SequenceMatcher(None, t_lower, window).ratio() * 100.0
                    if ratio > best_score:
                        best_score = ratio
                        best_term = t_clean
                        if best_score >= 100.0:
                            return 100.0, True, best_term

                # Token-level overlap
                word_scores = []
                for tw in target_words:
                    tw_best = 0.0
                    for cw in text_words_lower:
                        if tw in cw or cw in tw:
                            r = (min(len(tw), len(cw)) / max(len(tw), len(cw))) * 100.0
                            tw_best = max(tw_best, r)
                        r2 = difflib.SequenceMatcher(None, tw, cw).ratio() * 100.0
                        tw_best = max(tw_best, r2)
                    word_scores.append(tw_best)
                combo = sum(word_scores) / len(word_scores) if word_scores else 0.0
                if combo > best_score:
                    best_score = combo
                    best_term = t_clean

            else:
                # Single-word target: compare against each word in text
                for cw in text_words_lower:
                    if t_lower in cw or cw in t_lower:
                        # Substring in token (e.g. inflected suffix 'मुल्लापेरियारला')
                        ratio = (min(len(t_lower), len(cw)) / max(len(t_lower), len(cw))) * 100.0
                        if ratio > best_score:
                            best_score = ratio
                            best_term = t_clean
                    r = difflib.SequenceMatcher(None, t_lower, cw).ratio() * 100.0
                    if r > best_score:
                        best_score = r
                        best_term = t_clean

    is_match = best_score >= 75.0
    return round(best_score, 1), is_match, best_term
