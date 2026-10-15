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
_INDIA_RE = re.compile(r"\b(india|indian|bharat|hindustan|cwc|ndsa|sdso)\b", re.IGNORECASE)

FOREIGN_DAMS = [
    "three gorges", "hoover dam", "oroville", "kakhovka", "nova kakhovka", "kariba", "aswan",
    "tarbela", "mangla", "diamer", "bhasha", "brumadinho", "mariana dam", "bento rodrigues",
    "matai'an", "banqiao", "itaipu", "tucurui", "guri dam", "grand renaissance", "gerd dam",
    "bagre dam", "luzon", "fontana dam", "rutland water", "fujinuma", "kunfusi", "lac qui parle",
    "fukushima", "chornobyl", "chernobyl", "dagestan", "alaska", "michigan", "arizona",
]
_FOREIGN_DAM_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in FOREIGN_DAMS) + r")\b", re.IGNORECASE)

FOREIGN_COUNTRIES = [
    "china", "chinese", "pakistan", "pakistani", "ukraine", "ukrainian", "russia", "russian",
    "brazil", "brazilian", "united states", "usa", "america", "american", "california", "texas",
    "florida", "australia", "australian", "canada", "canadian", "japan", "japanese", "taiwan",
    "taiwanese", "indonesia", "indonesian", "philippines", "turkey", "turkish", "syria", "syrian",
    "iraq", "iran", "mexico", "colombia", "argentina", "spain", "germany", "italy",
    "britain", "british", "england", "scotland", "egypt", "ethiopia", "kenya", "sudan", "zambia",
    "zimbabwe", "ghana", "myanmar", "burma", "thailand", "vietnam", "laos", "cambodia", "kazakhstan",
]
_FOREIGN_COUNTRY_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in FOREIGN_COUNTRIES) + r")\b", re.IGNORECASE)

INDIAN_CITIES = [
    "mumbai", "pune", "nagpur", "nashik", "aurangabad", "kolhapur", "solapur", "thane",
    "gondia", "tiroda", "tirora", "bhandara", "gadchiroli", "chandrapur", "amravati", "yavatmal", "wardha",
    "गोंदिया", "तिरोडा", "तिरोरा", "भंडारा", "गडचिरोली", "चंद्रपूर",
    "ahmedabad", "surat", "vadodara", "rajkot", "bhavnagar", "jamnagar", "junagadh", "gandhinagar", "morbi", "kutch",
    "jaipur", "jodhpur", "kota", "bikaner", "ajmer", "udaipur", "bhilwara", "alwar", "sikar",
    "bhopal", "indore", "gwalior", "jabalpur", "ujjain", "sagar", "dewas", "satna", "rewa",
    "patna", "gaya", "bhagalpur", "muzaffarpur", "purnia", "darbhanga",
    "lucknow", "kanpur", "ghaziabad", "agra", "meerut", "varanasi", "prayagraj", "bareilly", "aligarh", "moradabad", "saharanpur", "gorakhpur", "noida", "jhansi",
    "dehradun", "haridwar", "rishikesh", "roorkee", "haldwani", "rudrapur", "nainital", "tehri", "uttarkashi", "chamoli",
    "shimla", "mandi", "dharamshala", "solan", "kullu", "manali", "bilaspur", "chamba", "kangra", "kinnaur",
    "srinagar", "jammu", "anantnag", "baramulla", "udhampur", "leh", "kargil", "kishtwar", "doda", "ramban", "reasi",
    "bengaluru", "bangalore", "mysuru", "mysore", "hubballi", "dharwad", "mangaluru", "mangalore", "belagavi", "belgaum", "kalaburagi", "davanagere", "ballari", "vijayapura", "shivamogga", "shimoga", "tumakuru", "raichur", "bidar", "hassan",
    "hyderabad", "warangal", "nizamabad", "khammam", "karimnagar", "ramagundam", "mahbubnagar", "nalgonda", "adilabad", "suryapet",
    "chennai", "coimbatore", "madurai", "tiruchirappalli", "salem", "tirunelveli", "tiruppur", "erode", "vellore", "thoothukudi", "dindigul", "thanjavur",
    "thiruvananthapuram", "kochi", "cochin", "kozhikode", "calicut", "thrissur", "kollam", "palakkad", "alappuzha", "malappuram", "kannur", "kottayam", "idukki", "wayanad", "pathanamthitta", "kasaragod",
    "bhubaneswar", "cuttack", "rourkela", "berhampur", "sambalpur", "puri", "balasore",
    "kolkata", "howrah", "asansol", "siliguri", "durgapur", "bardhaman", "malda", "kharagpur",
    "guwahati", "silchar", "dibrugarh", "jorhat", "nagaon", "tinsukia", "tezpur",
    "raipur", "bhilai", "korba", "durg", "ranchi", "jamshedpur", "dhanbad", "bokaro",
    "ludhiana", "amritsar", "jalandhar", "patiala", "bathinda", "mohali", "pathankot",
    "faridabad", "gurugram", "gurgaon", "panipat", "ambala", "yamunanagar", "rohtak", "hisar", "karnal", "sonipat"
]
_INDIAN_CITIES_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in INDIAN_CITIES) + r")\b", re.IGNORECASE)

