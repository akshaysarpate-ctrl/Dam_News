"""SQLite storage. Duplicates are ignored by URL and by (source + normalised title)."""
import hashlib
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  url_hash     TEXT NOT NULL UNIQUE,
  dedupe_key   TEXT NOT NULL UNIQUE,
  kind         TEXT NOT NULL DEFAULT 'article',   -- article | video
  title        TEXT NOT NULL,
  url          TEXT NOT NULL,
  source       TEXT NOT NULL DEFAULT '',
  language     TEXT NOT NULL DEFAULT 'und',
  published_at TEXT NOT NULL,                     -- UTC, YYYY-MM-DDTHH:MM:SSZ
  snippet      TEXT NOT NULL DEFAULT '',
  thumbnail    TEXT NOT NULL DEFAULT '',
  state        TEXT NOT NULL DEFAULT '',
  district     TEXT NOT NULL DEFAULT '',
  dam_name     TEXT NOT NULL DEFAULT '',
  structure    TEXT NOT NULL DEFAULT '',          -- dam | barrage | tank_bund | ...
  event_type   TEXT NOT NULL DEFAULT '',
  score        INTEGER NOT NULL DEFAULT 0,
  status       TEXT NOT NULL DEFAULT 'maybe',     -- relevant | maybe | rejected
  llm_checked  INTEGER NOT NULL DEFAULT 0,
  collector    TEXT NOT NULL DEFAULT '',
  query        TEXT NOT NULL DEFAULT '',
  fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_pub    ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status, published_at DESC);

CREATE TABLE IF NOT EXISTS runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  seen        INTEGER DEFAULT 0,
  added       INTEGER DEFAULT 0
);
"""

IST = timezone(timedelta(hours=5, minutes=30))

_TRACKING_PARAMS = {"fbclid", "gclid", "oc", "ved", "ref"}


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return utc_iso(datetime.now(timezone.utc))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    # Ensure any YouTube URLs or sources are tagged as kind='video'
    try:
        conn.execute("UPDATE articles SET kind = 'video' WHERE (source LIKE '%youtube%' OR url LIKE '%youtube%' OR url LIKE '%youtu.be%') AND kind != 'video'")
        conn.commit()
    except Exception:
        pass
    return conn


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                       urlencode(query), ""))


def norm_title(title: str) -> str:
    """Lower-case, keep letters/marks/digits of any script, collapse everything else."""
    t = unicodedata.normalize("NFKC", title).lower()
    t = "".join(ch if unicodedata.category(ch)[0] in "LMN" else " " for ch in t)
    return " ".join(t.split())[:160]


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


import re

def extract_youtube_id(url: str) -> str:
    """Extract 11-char YouTube video ID from watch, embed, short, or youtu.be URLs."""
    if not url:
        return ""
    m = re.search(r"(?:v=|\/embed\/|\/watch\?v=|\/v\/|youtu\.be\/|\/shorts\/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else ""


def insert_article(conn: sqlite3.Connection, a: dict) -> bool:
    """Insert one article. Returns True if it was new."""
    url = a["url"]
    if not url.lower().startswith(("http://", "https://")):
        return False

    yt_id = extract_youtube_id(url)
    kind = a.get("kind", "article")
    source = a.get("source", "")
    url_lower = url.lower()
    source_lower = source.lower()

    if yt_id or "youtube.com" in url_lower or "youtu.be" in url_lower or "youtube" in source_lower:
        kind = "video"
        if not source:
            source = "YouTube"

    thumbnail = a.get("thumbnail", "")
    if kind == "video" and not thumbnail and yt_id:
        thumbnail = f"https://i.ytimg.com/vi/{yt_id}/hqdefault.jpg"

    cur = conn.execute(
        """INSERT OR IGNORE INTO articles
           (url_hash, dedupe_key, kind, title, url, source, language, published_at,
            snippet, thumbnail, state, district, dam_name, score, status, collector, query, fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _sha1(canonical_url(url)),
            _sha1((source.lower()) + "|" + norm_title(a["title"])),
            kind, a["title"], url, source,
            a.get("language", "und"), a["published_at"], a.get("snippet", ""),
            thumbnail, a.get("state", ""), a.get("district", ""),
            a.get("dam_name", ""), a.get("score", 0),
            a.get("status", "maybe"), a.get("collector", ""), a.get("query", ""),
            now_iso(),
        ),
    )
    return cur.rowcount == 1


def start_run(conn) -> int:
    cur = conn.execute("INSERT INTO runs(started_at) VALUES (?)", (now_iso(),))
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id: int, seen: int, added: int) -> None:
    conn.execute("UPDATE runs SET finished_at=?, seen=?, added=? WHERE id=?",
                 (now_iso(), seen, added, run_id))
    conn.commit()
