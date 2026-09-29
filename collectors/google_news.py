"""Google News RSS collector.

One request per (language, query, date window). Google returns at most ~100 items per
request, so long look-backs are split into date windows (after:/before:) by collect.py.
"""
import html
import re
from datetime import datetime, timezone

import feedparser

import db
import util

BASE = "https://news.google.com/rss/search"
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", text or "")).split())


def parse_feed(content: bytes, lang: str, query: str) -> list[dict]:
    feed = feedparser.parse(content)
    items = []
    for entry in feed.entries:
        parsed = entry.get("published_parsed")
        if not parsed or not entry.get("link") or not entry.get("title"):
            continue
        title = _clean(entry.title)
        source = _clean((entry.get("source") or {}).get("title", ""))
        suffix = f" - {source}"
        if source and title.endswith(suffix):
            title = title[: -len(suffix)]
        snippet = _clean(entry.get("summary", ""))
        # Google's summary is usually the headline + source name again: drop that.
        if snippet.startswith(title) or snippet == source:
            snippet = ""
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        items.append({
            "kind": "article", "title": title, "url": entry.link, "source": source,
            "language": lang, "published_at": db.utc_iso(published), "snippet": snippet,
            "collector": "gnews", "query": query,
        })
    return items


def fetch(lang: str, lang_cfg: dict, query: str, after=None, before=None, sleep=(0.1, 0.3)) -> list[dict]:
    q = query
    if after:
        q += f" after:{after:%Y-%m-%d}"
    if before:
        q += f" before:{before:%Y-%m-%d}"
    edition = lang_cfg["edition"]
    resp = util.get(BASE, params={"q": q, "hl": edition["hl"], "gl": edition["gl"],
                                  "ceid": edition["ceid"]}, sleep=sleep)
    if resp is None:
        return []
    return parse_feed(resp.content, lang, query)