INDIAN_RIVERS = [
    "ganga", "ganges", "yamuna", "godavari", "krishna", "narmada", "mahanadi", "cauvery", "kaveri",
    "brahmaputra", "tapi", "tapti", "sabarmati", "mahi", "periyar", "pennar", "subarnarekha",
    "beas", "sutlej", "ravi", "chenab", "jhelum", "tungabhadra", "bhima", "koyna", "vaigai",
    "damodar", "teesta", "chambal", "betwa", "kosi", "ghaghara", "gandak", "bhagirathi", "alaknanda", "aravali"
]
_INDIAN_RIVERS_RE = re.compile(r"\b(" + "|".join(re.escape(r) for r in INDIAN_RIVERS) + r")\b", re.IGNORECASE)

# AI & Synthetic / Simulation / Fictional Content Patterns
# AI & Synthetic / Simulation / Fictional Content Patterns
AI_PATTERNS = [
    r"\bai\b",
    r"\bai[- ]generated\b",
    r"\bai[- ]animation\b",
    r"\bai\s*(pics?|photos?|images?|तस्वीर|तस्वीरें|चित्र|video|वीडियो|story|stories)",
    r"\bartificial intelligence\b",
    r"आर्टिफिशियल इंटेलिजेंस",
    r"\bcgi\b",
    r"\bsimulation\b",
    r"\bsimulator\b",
    r"\bdeepfake\b",
    r"\bmidjourney\b",
    r"\bdall[- ]e\b",
    r"\bsora\b",
    r"\brunway\b",
    r"\bchatgpt\b",
    r"\bopenai\b",
    r"\bsynthetic\b",
    r"\bunreal engine\b",
    r"\bblender\b",
    r"\b3d animation\b",
    r"\b2d\s*(hindi\s*)?story\b",
    r"\b2d animation\b",
    r"\blego\b",
    r"\bminecraft\b",
    r"\broblox\b",
    r"\bgta\b",
    r"\bbeamng\b",
    r"\bteardown\b",
    r"\bhypothetical\b",
    r"\bwhat if\b",
    r"क्या होगा अगर",
    r"काल्पनिक",
    r"\bfictional?\b",
    r"\bcartoon\b",
    r"\btoon\b",
    r"कहानी",
    r"\bkahani\b",
    r"\bkahaniyan\b",
    r"\bdam\s*dam\s*damru\b",
    r"\bdamru\b",
    r"\bbhajan\b",
    r"\baarti\b",
    r"\bvisarjan\b",
    r"\bkhatu\s*(sham|dham|dam)\b",
    r"\bdj\s*song\b",
    r"\bdj\s*bhajan\b",
    r"\bnavratri\b",
    r"\bbhakti\b",
]
_AI_SYNTHETIC_RE = re.compile("|".join(AI_PATTERNS), re.IGNORECASE)

AI_SOURCE_PATTERNS = [
    r"\bai\b",
    r"\bartificial intelligence\b",
    r"\bcgi\b",
    r"\btoon\b",
    r"\bcartoon\b",
    r"\banimation\b",
    r"\bsimulator\b",
    r"\bsimulation\b",
    r"\bkahani\b",
    r"\bkahaniyan\b",
    r"\bghibli\b",
    r"\bgiant adventures\b",
    r"\bshadowframe\b",
    r"\bcosmic minds\b",
    r"\bechoes unveiled\b",
    r"\bfactnova\b",
    r"\blegacydailypay\b",
    r"\bdear humans\b",
    r"\borganic promotions\b",
    r"\bbeyond the limits\b",
    r"\bfantastic architecture\b",
    r"\bmurphy's law files\b",
    r"\bhistoraxp\b",
    r"\btidal bricks\b",
    r"\bbhajan\b",
    r"\bdivine\b",
    r"\bblueprint decay\b",
]
_AI_SOURCE_RE = re.compile("|".join(AI_SOURCE_PATTERNS), re.IGNORECASE)

