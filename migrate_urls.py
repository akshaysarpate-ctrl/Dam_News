"""Batch resolve Google News URLs in database to direct publisher URLs."""
import logging
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import util

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate_urls")

def resolve_row(row):
    aid, title, source, url = row
    if not url or "news.google.com" not in url:
        return aid, url, False
    direct = util.resolve_news_url(url, title=title, source=source)
    if direct and "google.com" not in direct and direct.startswith("http"):
        return aid, direct, True
    return aid, direct, False

def run_batch(limit=100, workers=8):
    conn = sqlite3.connect("dam_news.db", timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, source, url FROM articles WHERE url LIKE '%news.google.com%' ORDER BY published_at DESC LIMIT ?",
        (limit,)
    )
    rows = [(r["id"], r["title"], r["source"], r["url"]) for r in cur.fetchall()]
    conn.close()

    log.info("Found %d articles with Google News URLs to resolve", len(rows))
    if not rows:
        return

    updated = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(resolve_row, r) for r in rows]
        for f in as_completed(futs):
            aid, direct_url, success = f.result()
            if success:
                try:
                    c = sqlite3.connect("dam_news.db", timeout=30)
                    c.execute("UPDATE articles SET url = ? WHERE id = ?", (direct_url, aid))
                    c.commit()
                    c.close()
                    updated += 1
                except Exception as e:
                    log.warning("DB update failed for %s: %s", aid, e)

    log.info("Resolved %d/%d articles to direct publisher URLs in %.2fs", updated, len(rows), time.time() - t0)

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run_batch(limit=count)
