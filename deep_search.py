"""Deep search module for dam news across national and regional newspapers."""
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
import db
import filters
import util
from collectors import google_news

log = logging.getLogger("deep_search")

# Specific regional language dam terms for name pairing
REGIONAL_DAM_TERMS = {
    "hi": ["बांध", "डैम", "जलाशय", "तटबंध", "बैराज"],
    "mr": ["धरण", "बंधारा", "जलाशय", "तलाव"],
    "gu": ["ડેમ", "જળાશય", "ચેકડેમ"],
    "bn": ["বাঁধ", "ড্যাম", "জলাধার"],
    "ta": ["அணை", "தடுப்பணை", "ஏரி"],
    "te": ["డ్యామ్", "ప్రాజెక్టు", "ఆనకట్ట", "రిజర్వాయర్"],
    "kn": ["ಅಣೆಕಟ್ಟು", "ಡ್ಯಾಂ", "ಜಲಾಶಯ"],
    "ml": ["ഡാം", "അണക്കെട്ട്"],
    "or": ["ବନ୍ଧ", "ଡ୍ୟାମ", "ଜଳଭଣ୍ଡାର"],
    "pa": ["ਡੈਮ", "ਬੰਨ੍ਹ"],
    "ur": ["ڈیم", "بیراج"],
    "as": ["বান্ধ", "ডেম"],
}

# Major newspaper domains in India to ensure deep newspaper crawling
NEWSPAPER_DOMAINS = [
    "thehindu.com", "timesofindia.indiatimes.com", "indianexpress.com",
    "hindustantimes.com", "deccanherald.com", "telegraphindia.com",
    "tribuneindia.com", "amarujala.com", "jagran.com", "bhaskar.com",
    "lokmat.com", "esakal.com", "eenadu.net", "sakshi.com", "dinamalar.com",
    "dailythanthi.com", "prajavani.net", "manoramaonline.com", "mathrubhumi.com",
    "anandabazar.com", "sambad.in", "ajitjalandhar.com"
]

GENERIC_TERMS = {
    "dam", "dams", "dam failure", "dam breach", "inundation", "dam collapse",
    "failure", "breach", "collapse", "reservoir", "barrage", "bund", "flooded", "flood"
}


def clean_search_name(raw_name: str) -> tuple[str, str]:
    """Clean the input name and return (base_name, clean_name).
    e.g. 'Kalyani dam' -> ('Kalyani', 'Kalyani dam')
         'Mullaperiyar' -> ('Mullaperiyar', 'Mullaperiyar')
         'dam breach'   -> ('dam breach', 'dam breach')
    """
    clean = " ".join(raw_name.strip().split())
    if clean.lower() in GENERIC_TERMS:
        return clean, clean
    # Strip trailing or leading words like 'dam', 'reservoir', 'project' for the base name
    base = re.sub(r"(?i)\b(dam|reservoir|project|barrage|bund|lake)\b", "", clean).strip()
    if not base:
        base = clean
    return base, clean


