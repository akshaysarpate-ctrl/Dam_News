"""Deep search module for dam news across national and regional newspapers."""
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
import db
import filters
import util
from collectors import google_news, sandrp

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
    "ml": ["ഡാം", "അணക്കെട്ട്"],
    "or": ["ବନ୍ଧ", "ଡ୍ୟାମ", "ଜଳଭଣ୍ଡାର"],
    "pa": ["ਡੈਮ", "ਬੰਨ੍ਹ"],
    "ur": ["ڈیم", "بیراج"],
    "as": ["বান্ধ", "ডেম"],
}

# Major newspaper & watchdog domains in India (sandrp.in is given top priority)
NEWSPAPER_DOMAINS = [
    "sandrp.in", "thehindu.com", "timesofindia.indiatimes.com", "indianexpress.com",
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
    import multilingual_search
    base_name, clean_name = clean_search_name(raw_name)
    is_generic = base_name.lower() in GENERIC_TERMS
    tasks = []

    # Convert English search term into all 12 supported Indian language scripts
    converted = multilingual_search.convert_name_to_all_languages(raw_name)

    # 1. English - Priority SANDRP watchdog queries + Core newspaper coverage
    en_cfg = config.LANGUAGES.get("en", {})
    if en_cfg:
        # Priority queries targeting sandrp.in
        tasks.append(("en", en_cfg, f'"{base_name}" site:sandrp.in'))
        if is_generic:
            tasks.append(("en", en_cfg, f'"{base_name}" dam'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam failure breach collapse'))
            tasks.append(("en", en_cfg, f'dam {base_name} site:thehindu.com OR site:timesofindia.indiatimes.com OR site:indianexpress.com'))
        else:
            tasks.append(("en", en_cfg, f'"{base_name}" dam'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam failure OR breach OR burst OR collapse OR flood'))
            tasks.append(("en", en_cfg, f'"{base_name}" reservoir OR barrage OR "water level" OR gates'))
            tasks.append(("en", en_cfg, f'"{base_name}" dam site:thehindu.com OR site:timesofindia.indiatimes.com OR site:indianexpress.com'))

    # 2. Regional Languages - Uses converted native script for each language
    for code, cfg in config.LANGUAGES.items():
        if code == "en":
            continue
        terms = REGIONAL_DAM_TERMS.get(code, [])
        native_variants = converted.get(code, [base_name])
        native_word = native_variants[0] if native_variants else base_name
        if terms:
            tasks.append((code, cfg, f'{native_word} {terms[0]}'))
            if not is_generic:
                tasks.append((code, cfg, f'"{native_word}"'))

    # 3. Dedicated incident queries for major regional languages using native script
    hi_name = converted.get("hi", [base_name])[0]
    hi_cfg = config.LANGUAGES.get("hi")
    if hi_cfg:
        tasks.append(("hi", hi_cfg, f'"{hi_name}" बांध दरार OR रिसाव OR बाढ़'))
        tasks.append(("hi", hi_cfg, f'"{hi_name}" बांध'))

    mr_name = converted.get("mr", [base_name])[0]
    mr_cfg = config.LANGUAGES.get("mr")
    if mr_cfg:
        tasks.append(("mr", mr_cfg, f'"{mr_name}" धरण पाणी OR पूर'))
        tasks.append(("mr", mr_cfg, f'"{mr_name}" धरण'))

    te_name = converted.get("te", [base_name])[0]
    te_cfg = config.LANGUAGES.get("te")
    if te_cfg:
        tasks.append(("te", te_cfg, f'"{te_name}" డ్యామ్ గేట్లు OR ముంపు'))

    ta_name = converted.get("ta", [base_name])[0]
    ta_cfg = config.LANGUAGES.get("ta")
    if ta_cfg:
        tasks.append(("ta", ta_cfg, f'"{ta_name}" அணை'))

    gu_name = converted.get("gu", [base_name])[0]
    gu_cfg = config.LANGUAGES.get("gu")
    if gu_cfg:
        tasks.append(("gu", gu_cfg, f'"{gu_name}" ડેમ'))

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

    # Priority 1: Query SANDRP (https://sandrp.in/) native feeds directly for this dam
    try:
        sandrp_items = sandrp.fetch_for_dam(base_name)
        stats["items_seen"] += len(sandrp_items)
        all_fetched.extend(sandrp_items)
    except Exception as e:
        log.warning("SANDRP direct fetch failed for %r: %s", base_name, e)

    # Priority 2: Concurrent multi-newspaper queries
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

    import multilingual_search
    converted = multilingual_search.convert_name_to_all_languages(raw_name)

    valid_items = []
    for item in all_fetched:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")
        source = item.get("source", "")
        text = f"{title} {snippet}".lower()
        is_sandrp_item = ("sandrp.in" in url.lower()) or ("sandrp" in source.lower())

        if filters._AI_SYNTHETIC_RE.search(text) or (item.get("source") and filters._AI_SOURCE_RE.search(item["source"])) or filters._NON_DAM_METAPHOR_RE.search(text):
            continue

        # Check if the text matches converted name by at least 75%
        score_pct, is_75_match, matched_term = multilingual_search.calculate_75_match(converted, f"{title} {snippet}")

        verdict = filters.evaluate(item["language"], title, snippet, source, url)

        if is_75_match:
            state = filters.detect_state(f"{title} {snippet}")
            item["score"] = max(item.get("score", 0), int(score_pct))
            item["status"] = "relevant"
            item["state"] = state
            item["dam_name"] = clean_name.title()
        elif is_sandrp_item:
            state = filters.detect_state(f"{title} {snippet}")
            item["score"] = 95
            item["status"] = "relevant"
            item["state"] = state
        elif verdict:
            item["score"], item["status"], item["state"] = verdict
        elif is_generic and any(w in text for w in ("dam", "reservoir", "barrage")):
            state = filters.detect_state(f"{title} {snippet}")
            item["score"] = 50
            item["status"] = "maybe"
            item["state"] = state
        else:
            continue

        if is_sandrp_item:
            item["score"] = max(item.get("score", 0), 95)
            item["status"] = "relevant"

        if not is_generic and not item.get("dam_name"):
            if base_lower in text:
                item["dam_name"] = base_name.title()
            elif "dam" in text:
                item["dam_name"] = clean_name.title()

        valid_items.append(item)

    # Decode Google News URLs to direct publisher URLs before inserting
    urls_to_decode = [it["url"] for it in valid_items if "news.google.com" in it.get("url", "")]
    if urls_to_decode:
        try:
            decoded = util.batch_decode_google_urls(urls_to_decode)
            dec_map = dict(zip(urls_to_decode, decoded))
            for it in valid_items:
                if it.get("url") in dec_map and "news.google.com" not in dec_map[it["url"]]:
                    it["url"] = dec_map[it["url"]]
        except Exception as exc:
            log.warning("Pre-insert URL decode error: %s", exc)

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
