"""YouTube collector (YouTube Data API v3, search.list).

Each search costs 100 quota units; the free quota is 10,000 units/day.
Get a key at https://console.cloud.google.com (enable "YouTube Data API v3").
"""
import html
import logging
import time
from datetime import datetime, timezone

import requests

import db

log = logging.getLogger("youtube")
API = "https://www.googleapis.com/youtube/v3/search"


class QuotaExceeded(Exception):
    pass


def fetch(api_key: str, lang: str, query: str, published_after: datetime,
          published_before: datetime | None = None, max_results: int = 25) -> list[dict]:
    params = {
        "part": "snippet", "type": "video", "q": query, "maxResults": max_results,
        "order": "relevance", "regionCode": "IN", "relevanceLanguage": lang,
        "publishedAfter": published_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "key": api_key,
    }
    if published_before:
        params["publishedBefore"] = published_before.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = requests.get(API, params=params, timeout=30)
    except requests.RequestException as exc:
        log.warning("YouTube request failed: %s", str(exc)[:160])
        return []
    if resp.status_code == 429 or (resp.status_code == 403 and "quota" in resp.text.lower()):
        log.warning("YouTube quota exceeded (HTTP %s): %s", resp.status_code, resp.text[:140])
        raise QuotaExceeded()
    if resp.status_code != 200:
        log.warning("YouTube HTTP %s: %s", resp.status_code, resp.text[:200])
        return []
    time.sleep(0.3)

    items = []
    for it in resp.json().get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid or not sn.get("title") or not sn.get("publishedAt"):
            continue
        published = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        thumbs = sn.get("thumbnails") or {}
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        items.append({
            "kind": "video", "title": html.unescape(sn["title"]),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "source": html.unescape(sn.get("channelTitle", "")), "language": lang,
            "published_at": db.utc_iso(published),
            "snippet": html.unescape(sn.get("description", "")),
            "thumbnail": thumb, "collector": "youtube", "query": query,
        })
    return items
