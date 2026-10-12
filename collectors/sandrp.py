"""SANDRP (South Asia Network on Dams, Rivers and People - https://sandrp.in/) collector.

SANDRP is a high-priority, authoritative watchdog and research source for
dam safety, floods, barrage operations, and river issues in India.
"""
import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

import db
import util

log = logging.getLogger("sandrp")

SANDRP_BASE = "https://sandrp.in"
SANDRP_MAIN_FEED = "https://sandrp.in/feed/"
SANDRP_SEARCH_FEED = "https://sandrp.in/?s={query}&feed=rss2"
GNEWS_SEARCH_BASE = "https://news.google.com/rss/search"

_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    if not text:
        return ""
    cleaned = html.unescape(_TAG.sub(" ", text))
    return " ".join(cleaned.split())


def _parse_entry(entry, query: str = "sandrp") -> dict | None:
    link = entry.get("link", "").strip()
    title = _clean(entry.get("title", ""))
    if not link or not title:
        return None

    # Strip trailing " - South Asia Network on Dams, Rivers and People" if present
    for suffix in [" - South Asia Network on Dams, Rivers and People", " - SANDRP"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()

    parsed = entry.get("published_parsed")
    if parsed:
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
    else:
        published = datetime.now(timezone.utc)

    summary = _clean(entry.get("summary", "") or entry.get("description", ""))
    # Truncate summary if excessively long
    if len(summary) > 600:
        summary = summary[:600] + "..."

    return {
        "kind": "article",
        "title": title,
        "url": link,
        "source": "SANDRP",
        "language": "en",
        "published_at": db.utc_iso(published),
        "snippet": summary,
        "collector": "sandrp",
        "query": query,
    }


def fetch_native_feed(url: str, query: str = "sandrp", after=None, before=None) -> list[dict]:
    """Fetch and parse a WordPress RSS feed from sandrp.in."""
    try:
        resp = util.get(url, timeout=10, retries=2, sleep=(0.1, 0.3))
        if resp is None:
            return []
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries:
            item = _parse_entry(entry, query=query)
            if not item:
                continue

            if after or before:
                pub_dt = datetime.strptime(item["published_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if after and pub_dt.date() < after:
                    continue
                if before and pub_dt.date() >= before:
                    continue

            items.append(item)
        return items
    except Exception as e:
        log.warning("Failed to fetch SANDRP feed %s: %s", url, e)
        return []


def fetch_gnews_sandrp(query: str = "dam", after=None, before=None) -> list[dict]:
    """Search Google News for site:sandrp.in covering historical ranges."""
    try:
        q = f"site:sandrp.in {query}".strip()
        if after:
            q += f" after:{after:%Y-%m-%d}"
        if before:
            q += f" before:{before:%Y-%m-%d}"

        resp = util.get(
            GNEWS_SEARCH_BASE,
            params={"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            timeout=8,
            retries=1,
            sleep=(0.1, 0.3),
        )
        if resp is None:
            return []

        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries:
            parsed = entry.get("published_parsed")
            link = entry.get("link", "").strip()
            title = _clean(entry.get("title", ""))
            if not parsed or not link or not title:
                continue

            for suffix in [" - South Asia Network on Dams, Rivers and People", " - SANDRP"]:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()

            snippet = _clean(entry.get("summary", ""))
            if snippet.startswith(title):
                snippet = ""

            published = datetime(*parsed[:6], tzinfo=timezone.utc)
            items.append({
                "kind": "article",
                "title": title,
                "url": link,
                "source": "SANDRP",
                "language": "en",
                "published_at": db.utc_iso(published),
                "snippet": snippet,
                "collector": "sandrp",
                "query": q,
            })
        return items
    except Exception as e:
        log.warning("Failed to fetch Google News for SANDRP: %s", e)
        return []


def fetch_recent(after=None, before=None) -> list[dict]:
    """Fetch recent articles directly from SANDRP native feeds and site queries."""
    seen_urls = set()
    results = []

    # 1. Main RSS feed
    for it in fetch_native_feed(SANDRP_MAIN_FEED, query="main_feed", after=after, before=before):
        if it["url"] not in seen_urls:
            seen_urls.add(it["url"])
            results.append(it)

    # 2. Targeted topic searches on SANDRP
    topics = ["dam", "dam safety", "flood", "barrage", "reservoir"]
    for topic in topics:
        feed_url = SANDRP_SEARCH_FEED.format(query=quote_plus(topic))
        for it in fetch_native_feed(feed_url, query=f"sandrp:{topic}", after=after, before=before):
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                results.append(it)

    # 3. Google News site:sandrp.in for historical date windows
    if after or before:
        for it in fetch_gnews_sandrp("dam", after=after, before=before):
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                results.append(it)

    return results


def fetch_for_dam(dam_name: str) -> list[dict]:
    """Search SANDRP directly and via Google News for a specific dam or project name."""
    seen_urls = set()
    results = []

    # 1. Direct WordPress search feed on sandrp.in
    feed_url = SANDRP_SEARCH_FEED.format(query=quote_plus(dam_name))
    for it in fetch_native_feed(feed_url, query=f"dam:{dam_name}"):
        if it["url"] not in seen_urls:
            seen_urls.add(it["url"])
            results.append(it)

    # 2. Google News site:sandrp.in
    for it in fetch_gnews_sandrp(f'"{dam_name}"'):
        if it["url"] not in seen_urls:
            seen_urls.add(it["url"])
            results.append(it)

    return results
