#!/usr/bin/env python3
"""Collect dam-failure news and videos and store them in the database.

Daily run:              python collect.py
First run (a year):     python collect.py --days 365
A specific date range:  python collect.py --from 2026-06-01 --to 2026-08-15
Check the feeds:        python collect.py --test
Only some languages:    python collect.py --langs hi,mr,en

The website's "Search the internet" button uses the same collect_range() function.
"""
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from functools import partial

import classify
import config
import db
import filters
import util
from collectors import gdelt, google_news, youtube

log = logging.getLogger("collect")


def today_ist() -> date:
    return datetime.now(db.IST).date()


def date_windows(start: date, end: date, window_days: int):
    """Yield (after, before) pairs covering start..end inclusive; 'before' is exclusive."""
    stop = end + timedelta(days=1)
    cur = start
    while cur < stop:
        nxt = min(cur + timedelta(days=window_days), stop)
        yield cur, nxt
        cur = nxt


def store(conn, items, stats):
    valid = []
    for item in items:
        stats["seen"] += 1
        verdict = filters.evaluate(item["language"], item["title"], item.get("snippet", ""), item.get("source", ""))
        if not verdict:
            continue
        item["score"], item["status"], item["state"] = verdict
        valid.append(item)

    gnews = [it for it in valid if "news.google.com" in it.get("url", "")]
    if gnews:
        try:
            urls = [it["url"] for it in gnews]
            decoded = util.batch_decode_google_urls(urls)
            for it, dec in zip(gnews, decoded):
                if dec:
                    it["url"] = dec
        except Exception:
            pass

    for item in valid:
        if db.insert_article(conn, item):
            stats["added"] += 1
    conn.commit()


def collect_range(conn, start: date, end: date, langs=None,
                  sources=("gnews", "youtube", "gdelt"), use_ai=True, workers=1,
                  window_days=31, ai_limit=150, progress=None) -> dict:
    """Search the internet for stories published from `start` to `end` (inclusive) and
    save them. progress(done, total, message, added) is called as the work advances."""
    langs = langs or list(config.LANGUAGES)
    sources = set(sources)
    stats = {"seen": 0, "added": 0, "notes": []}
    run_id = db.start_run(conn)

    # ---- plan the work as a list of small search tasks
    tasks = []
    if "gnews" in sources:
        for after, before in date_windows(start, end, window_days):
            for code in langs:
                cfg = config.LANGUAGES[code]
                for query in cfg["queries"]:
                    tasks.append(("gnews", partial(google_news.fetch, code, cfg, query, after, before)))

    if "youtube" in sources:
        if not config.YOUTUBE_API_KEY:
            stats["notes"].append("YouTube was skipped because no YOUTUBE_API_KEY is set in .env.")
        else:
            t0 = datetime.combine(start, time.min, tzinfo=db.IST)
            t1 = datetime.combine(end + timedelta(days=1), time.min, tzinfo=db.IST)
            for code in langs:
                for query in config.LANGUAGES[code]["queries"][:config.YOUTUBE_QUERIES_PER_LANGUAGE]:
                    tasks.append(("youtube", partial(youtube.fetch, config.YOUTUBE_API_KEY,
                                                     code, query, t0, t1)))

    gdelt_queries, gdelt_start = [], start
    if "gdelt" in sources:
        gdelt_start = max(start, today_ist() - timedelta(days=89))
        if gdelt_start > end:
            stats["notes"].append("GDELT was skipped: it only covers roughly the last 3 months.")
        else:
            gdelt_queries = config.LANGUAGES["en"]["queries"][:config.GDELT_QUERIES]
            if gdelt_start > start:
                stats["notes"].append(f"GDELT only covered {gdelt_start:%d %b %Y} onwards (its 3-month limit).")

    total = len(tasks) + len(gdelt_queries)
    state = {"done": 0, "youtube_stopped": False}

    def report(message):
        if progress:
            progress(state["done"], total, message, stats["added"])

    def run_one(task):
        kind, fn = task
        if kind == "youtube" and state["youtube_stopped"]:
            return kind, []
        try:
            return kind, fn()
        except youtube.QuotaExceeded:
            return kind, None
        except Exception:
            log.exception("A search step failed and was skipped")
            return kind, []

    # ---- news and video searches (in parallel when workers > 1)
    report("Searching news and videos")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(run_one, t) for t in tasks]
        for fut in as_completed(futures):
            kind, items = fut.result()
            if items is None:
                state["youtube_stopped"] = True
                stats["notes"].append("YouTube's daily quota ran out, so some videos are missing.")
                items = []
            store(conn, items, stats)
            state["done"] += 1
            report("Searching news and videos")

    # ---- GDELT (one request every ~6 seconds, so it runs one at a time)
    for query in gdelt_queries:
        report("Searching GDELT")
        store(conn, gdelt.fetch(query, gdelt_start, end), stats)
        state["done"] += 1
    if gdelt_queries:
        report("Searching GDELT")

    # ---- optional AI check
    if use_ai and config.ANTHROPIC_API_KEY:
        report("Checking results with AI")
        classify.classify_pending(conn, ai_limit)
    elif use_ai:
        log.info("ANTHROPIC_API_KEY not set - using keyword scoring only.")

    db.finish_run(conn, run_id, stats["seen"], stats["added"])
    stats["notes"] = list(dict.fromkeys(stats["notes"]))
    return stats


