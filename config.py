"""Settings for the Dam Failure News Watch. Secrets live in .env (see .env.example)."""
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional; environment variables still work
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
if load_dotenv:
    if (BASE_DIR / ".env").exists():
        load_dotenv(BASE_DIR / ".env")
    elif (BASE_DIR / ".env.example").exists():
        load_dotenv(BASE_DIR / ".env.example")

DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "dam_news.db"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# Local news often says "dam" for river-flood embankments (levees). By default the
# AI check drops those. Set INCLUDE_RIVER_EMBANKMENTS=1 in .env to keep them.
INCLUDE_RIVER_EMBANKMENTS = os.getenv("INCLUDE_RIVER_EMBANKMENTS", "0") == "1"

# YouTube search costs 100 quota units per call (free quota: 10,000 units/day).
YOUTUBE_QUERIES_PER_LANGUAGE = int(os.getenv("YOUTUBE_QUERIES_PER_LANGUAGE", "3"))
GDELT_QUERIES = int(os.getenv("GDELT_QUERIES", "6"))
# Searches run at the same time when you press "Search the internet" on the website.
# Lower to 1 if Google starts refusing requests.
SEARCH_WORKERS = int(os.getenv("SEARCH_WORKERS", "3"))

with open(BASE_DIR / "keywords.json", encoding="utf-8") as f:
    _KEYWORDS = json.load(f)

LANGUAGES = _KEYWORDS["languages"]
NEGATIVE_TERMS = _KEYWORDS["negative_terms"]
