"""Web interface. Run:  python app.py   then open http://127.0.0.1:5000"""
import csv
import io
import math
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, url_for

import config
import db
import deep_search
import jobs
import scheduler
import util

app = Flask(__name__)
# Start daily 7 AM IST scheduler (works under Gunicorn and standalone)
scheduler.start_scheduler()
IST = db.IST
UTC = timezone.utc
PAGE_SIZE = 40
DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"
MAX_RANGE_DAYS = 366

# Track the last article id seen per search so we can stream newly found articles
_live_last_id = 0

DAY_TABS = {
    "today":     {"label": "Today",               "offset": 0},
    "yesterday": {"label": "Yesterday",           "offset": 1},
    "dby":       {"label": "Day before yesterday", "offset": 2},
}

PERIODS = {
    "1m": {"label": "1 month", "days": 30},
    "3m": {"label": "3 months", "days": 90},
    "6m": {"label": "6 months", "days": 180},
    "1y": {"label": "1 year", "days": 365},
}

NOTICES = {
    "busy": "A search is already running. Wait for it to finish, then try again.",
    "range": "Choose a From and a To date, written like 2026-06-01, with From on or before To.",
    "toolong": "Choose a range of one year or less. For longer periods, search one year at a time.",
    "nolangs": "Tick at least one language to search.",
    "refreshed": "Refresh started — fetching the latest news from the last 3 days.",
}

# Workers for web-initiated search (higher = faster but more aggressive)
WEB_SEARCH_WORKERS = 6
WEB_WINDOW_DAYS = 14


def today() -> date:
    return datetime.now(IST).date()


# ---------------------------------------------------------------- date range and filters
def parse_range(start_text, end_text):
    """Return (start, end, error_key). Dates are India dates; end is clamped to today."""
    try:
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    except ValueError:
        return None, None, "range"
    end = min(end, today())
    if start > end:
        return None, None, "range"
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        return None, None, "toolong"
    return start, end, ""


def parse_filters():
    a = request.args
    period = a.get("period", "3m")
    day = a.get("day", "")
    try:
        page = max(1, int(a.get("page", 1)))
    except ValueError:
        page = 1
    f = {
        "period": period if period in PERIODS else "3m",
        "day": day if day in DAY_TABS else "",
        "lang": a.get("lang", ""),
        "state": a.get("state", ""),
        "kind": a.get("kind", "") if a.get("kind") in ("article", "video") else "",
        "q": a.get("q", "").strip(),
        "maybe": a.get("maybe") == "1",
        "page": page,
        "custom": a.get("custom") == "1",
        "start": None, "end": None, "error": "",
    }
    s, e = a.get("start", "").strip(), a.get("end", "").strip()
    if s or e:
        start, end, err = parse_range(s, e)
        if err:
            f["error"] = NOTICES[err]
        else:
            f["start"], f["end"] = start, end
    return f


def bucket_for(span_days):
    if span_days <= 1:
        return 1, "hour"    # single-day view uses hourly buckets
    if span_days <= 45:
        return 1, "day"
    if span_days <= 200:
        return 7, "week"
    return 14, "fortnight"


def view_window(f):
    """The date span being shown: a day tab, a period tab, or a custom From/To."""
    day_key = f.get("day")
    if f["start"]:
        start, end, custom = f["start"], f["end"], True
        phrase = (f"on {start:%d %b %Y}" if start == end
                  else f"from {start:%d %b %Y} to {end:%d %b %Y}")
    elif f.get("custom"):
        end, custom = today(), True
        start = end - timedelta(days=30)
        phrase = f"from {start:%d %b %Y} to {end:%d %b %Y}"
    elif day_key and day_key in DAY_TABS:
        d = today() - timedelta(days=DAY_TABS[day_key]["offset"])
        start = end = d
        custom = False
        phrase = f"on {d:%A, %d %b %Y}" if day_key != "today" else "today"
    else:
        p = PERIODS[f["period"]]
        end, custom = today(), False
        start = end - timedelta(days=p["days"])
        phrase = f"in the last {p['label']}"
    span = (end - start).days + 1
    bucket, unit = bucket_for(span)
    return {"start": start, "end": end, "custom": custom, "phrase": phrase,
            "bucket": bucket, "unit": unit, "day": day_key or ""}


