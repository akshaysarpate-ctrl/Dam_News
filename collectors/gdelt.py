"""GDELT DOC 2.0 API collector: free, indexes many regional Indian outlets.

The API only looks back ~3 months and allows about one request per 5 seconds.
"""
import logging
from datetime import datetime, timezone

import db
import util

log = logging.getLogger("gdelt")
API = "https://api.gdeltproject.org/api/v2/doc/doc"
LANG_MAP = {
    "english": "en", "hindi": "hi", "marathi": "mr", "tamil": "ta", "telugu": "te",
    "kannada": "kn", "malayalam": "ml", "bengali": "bn", "gujarati": "gu",
    "punjabi": "pa", "urdu": "ur", "oriya": "or", "odia": "or", "assamese": "as",
}


def fetch(query: str, start, end) -> list[dict]:
    """start and end are dates (inclusive). GDELT only holds about the last 3 months."""
    phrase = f'"{query}"' if " " in query else query
    params = {
        "query": f"{phrase} sourcecountry:IN", "mode": "artlist", "format": "json",
        "maxrecords": 250, "sort": "datedesc",
        "startdatetime": f"{start:%Y%m%d}000000",
        "enddatetime": f"{end:%Y%m%d}235959",
    }
    resp = util.get(API, params=params, sleep=(5.5, 6.5))
    if resp is None:
        return []
    try:
        data = resp.json()
    except ValueError:
        log.warning("GDELT returned a non-JSON reply for %r: %s", query, resp.text[:120])
        return []
    items = []
    for art in data.get("articles", []):
        try:
            seen = datetime.strptime(art["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if not art.get("url") or not art.get("title"):
            continue
        items.append({
            "kind": "article", "title": " ".join(art["title"].split()), "url": art["url"],
            "source": art.get("domain", ""),
            "language": LANG_MAP.get((art.get("language") or "").lower(), "und"),
            "published_at": db.utc_iso(seen), "snippet": "",
            "thumbnail": art.get("socialimage", "") or "",
            "collector": "gdelt", "query": query,
        })
    return items
