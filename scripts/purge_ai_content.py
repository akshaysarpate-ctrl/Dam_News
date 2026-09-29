import sqlite3
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect("dam_news.db")
c = conn.cursor()

# Comprehensive AI & Synthetic Content Patterns
AI_PATTERNS = [
    # AI explicit markers
    r"\bai\b",
    r"\bai[- ]generated\b",
    r"\bai[- ]animation\b",
    r"\bai\s*(pics?|photos?|images?|तस्वीर|तस्वीरें|चित्र|video|वीडियो)",
    r"\bartificial intelligence\b",
    r"आर्टिफिशियल इंटेलिजेंस",
    # Computer graphics & simulation
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
    # Hypothetical fiction / what if
    r"\bhypothetical\b",
    r"\bwhat if\b",
    r"क्या होगा अगर",
    r"काल्पनिक",
    r"\bfictional?\b",
    # Cartoons / children stories / fairy tales
    r"\bcartoon\b",
    r"\btoon\b",
    r"कहानी",
    r"\bkahani\b",
]

ai_combined_re = re.compile("|".join(AI_PATTERNS), re.IGNORECASE)

# AI source channel patterns
AI_SOURCE_PATTERNS = [
    r"\bai\b",
    r"\bartificial intelligence\b",
    r"\bcgi\b",
    r"\btoon\b",
    r"\bcartoon\b",
    r"\banimation\b",
    r"\bsimulator\b",
    r"\bsimulation\b",
]
ai_source_re = re.compile("|".join(AI_SOURCE_PATTERNS), re.IGNORECASE)

rows = c.execute("SELECT id, kind, title, snippet, source FROM articles").fetchall()
to_delete = []

for r in rows:
    aid, kind, title, snippet, source = r
    text = f"{title} {snippet}".lower()
    src = source.lower()
    
    # Check text for AI/simulation/cartoon
    m_text = ai_combined_re.search(text)
    m_src = ai_source_re.search(src)
    
    if m_text or m_src:
        reason = f"Matched text: {m_text.group(0)}" if m_text else f"Matched source: {m_src.group(0)}"
        to_delete.append((aid, title, source, reason))

print(f"Total articles scanned: {len(rows)}")
print(f"Total AI/synthetic/cartoon items identified: {len(to_delete)}")

for item in to_delete:
    t = item[1].encode('ascii', 'replace').decode()
    print(f"ID {item[0]:5d} | {item[3]:30s} | Src: {item[2][:20]:20s} | {t[:55]}")

if to_delete:
    c.executemany("DELETE FROM articles WHERE id = ?", [(item[0],) for item in to_delete])
    conn.commit()
    print(f"\nSuccessfully purged {len(to_delete)} AI-generated / synthetic items from database.")

remaining = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
print(f"Remaining authentic ground articles: {remaining}")
conn.close()