def build_where(f, view, skip=()):
    lo = datetime.combine(view["start"], time.min, tzinfo=IST).astimezone(UTC).strftime(DATE_FMT)
    hi = datetime.combine(view["end"] + timedelta(days=1), time.min,
                          tzinfo=IST).astimezone(UTC).strftime(DATE_FMT)
    where, params = ["published_at >= ?", "published_at < ?"], [lo, hi]
    where.append("status IN ('relevant','maybe')" if f["maybe"] else "status = 'relevant'")
    if f["lang"] and "lang" not in skip:
        where.append("language = ?"); params.append(f["lang"])
    if f["state"] and "state" not in skip:
        where.append("state = ?"); params.append(f["state"])
    if f["kind"] and "kind" not in skip:
        where.append("kind = ?"); params.append(f["kind"])
    if f["q"]:
        where.append("(title LIKE ? OR snippet LIKE ? OR dam_name LIKE ?)")
        params += [f"%{f['q']}%"] * 3
    return " AND ".join(where), params


def histogram(dates, view):
    start, end, bucket = view["start"], view["end"], view["bucket"]
    unit = view["unit"]

    # Single-day view: show 24 hourly bars
    if unit == "hour":
        n = 24
        counts = [0] * n
        for d in dates:
            dt = datetime.strptime(d, DATE_FMT).replace(tzinfo=UTC).astimezone(IST)
            if dt.date() == start:
                counts[dt.hour] += 1
        peak = max(counts) or 1
        bars = []
        for h, c in enumerate(counts):
            label = f"{h:02d}:00"
            bars.append({"count": c, "pct": round(100 * c / peak), "label": label})
        return bars, max(counts)

    # Multi-day view (unchanged logic)
    n = math.ceil(((end - start).days + 1) / bucket)
    counts = [0] * n
    for d in dates:
        day = datetime.strptime(d, DATE_FMT).replace(tzinfo=UTC).astimezone(IST).date()
        i = n - 1 - max(0, (end - day).days) // bucket
        if 0 <= i < n:
            counts[i] += 1
    peak = max(counts) or 1
    bars = []
    for i, c in enumerate(counts):
        bar_end = end - timedelta(days=(n - 1 - i) * bucket)
        bar_start = max(start, bar_end - timedelta(days=bucket - 1))
        label = f"{bar_end:%d %b}" if bucket == 1 else f"{bar_start:%d %b} to {bar_end:%d %b}"
        bars.append({"count": c, "pct": round(100 * c / peak), "label": label})
    return bars, max(counts)