def build_deep_newspaper_queries(raw_name: str) -> list[tuple[str, dict, str]]:
    """Build high-yield, focused search queries across national and regional newspapers.
    Returns list of (lang_code, lang_cfg, query_string).
    """
    base_name, clean_name = clean_search_name(raw_name)
    is_generic = base_name.lower() in GENERIC_TERMS
    tasks = []

    # 1. English - Core queries + Newspaper coverage
    en_cfg = config.LANGUAGES.get("en", {})
    if en_cfg:
        if is_generic:
            tasks.append(("en", en_cfg, f'"{base_name}" dam'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam failure breach collapse'))
            tasks.append(("en", en_cfg, f'dam {base_name} site:thehindu.com OR site:timesofindia.indiatimes.com OR site:indianexpress.com'))
        else:
            tasks.append(("en", en_cfg, f'"{base_name}" dam'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam failure OR breach OR burst OR collapse OR flood'))
            tasks.append(("en", en_cfg, f'"{base_name}" reservoir OR barrage OR "water level" OR gates'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam site:thehindu.com OR site:timesofindia.indiatimes.com OR site:indianexpress.com'))

    # 2. Regional Languages - 1 top query per regional language
    for code, cfg in config.LANGUAGES.items():
        if code == "en":
            continue
        terms = REGIONAL_DAM_TERMS.get(code, [])
        if terms:
            tasks.append((code, cfg, f'{base_name} {terms[0]}'))

    # 3. Dedicated incident queries for major regional languages
    hi_cfg = config.LANGUAGES.get("hi")
    if hi_cfg:
        tasks.append(("hi", hi_cfg, f'"{base_name}" बांध दरार OR रिसाव OR बाढ़'))
    mr_cfg = config.LANGUAGES.get("mr")
    if mr_cfg:
        tasks.append(("mr", mr_cfg, f'"{base_name}" धरण पाणी OR पूर'))
    te_cfg = config.LANGUAGES.get("te")
    if te_cfg:
        tasks.append(("te", te_cfg, f'"{base_name}" డ్యామ్ గేట్లు OR ముంపు'))

    return tasks


def run_deep_search(conn, raw_name: str, workers: int = 15) -> dict:
    """Execute deep search across all newspapers on the internet and store in DB."""
    t0 = time.time()
    base_name, clean_name = clean_search_name(raw_name)
    queries = build_deep_newspaper_queries(raw_name)

    stats = {
        "name": raw_name,
        "base_name": base_name,
        "queries_total": len(queries),
        "items_seen": 0,
        "items_added": 0,
        "time_seconds": 0.0,
    }

    log.info("Starting deep newspaper search for %r (%d queries, %d workers)",
             raw_name, len(queries), workers)

    def fetch_one(task):
        code, cfg, q = task
        try:
            edition = cfg["edition"]
            resp = util.get(google_news.BASE,
                            params={"q": q, "hl": edition["hl"], "gl": edition["gl"], "ceid": edition["ceid"]},
                            timeout=6, retries=1, sleep=(0, 0))
            if resp is None:
                return code, q, []
            return code, q, google_news.parse_feed(resp.content, code, q)
        except Exception as e:
            log.warning("Search query failed %r (%s): %s", q, code, e)
            return code, q, []

    all_fetched = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(fetch_one, t) for t in queries]
        for f in as_completed(futs):
            code, q, items = f.result()
            stats["items_seen"] += len(items)
            for it in items:
                all_fetched.append(it)

    # Process and store results
    base_lower = base_name.lower()
    is_generic = base_lower in GENERIC_TERMS

    WATER_TERMS = (
        "dam", "reservoir", "barrage", "bund", "water", "flood", "lake",
        "canal", "river", "gate", "breach", "collapse", "spillway", "overflow",
        "inundat", "submerg", "leak", "crack", "seepage", "alert", "disaster"
    )

    valid_items = []
    for item in all_fetched:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        text = f"{title} {snippet}".lower()

        # Check if the name or dam terms match
        verdict = filters.evaluate(item["language"], title, snippet)
        
        if verdict:
            item["score"], item["status"], item["state"] = verdict
        elif base_lower in text and any(w in text for w in WATER_TERMS):
            state = filters.detect_state(f"{title} {snippet}")
            item["score"] = 60
            item["status"] = "relevant"
            item["state"] = state
        elif is_generic and any(w in text for w in ("dam", "reservoir", "barrage")):
            state = filters.detect_state(f"{title} {snippet}")
            item["score"] = 50
            item["status"] = "maybe"
            item["state"] = state
        else:
            continue

        if not is_generic:
            if base_lower in text:
                item["dam_name"] = base_name.title()
            elif "dam" in text:
                item["dam_name"] = clean_name.title()

        valid_items.append(item)

    for item in valid_items:
        if db.insert_article(conn, item):
            stats["items_added"] += 1

    conn.commit()
    stats["time_seconds"] = round(time.time() - t0, 2)
    log.info("Deep search finished for %r: %d seen, %d added in %.2fs",
             raw_name, stats["items_seen"], stats["items_added"], stats["time_seconds"])

    # Decode Google News URLs asynchronously in background so the UI loads in ~1 second
    if stats["items_added"] > 0:
        def _bg_decode():
            try:
                import time as _t
                _t.sleep(0.5)
                bg_conn = db.connect()
                rows = bg_conn.execute(
                    "SELECT id, url FROM articles WHERE url LIKE '%news.google.com%' ORDER BY id DESC LIMIT 50"
                ).fetchall()
                if rows:
                    urls = [r["url"] for r in rows]
                    decoded = util.batch_decode_google_urls(urls)
                    updates = [(d, r["id"]) for r, d in zip(rows, decoded) if d and "news.google.com" not in d]
                    if updates:
                        bg_conn.executemany("UPDATE articles SET url = ? WHERE id = ?", updates)
                        bg_conn.commit()
                bg_conn.close()
            except Exception as exc:
                log.warning("Background URL decode error: %s", exc)

        import threading
        threading.Thread(target=_bg_decode, daemon=True).start()

    return stats
