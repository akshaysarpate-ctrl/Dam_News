import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from googlenewsdecoder import GoogleDecoder

CHUNK_SIZE = 40

def main():
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, url FROM articles WHERE url LIKE '%news.google.com%' OR url LIKE '%google.com/rss%'"
    ).fetchall()
    total = len(rows)
    print(f"Total articles to decode: {total}")
    if not total:
        print("All articles already resolved!")
        return

    resolved_count = 0
    start_time = time.time()

    with GoogleDecoder(timeout=20.0) as gd:
        for offset in range(0, total, CHUNK_SIZE):
            chunk = rows[offset : offset + CHUNK_SIZE]
            urls = [r["url"] for r in chunk]
            try:
                results = gd.decode_google_news_urls(urls)
                updates = []
                for r, res in zip(chunk, results):
                    if res.get("success") and res.get("decoded_url"):
                        d_url = res["decoded_url"]
                        if "news.google.com" not in d_url and "google.com" not in d_url:
                            updates.append((d_url, r["id"]))
                            resolved_count += 1
                if updates:
                    conn.executemany("UPDATE articles SET url = ? WHERE id = ?", updates)
                    conn.commit()
            except Exception as e:
                print(f"Chunk error at offset {offset}: {e}")

            done = min(offset + CHUNK_SIZE, total)
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            print(f"Progress: {done}/{total} ({resolved_count} direct URLs saved, {rate:.1f} items/s)")

    conn.close()
    print(f"Completed! Successfully resolved {resolved_count}/{total} URLs to direct publisher links.")

if __name__ == "__main__":
    main()