# Figurative / Idiomatic non-dam phrases in all supported Indian languages & English
# (e.g. "सब्र का बांध टूट गया", "धैर्याचा बांध फुटला", "ধৈর্যের বাঁধ ভেঙে গেল", "dam of patience broke")
NON_DAM_METAPHOR_PATTERNS = [
    # Hindi / Urdu / Hinglish
    r"(?:सब्र|सबर|धैर्य)\s*(?:का|के|की|दा)?\s*(?:बाँध|बांध|पैमाना)",
    r"(?:बाँध|बांध)\s*(?:का|के|की)?\s*(?:सब्र|सबर|धैर्य)",
    r"(?:टूटा|टूट|फूटा|फूट)\s*(?:गया\s*)?(?:का\s*)?(?:सब्र|सबर|धैर्य)",
    r"(?:सब्र|सबर|धैर्य)\s*(?:का\s*)?(?:टूटा|टूट|फूटा|फूट)",
    # Bengali
    r"ধৈর্য(?:ের)?\s*বাঁধ",
    r"সবর(?:ের)?\s*বাঁধ",
    r"ধৈর্য\s*ভাঙ",
    # Assamese
    r"ধৈৰ্য(?:ৰ|্যৰ)?\s*বান্ধ",
    # Odia
    r"ଧୈର୍ଯ୍ୟ(?:ର)?\s*ବନ୍ଧ",
    r"ଧୈର୍ଯ୍ୟ\s*ଭାଙ୍ଗ",
    # Marathi
    r"धैर्याचा\s*बांध",
    r"संयमाचा\s*बांध",
    r"सबरचा\s*बांध",
    r"धैर्य\s*(?:सुटले|फुटले|तुटले)",
    # Gujarati
    r"ધીરજ(?:નો|\s*નો)?\s*બંધ",
    r"સબ્ર(?:નો|\s*નો)?\s*બંધ",
    r"સબર(?:નો|\s*નો)?\s*બંધ",
    r"સંયમ(?:નો|\s*નો)?\s*બંધ",
    r"ધીરજ\s*(?:તૂટી|ખૂટી)",
    # Punjabi
    r"ਸਬਰ\s*ਦਾ\s*(?:ਬੰਨ੍ਹ|ਬੰਧ)",
    r"ਧੀਰਜ\s*ਦਾ\s*(?:ਬੰਨ੍ਹ|ਬੰਧ)",
    r"ਟੁੱਟਿਆ\s*ਸਬਰ",
    r"ਸਬਰ\s*ਟੁੱਟ",
    # Urdu
    r"صبر\s*کا\s*(?:بندھ|بند|پیمانہ)",
    r"صبر\s*ٹوٹ",
    # South Indian languages
    r"సహన(?:పు|ం)?\s*(?:ఆనకట్ట|కట్ట)",
    r"సహనం\s*నశించి",
    r"తాಳ್ಮೆಯ\s*(?:ಕಟ್ಟೆ|ಅಣೆಕಟ್ಟು)",
    r"ತಾಳ್ಮೆ\s*ಗೆಟ್ಟ",
    r"பொறுமை(?:யின்)?\s*அணை",
    r"பொறுமை\s*இழந்த",
    r"ക്ഷമയുടെ\s*അണക്കെട്ട്",
    r"ക്ഷമ\s*നശിച്ചു",
    # English & Latin transliterations
    r"\bdam\s+of\s+patience\b",
    r"\bdam\s+of\s+forbearance\b",
    r"\bdam\s+of\s+tolerance\b",
    r"\bpatience\s+dam\b",
    r"\b(?:lost|broke|burst|broken)\s+(?:all\s+)?patience\b",
    r"\bpatience\s+(?:broke|burst|ran\s+out)\b",
    r"\bsabr\s*(?:ka|ke|ki)?\s*b[a|aa]+ndh\b",
    r"\bsabar\s*(?:ka|ke|ki)?\s*b[a|aa]+ndh\b",
    r"\bdhairya\s*(?:ka|ke|ki)?\s*b[a|aa]+ndh\b",
    r"\bsabr\s*(?:ka\s*)?toot\b",
]
_NON_DAM_METAPHOR_RE = re.compile("|".join(NON_DAM_METAPHOR_PATTERNS), re.IGNORECASE)


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


