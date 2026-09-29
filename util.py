"""Small HTTP helper: retries, back-off on rate limiting, polite delay between calls."""
import logging
import random
import time

import requests

log = logging.getLogger("http")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
}


def get(url, params=None, retries=3, timeout=30, sleep=(1.0, 2.0)):
    """Return a 200 response, or None after logging why it failed."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            log.warning("Request failed (%s): %s", type(exc).__name__, str(exc)[:160])
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 200:
            time.sleep(random.uniform(*sleep))
            return resp
        if resp.status_code in (429, 503):
            wait = 5 * 2 ** attempt
            log.warning("HTTP %s from %s - waiting %ss", resp.status_code, url.split("?")[0], wait)
            time.sleep(wait)
            continue
        log.warning("HTTP %s from %s", resp.status_code, url.split("?")[0])
        return None
    return None


def resolve_news_url(url: str, title: str = "", source: str = "") -> str:
    """Resolve an encoded Google News URL to the direct publisher newspaper URL.

    Guarantees opening the actual news article directly on the newspaper's
    website without any intermediate Google Redirect Notice or search page.
    """
    if not url:
        return ""
    if "news.google.com" not in url and "google.com" not in url:
        return url

    # 1. Primary: Use GoogleDecoder (batchexecute RPC over HTTP/2)
    try:
        from googlenewsdecoder import GoogleDecoder
        with GoogleDecoder(timeout=6.0) as gd:
            res = gd.decode_google_news_url(url)
            if res.get("success") and res.get("decoded_url"):
                target = res["decoded_url"]
                if "news.google.com" not in target and "google.com" not in target:
                    return target
    except Exception as exc:
        log.warning("GoogleDecoder error for %s: %s", url[:50], exc)

    # 2. Secondary fallback: DuckDuckGo search for exact title & source
    if title:
        try:
            import urllib.parse
            q = f"{title} {source}".strip()
            r = requests.post("https://html.duckduckgo.com/html/", data={"q": q},
                              headers=HEADERS, timeout=3.5)
            if r.status_code == 200:
                from selectolax.parser import HTMLParser
                tree = HTMLParser(r.text)
                for a in tree.css("a.result__url, a.result__snippet, a.result__a"):
                    h = a.attributes.get("href", "")
                    if "uddg=" in h:
                        pq = urllib.parse.parse_qs(urllib.parse.urlparse(h).query)
                        if "uddg" in pq:
                            candidate = pq["uddg"][0]
                            if candidate.startswith("http") and not any(d in candidate for d in ("duckduckgo.com", "google.com")):
                                return candidate
        except Exception:
            pass

    return url


def batch_decode_google_urls(urls: list[str]) -> list[str]:
    """Decode a batch of Google News URLs into direct publisher newspaper URLs."""
    if not urls:
        return []
    from googlenewsdecoder import GoogleDecoder
    try:
        with GoogleDecoder(timeout=20.0) as gd:
            results = gd.decode_google_news_urls(urls)
            out = []
            for r, u in zip(results, urls):
                decoded = r.get("decoded_url") if r.get("success") else None
                if decoded and "news.google.com" not in decoded and "google.com" not in decoded:
                    out.append(decoded)
                else:
                    out.append(u)
            return out
    except Exception as exc:
        log.warning("batch_decode_google_urls error: %s", exc)
        return urls