def test_feeds(langs):
    """Fetch one query per language and print how many items came back (nothing is saved)."""
    for code in langs:
        cfg = config.LANGUAGES[code]
        items = google_news.fetch(code, cfg, cfg["queries"][0])
        kept = sum(1 for i in items if filters.evaluate(code, i["title"], i["snippet"]))
        first = items[0]["title"][:70] if items else "-"
        print(f"{code:3} {cfg['name']:10} query {cfg['queries'][0]!r}: "
              f"{len(items):3} items, {kept:3} pass the filter | {first}")


def parse_date(text: str, flag: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise SystemExit(f"{flag} must look like 2026-06-01, not {text!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=3,
                        help="how far back to look (default 3; use 365 on the first run)")
    parser.add_argument("--from", dest="start_date", help="start date, e.g. 2026-06-01")
    parser.add_argument("--to", dest="end_date", help="end date (default: today)")
    parser.add_argument("--window-days", type=int, default=31,
                        help="split Google News searches into windows of this many days")
    parser.add_argument("--workers", type=int, default=1,
                        help="searches to run at the same time (default 1 = gentlest)")
    parser.add_argument("--sources", default="gnews,youtube,gdelt",
                        help="comma list of: gnews, youtube, gdelt")
    parser.add_argument("--langs", default="", help="comma list of language codes (default: all)")
    parser.add_argument("--no-ai", action="store_true", help="skip the Claude relevance check")
    parser.add_argument("--test", action="store_true", help="test feeds per language, save nothing")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    langs = [c.strip() for c in args.langs.split(",") if c.strip()] or list(config.LANGUAGES)
    unknown = [c for c in langs if c not in config.LANGUAGES]
    if unknown:
        raise SystemExit(f"Unknown language code(s): {', '.join(unknown)}")
    if args.test:
        test_feeds(langs)
        return

    end = parse_date(args.end_date, "--to") if args.end_date else today_ist()
    start = parse_date(args.start_date, "--from") if args.start_date else end - timedelta(days=args.days)
    if start > end:
        raise SystemExit("--from is after --to")

    def show(done, total, message, added):
        if total and done and (done % 25 == 0 or done == total):
            log.info("%s: %d of %d searches done, %d new stories", message, done, total, added)

    log.info("Collecting %s to %s", start, end)
    conn = db.connect()
    stats = collect_range(conn, start, end, langs, args.sources.split(","),
                          use_ai=not args.no_ai, workers=args.workers,
                          window_days=args.window_days, progress=show)
    for note in stats["notes"]:
        log.warning(note)
    log.info("Finished. Looked at %d items, added %d new.", stats["seen"], stats["added"])


if __name__ == "__main__":
    main()
