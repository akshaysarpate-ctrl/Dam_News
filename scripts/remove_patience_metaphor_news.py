"""Purge news articles containing figurative patience idioms like '[सब्र का बांध टूट गया]' in any language.
These are metaphors ('dam of patience broke', etc.) and are not related to actual physical dams.
"""
import os
import sqlite3
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add parent directory to sys.path to import filters
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import filters

DB_PATH = os.path.join(BASE_DIR, "dam_news.db")


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT id, language, kind, title, snippet, source, url FROM articles"
    ).fetchall()

    to_delete = []
    for r in rows:
        aid, lang, kind, title, snippet, source, url = r
        text = f"{title} {snippet}"
        m = filters._NON_DAM_METAPHOR_RE.search(text)
        if m:
            matched_phrase = m.group(0)
            to_delete.append((aid, lang, source, matched_phrase, title))

    print(f"Total articles scanned in database: {len(rows)}")
    print(f"Identified figurative/metaphorical items to remove: {len(to_delete)}")
    print("-" * 80)

    for aid, lang, source, phrase, title in to_delete:
        print(f"ID {aid:5d} [{lang}] | Matched: '{phrase}' | Src: {source[:22]:22s} | {title}")

    print("-" * 80)

    if to_delete:
        cur.executemany("DELETE FROM articles WHERE id = ?", [(item[0],) for item in to_delete])
        conn.commit()
        print(f"Successfully deleted {len(to_delete)} non-dam articles from 'articles' table.")
    else:
        print("No matching articles found to delete.")

    remaining = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    print(f"Total remaining authentic articles in database: {remaining}")

    conn.close()


if __name__ == "__main__":
    main()