DISTRICT_TO_STATE = {
    "gondia": "Maharashtra", "गोंदिया": "Maharashtra",
    "tiroda": "Maharashtra", "तिरोडा": "Maharashtra",
    "tirora": "Maharashtra", "तिरोरा": "Maharashtra",
    "bhandara": "Maharashtra", "भंडारा": "Maharashtra",
    "chandrapur": "Maharashtra", "चंद्रपूर": "Maharashtra",
    "nagpur": "Maharashtra", "नागपूर": "Maharashtra",
    "pune": "Maharashtra", "पुणे": "Maharashtra",
    "nashik": "Maharashtra", "नासिक": "Maharashtra",
    "solapur": "Maharashtra", "सोलापूर": "Maharashtra",
    "kolhapur": "Maharashtra", "कोल्हापूर": "Maharashtra",
}
_DISTRICT_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in DISTRICT_TO_STATE) + r")\b", re.IGNORECASE)


def detect_state(text: str) -> str:
    norm = nfkc(text)
    m = _STATE_RE.search(norm)
    if m:
        found = m.group(1)
        if found in _STATE_ALIASES:
            return _STATE_ALIASES[found]
        return next(s for s in INDIAN_STATES if s.lower() == found)
    # Check district
    dm = _DISTRICT_RE.search(norm)
    if dm:
        return DISTRICT_TO_STATE.get(dm.group(1).lower(), "")
    return ""


def evaluate(lang: str, title: str, snippet: str = "", source: str = "", url: str = ""):
    """Return (score, status, state) or None if the item should be dropped.

    Strict Policies:
    - 0% AI content: No AI-generated videos, articles, CGI, simulations, or fiction.
    - India only: Only authentic Indian dams and India-related dam news.
    - Top Priority Source: https://sandrp.in/ (South Asia Network on Dams, Rivers and People)
      always receives priority scoring and guaranteed acceptance for dam/river/water issues.
    """
    text = nfkc(f"{title} {snippet}")

    # 0. Reject AI-generated, synthetic, CGI, simulation, and cartoon content immediately
    if _AI_SYNTHETIC_RE.search(text) or (source and _AI_SOURCE_RE.search(source)):
        return None

    # 0b. Reject figurative / non-dam metaphors ("सब्र का बांध टूट गया", "dam of patience", etc.)
    if _NON_DAM_METAPHOR_RE.search(text):
        return None

    # Check if this is from priority watchdog site SANDRP (https://sandrp.in/)
    is_sandrp = (
        "sandrp.in" in (url or "").lower()
        or "sandrp" in (source or "").lower()
        or "sandrp.in" in text
        or "south asia network on dams, rivers and people" in text
    )

    # 1. Reject explicit foreign dams immediately
    if _FOREIGN_DAM_RE.search(text):
        return None

    state = detect_state(f"{title} {snippet}")
    has_city = bool(_INDIAN_CITIES_RE.search(text))
    has_river = bool(_INDIAN_RIVERS_RE.search(text))
    has_india = bool(_INDIA_RE.search(text))
    has_indian_anchor = bool(state or has_city or has_river or has_india) or is_sandrp

    # 2. Reject foreign countries unless there is a strong Indian location/dam
    fc_match = _FOREIGN_COUNTRY_RE.search(text)
    if fc_match and not is_sandrp:
        if not (state or (has_city and has_india)):
            return None
        # Discard foreign dam disaster articles that happen to mention India in passing
        if fc_match.group(0) in ["china", "pakistan", "ukraine", "brazil", "russia", "myanmar", "indonesia"]:
            if any(w in title.lower() for w in ["mega-dam", "dam project", "rains, dam breach", "floods hit", "spencer", "vale's", "dagestan", "taiwan", "mataian", "fujinuma"]):
                return None

    # 3. For English articles: must have at least one genuine Indian anchor
    if lang == "en" and not has_indian_anchor:
        return None

    # Priority acceptance and scoring for SANDRP
    if is_sandrp:
        # SANDRP is dedicated to Indian dams, rivers, and water resources
        water_watchdog_terms = (
            "dam", "reservoir", "barrage", "bund", "river", "flood", "water",
            "embankment", "safety", "spillway", "canal", "breach", "burst",
            "monsoon", "drainage", "hydro", "basin", "ndsa", "cwc", "kumbh",
            "pollution", "drought", "weir", "gate", "collapse", "overflow"
        )
        if any(w in text for w in water_watchdog_terms):
            score = 90
            if any(w in text for w in ("breach", "burst", "collaps", "fail", "leak", "crack", "flood", "disaster", "seepage", "hazard", "safety")):
                score = 100
            return score, "relevant", state

    # 4. Dam & Failure term matching
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

    if state or has_india:
        score += 10

    score = max(0, min(100, score))
    if score >= 60:
        return score, "relevant", state
    if score >= 40:
        return score, "maybe", state
    return None

