import os
import sqlite3
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import filters

DB_PATH = os.path.join(BASE_DIR, "dam_news.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

rows = c.execute("SELECT id, kind, title, snippet, source, url FROM articles").fetchall()
to_delete = []

for r in rows:
    aid, kind, title, snippet, source, url = r
    # Skip verified institutional news watchdog
    if "sandrp.in" in (url or "").lower():
        continue

    text = f"{title} {snippet}".lower()
    src = (source or "").lower()

    m_text = filters._AI_SYNTHETIC_RE.search(text)
    m_src = filters._AI_SOURCE_RE.search(src)
    m_metaphor = filters._NON_DAM_METAPHOR_RE.search(text)

    if m_metaphor:
        to_delete.append((aid, kind, title, source, f"Patience Metaphor: {m_metaphor.group(0)}"))
    elif kind == "video":
        if m_text or m_src:
            reason = f"Video matched text: {m_text.group(0)}" if m_text else f"Video matched source: {m_src.group(0)}"
            to_delete.append((aid, kind, title, source, reason))
    else:
        # For articles, only purge if explicit AI / animation / simulation / non-dam event
        if m_src:
            to_delete.append((aid, kind, title, source, f"Article matched source: {m_src.group(0)}"))
        elif m_text:
            matched_term = m_text.group(0).lower()
            if any(w in matched_term for w in [
                "ai", "simulation", "cgi", "cartoon", "animation", "कहानी",
                "बैल", "पट में", "what if", "ghibli", "nostalgia", "तूफ़ान में फँसे",
                "पेड़ बचाने", "moral story", "fairy", "bedtime", "doll"
            ]):
                to_delete.append((aid, kind, title, source, f"Article matched text: {matched_term}"))

print(f"Total articles scanned: {len(rows)}")
print(f"Total AI/synthetic/cartoon/vlog items identified: {len(to_delete)}")
print("-" * 80)

for item in to_delete:
    t = item[2].encode('ascii', 'replace').decode()
    print(f"ID {item[0]:5d} | {item[4]:30s} | Src: {item[3][:20]:20s} | {t[:55]}")

if to_delete:
    c.executemany("DELETE FROM articles WHERE id = ?", [(item[0],) for item in to_delete])
    conn.commit()
    print(f"\nSuccessfully purged {len(to_delete)} AI-generated / synthetic / non-event items from database.")
else:
    print("\nNo matching items found to delete.")

remaining = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
print(f"Remaining authentic ground articles: {remaining}")
conn.close()