def trend_chart(dates, view):
    """Generate SVG trend line and area graph coordinates for timeline visualization."""
    start, end, bucket = view["start"], view["end"], view["bucket"]
    unit = view["unit"]

    if unit == "hour":
        n = 24
        counts = [0] * n
        for d in dates:
            dt = datetime.strptime(d, DATE_FMT).replace(tzinfo=UTC).astimezone(IST)
            if dt.date() == start:
                counts[dt.hour] += 1
        labels = [f"{h:02d}:00" for h in range(24)]
    else:
        n = math.ceil(((end - start).days + 1) / bucket)
        n = max(2, n)
        counts = [0] * n
        for d in dates:
            day = datetime.strptime(d, DATE_FMT).replace(tzinfo=UTC).astimezone(IST).date()
            i = n - 1 - max(0, (end - day).days) // bucket
            if 0 <= i < n:
                counts[i] += 1
        labels = []
        for i in range(n):
            b_end = end - timedelta(days=(n - 1 - i) * bucket)
            b_start = max(start, b_end - timedelta(days=bucket - 1))
            labels.append(f"{b_end:%d %b}" if bucket == 1 else f"{b_start:%d %b} – {b_end:%d %b}")

    peak = max(counts) if counts else 0
    effective_peak = peak if peak > 0 else 1

    W, H = 800, 110
    pad_x, pad_top, base_y = 24, 14, 94
    chart_w = W - 2 * pad_x
    chart_h = base_y - pad_top

    points = []
    for i, c in enumerate(counts):
        x = round(pad_x + (i / max(1, n - 1)) * chart_w, 1)
        y = round(base_y - (c / effective_peak) * chart_h, 1)
        points.append({
            "x": x,
            "y": y,
            "count": c,
            "label": labels[i],
            "pct": round(100 * c / effective_peak),
        })

    line_path = "M " + " L ".join(f"{p['x']},{p['y']}" for p in points)
    area_path = (f"M {points[0]['x']},{base_y} "
                 + " ".join(f"L {p['x']},{p['y']}" for p in points)
                 + f" L {points[-1]['x']},{base_y} Z")

    return {
        "points": points,
        "line_path": line_path,
        "area_path": area_path,
        "peak": peak,
        "unit": unit,
        "base_y": base_y,
        "mid_y": round(base_y - chart_h / 2, 1),
        "top_y": pad_top,
        "mid_val": math.ceil(peak / 2) if peak > 1 else "",
        "start_label": labels[0] if labels else "",
        "end_label": labels[-1] if labels else "",
        "total_stories": sum(counts),
    }


# ---------------------------------------------------------------- template helpers
def _parse(s):
    return datetime.strptime(s, DATE_FMT).replace(tzinfo=UTC)


@app.template_filter("ist_date")
def ist_date(s):
    return _parse(s).astimezone(IST).strftime("%d %b %Y")


@app.template_filter("ist_datetime")
def ist_datetime(s):
    return _parse(s).astimezone(IST).strftime("%d %b %Y, %H:%M IST")


@app.template_filter("ago")
def ago(s):
    if not s:
        return ""
    dt_ist = _parse(s).astimezone(IST)
    now_ist = datetime.now(IST)
    cal_days = (now_ist.date() - dt_ist.date()).days
    if cal_days <= 0:
        sec = int((now_ist - dt_ist).total_seconds())
        if sec < 120:
            return "just now"
        hours = sec // 3600
        if hours <= 0:
            mins = max(1, sec // 60)
            return f"{mins}m ago"
        return f"{hours}h ago"
    if cal_days == 1:
        return "yesterday"
    if cal_days == 2:
        return "2 days ago"
    if cal_days < 14:
        return f"{cal_days} days ago"
    if cal_days < 60:
        weeks = cal_days // 7
        return f"{weeks} {'week' if weeks == 1 else 'weeks'} ago"
    months = cal_days // 30
    return f"{months} {'month' if months == 1 else 'months'} ago"


@app.template_filter("lang_name")
def lang_name(code):
    return config.LANGUAGES.get(code, {}).get("name", "Other")


@app.template_filter("lang_native")
def lang_native(code):
    return config.LANGUAGES.get(code, {}).get("native", "Other")


@app.context_processor
def helpers():
    def qs(**changes):
        args = {k: v for k, v in request.args.items() if k not in ("page", "notice")}
        for key, value in changes.items():
            if value in (None, ""):
                args.pop(key, None)
            else:
                args[key] = value
        return url_for("index", **args)
    return {
        "qs": qs,
        "PERIODS": PERIODS,
        "DAY_TABS": DAY_TABS,
        "scheduler": scheduler.get_scheduler_status(),
    }


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    f = parse_filters()
    view = view_window(f)
    conn = db.connect()
    where, params = build_where(f, view)

    total = conn.execute(f"SELECT COUNT(*) FROM articles WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM articles WHERE {where} ORDER BY published_at DESC LIMIT ? OFFSET ?",
        params + [PAGE_SIZE, (f["page"] - 1) * PAGE_SIZE]).fetchall()

    w, p = build_where(f, view, skip={"lang"})
    langs = conn.execute(f"SELECT language, COUNT(*) AS c FROM articles WHERE {w} "
                         "GROUP BY language ORDER BY c DESC", p).fetchall()
    w, p = build_where(f, view, skip={"state"})
    states = conn.execute(f"SELECT state, COUNT(*) AS c FROM articles WHERE {w} AND state != '' "
                          "GROUP BY state ORDER BY state", p).fetchall()
    w, p = build_where(f, view, skip={"kind"})
    kinds = {r["kind"]: r["c"] for r in conn.execute(
        f"SELECT kind, COUNT(*) AS c FROM articles WHERE {w} GROUP BY kind", p)}

    dates = [r[0] for r in conn.execute(f"SELECT published_at FROM articles WHERE {where}", params)]
    bars, peak = histogram(dates, view)
    trend = trend_chart(dates, view)
    last = conn.execute("SELECT finished_at FROM runs WHERE finished_at IS NOT NULL "
                        "ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    job = jobs.snapshot()
    job["this_range"] = (job["start"] == view["start"].isoformat()
                         and job["end"] == view["end"].isoformat())
    return render_template(
        "index.html", f=f, view=view, total=total, rows=rows,
        langs=langs, lang_total=sum(r["c"] for r in langs), states=states, kinds=kinds,
        bars=bars, peak=peak, trend=trend, pages=max(1, math.ceil(total / PAGE_SIZE)),
        last_run=last["finished_at"] if last else None,
        notice=f["error"] or NOTICES.get(request.args.get("notice", ""), ""),
        job=job, today=today().isoformat(), has_youtube=bool(config.YOUTUBE_API_KEY),
        all_langs=[{"code": c, "name": v["name"], "native": v["native"]}
                   for c, v in config.LANGUAGES.items()])


@app.post("/search-web")
def search_web():
    """Start a live internet search for the chosen dates, then show the page with progress."""
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        abort(403)
    start, end, err = parse_range(request.form.get("start", ""), request.form.get("end", ""))
    if err:
        return redirect(url_for("index", notice=err))
    langs = [c for c in request.form.getlist("search_langs") if c in config.LANGUAGES]
    if not langs:
        return redirect(url_for("index", start=start.isoformat(), end=end.isoformat(), notice="nolangs"))
    sources = ["gnews", "gdelt"] + (["youtube"] if config.YOUTUBE_API_KEY else [])
    started = jobs.start(start, end, langs, sources,
                         workers=WEB_SEARCH_WORKERS, window_days=WEB_WINDOW_DAYS)
    args = {"start": start.isoformat(), "end": end.isoformat()}
    if not started:
        args["notice"] = "busy"
    return redirect(url_for("index", **args))


@app.post("/refresh")
def refresh():
    """One-click refresh: search the last 3 days for all languages."""
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        abort(403)
    end = today()
    start = end - timedelta(days=2)
    langs = list(config.LANGUAGES)
    sources = ["gnews", "gdelt"] + (["youtube"] if config.YOUTUBE_API_KEY else [])
    started = jobs.start(start, end, langs, sources,
                         workers=WEB_SEARCH_WORKERS, window_days=WEB_WINDOW_DAYS)
    args = {"start": start.isoformat(), "end": end.isoformat()}
    if not started:
        args["notice"] = "busy"
    return redirect(url_for("index", **args))


@app.route("/search-name")
def search_name():
    """Search by dam/place name — with deep internet search across all national and regional newspapers."""
    name = request.args.get("name", "").strip()
    deep = request.args.get("deep", "1" if request.args.get("submitted") else "")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    lang = request.args.get("lang", "")
    state = request.args.get("state", "")
    kind = request.args.get("kind", "")
    if kind not in ("article", "video", ""):
        kind = ""

    conn = db.connect()
    deep_stats = None

    if name:
        base_name, _ = deep_search.clean_search_name(name)

        # Trigger deep internet search across newspapers if deep=1
        if deep == "1":
            deep_stats = deep_search.run_deep_search(conn, name)

        # Search across title, snippet, dam_name, state, district
        # Matches either the full name or the base name
        like_full = f"%{name}%"
        like_base = f"%{base_name}%"
        clauses = ["(title LIKE ? OR snippet LIKE ? OR dam_name LIKE ? OR state LIKE ? OR district LIKE ? "
                   "OR title LIKE ? OR snippet LIKE ? OR dam_name LIKE ?)"]
        params = [like_full, like_full, like_full, like_full, like_full,
                  like_base, like_base, like_base]
        clauses.append("status IN ('relevant','maybe')")
        if lang:
            clauses.append("language = ?"); params.append(lang)
        if state:
            clauses.append("state = ?"); params.append(state)
        if kind:
            clauses.append("kind = ?"); params.append(kind)
        where = " AND ".join(clauses)

        total = conn.execute(f"SELECT COUNT(*) FROM articles WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM articles WHERE {where} ORDER BY published_at DESC LIMIT ? OFFSET ?",
            params + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()

        # Sidebar facets — use base query (name + status only, no lang/state/kind filters)
        base_where = ("(title LIKE ? OR snippet LIKE ? OR dam_name LIKE ? OR state LIKE ? OR district LIKE ? "
                      "OR title LIKE ? OR snippet LIKE ? OR dam_name LIKE ?) "
                      "AND status IN ('relevant','maybe')")
        bp = [like_full, like_full, like_full, like_full, like_full,
              like_base, like_base, like_base]

        langs = conn.execute(f"SELECT language, COUNT(*) AS c FROM articles WHERE {base_where} "
                             "GROUP BY language ORDER BY c DESC", bp).fetchall()
        states = conn.execute(f"SELECT state, COUNT(*) AS c FROM articles WHERE {base_where} AND state != '' "
                              "GROUP BY state ORDER BY state", bp).fetchall()
        kinds_rows = conn.execute(
            f"SELECT kind, COUNT(*) AS c FROM articles WHERE {base_where} GROUP BY kind", bp).fetchall()
        kinds = {r["kind"]: r["c"] for r in kinds_rows}

        # Histogram by date
        dates = [r[0] for r in conn.execute(
            f"SELECT published_at FROM articles WHERE {where}", params)]
        if dates:
            all_dt = [datetime.strptime(d, DATE_FMT).replace(tzinfo=UTC).astimezone(IST).date() for d in dates]
            d_start, d_end = min(all_dt), max(all_dt)
            span = (d_end - d_start).days + 1
            bucket, unit = bucket_for(span)
            fake_view = {"start": d_start, "end": d_end, "bucket": bucket, "unit": unit}
            bars, peak = histogram(dates, fake_view)
            trend = trend_chart(dates, fake_view)
            view_phrase = f"from {d_start:%d %b %Y} to {d_end:%d %b %Y}"
        else:
            bars, peak = [], 0
            trend = None
            d_start = d_end = today()
            unit = "day"
            view_phrase = ""
    else:
        total = 0
        rows = []
        langs = []
        states = []
        kinds = {}
        bars = []
        peak = 0
        trend = None
        d_start = d_end = today()
        unit = "day"
        view_phrase = ""

    conn.close()

    return render_template(
        "search_name.html", name=name, total=total, rows=rows,
        langs=langs, lang_total=sum(r["c"] for r in langs),
        states=states, kinds=kinds,
        bars=bars, peak=peak, trend=trend,
        pages=max(1, math.ceil(total / PAGE_SIZE)),
        page=page, lang=lang, state_filter=state, kind=kind,
        view_start=d_start, view_end=d_end, unit=unit,
        view_phrase=view_phrase, deep=deep, deep_stats=deep_stats)


@app.get("/job")
def job_status():
    return jsonify(jobs.snapshot())


@app.get("/live-results")
def live_results():
    """Return newly found articles since the last poll. Called by JS during a running search."""
    after_id = request.args.get("after", 0, type=int)
    start_text = request.args.get("start", "")
    end_text = request.args.get("end", "")
    conn = db.connect()
    # Only return articles within the date range being searched
    clauses = ["id > ?"]
    params = [after_id]
    if start_text and end_text:
        try:
            s = date.fromisoformat(start_text)
            e = date.fromisoformat(end_text)
            lo = datetime.combine(s, time.min, tzinfo=IST).astimezone(UTC).strftime(DATE_FMT)
            hi = datetime.combine(e + timedelta(days=1), time.min, tzinfo=IST).astimezone(UTC).strftime(DATE_FMT)
            clauses += ["published_at >= ?", "published_at < ?"]
            params += [lo, hi]
        except ValueError:
            pass
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT id, kind, title, url, source, language, published_at, snippet, "
        f"thumbnail, state, district, dam_name, status "
        f"FROM articles WHERE {where} ORDER BY id ASC LIMIT 50", params).fetchall()
    conn.close()
    articles = []
    max_id = after_id
    for r in rows:
        max_id = max(max_id, r["id"])
        articles.append({
            "id": r["id"], "kind": r["kind"], "title": r["title"], "url": r["url"],
            "read_url": url_for("read_article", article_id=r["id"]),
            "source": r["source"] or "Unknown source",
            "language": config.LANGUAGES.get(r["language"], {}).get("name", "Other"),
            "published_at": r["published_at"],
            "published_display": ist_date(r["published_at"]),
            "ago": ago(r["published_at"]),
            "snippet": (r["snippet"] or "")[:220],
            "thumbnail": r["thumbnail"] or "",
            "state": r["state"] or "", "district": r["district"] or "",
            "dam_name": r["dam_name"] or "",
            "status": r["status"],
        })
    return jsonify({"articles": articles, "max_id": max_id})


@app.route("/read/<int:article_id>")
def read_article(article_id):
    """Safely open article directly at publisher website without intermediate redirect screens."""
    conn = db.connect()
    row = conn.execute("SELECT id, title, source, url FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)

    url = row["url"] or ""
    title = row["title"] or ""
    source = row["source"] or ""

    # If already a direct publisher URL (not Google News redirect), open immediately
    if url and "news.google.com" not in url and "google.com" not in url:
        return redirect(url, code=302)

    resolved = util.resolve_news_url(url, title=title, source=source)
    # If resolved to a clean publisher URL, persist to DB so next clicks are instant
    if resolved and "news.google.com" not in resolved and "google.com" not in resolved:
        try:
            conn = db.connect()
            conn.execute("UPDATE articles SET url = ? WHERE id = ?", (resolved, article_id))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return redirect(resolved, code=302)

    # In the rare event resolution fails, fallback to direct search query on DuckDuckGo
    if title:
        import urllib.parse
        target = f"https://duckduckgo.com/?q={urllib.parse.quote(f'{title} {source}'.strip())}"
        return redirect(target, code=302)

    return redirect(url, code=302)


@app.route("/export.csv")
def export_csv():
    f = parse_filters()
    view = view_window(f)
    conn = db.connect()
    where, params = build_where(f, view)
    rows = conn.execute(f"SELECT * FROM articles WHERE {where} ORDER BY published_at DESC",
                        params).fetchall()
    conn.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["published_utc", "title", "source", "language", "type", "state",
                     "district", "dam_name", "url"])
    for r in rows:
        writer.writerow([r["published_at"], r["title"], r["source"], r["language"], r["kind"],
                         r["state"], r["district"], r["dam_name"], r["url"]])
    # utf-8 with BOM so Excel shows Indian scripts correctly
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=dam_failure_news.csv"})


if __name__ == "__main__":
    scheduler.start_scheduler()
    app.run(host="127.0.0.1", port=5000, debug=False)
