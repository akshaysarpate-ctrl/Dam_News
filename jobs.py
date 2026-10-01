"""Runs one internet search at a time in the background so the page stays responsive.

The website starts a job with jobs.start(...) and polls jobs.snapshot() for progress.
"""
import logging
import threading

import collect
import config
import db

import time

log = logging.getLogger("jobs")
_lock = threading.Lock()
_state = {"status": "idle", "message": "", "done": 0, "total": 0, "added": 0,
          "seen": 0, "start": "", "end": "", "notes": [], "error": "",
          "started_at": 0, "finished_at": ""}


def snapshot() -> dict:
    with _lock:
        snap = dict(_state)
        snap["notes"] = list(_state["notes"])
    snap["percent"] = int(100 * snap["done"] / snap["total"]) if snap["total"] else 0
    return snap


def _update(**fields):
    with _lock:
        _state.update(fields)


def start(start_date, end_date, langs, sources, ai_limit=120,
          workers=None, window_days=31) -> bool:
    """Start a search. Returns False if one is already actively running."""
    if workers is None:
        workers = config.SEARCH_WORKERS
    with _lock:
        if _state["status"] == "running":
            # If the previous job has been running for > 3 minutes, consider it stale/timed out
            if time.time() - _state.get("started_at", 0) > 180:
                log.warning("Previous job appears stuck (>180s) - overriding with new search")
            else:
                return False
        _state.update(status="running", message="Starting", done=0, total=0, added=0, seen=0,
                      start=start_date.isoformat(), end=end_date.isoformat(), notes=[], error="",
                      started_at=time.time())
    threading.Thread(target=_work,
                     args=(start_date, end_date, langs, sources, ai_limit, workers, window_days),
                     daemon=True).start()
    return True


def _work(start_date, end_date, langs, sources, ai_limit, workers, window_days):
    conn = None
    try:
        conn = db.connect()

        def progress(done, total, message, added):
            _update(done=done, total=total, message=message, added=added)

        stats = collect.collect_range(conn, start_date, end_date, langs, sources,
                                      use_ai=True, workers=workers,
                                      window_days=window_days,
                                      ai_limit=ai_limit, progress=progress)
        _update(status="done", message="Finished", added=stats["added"], seen=stats["seen"],
                notes=stats["notes"], done=1, total=1, finished_at=db.now_iso())
    except Exception as exc:  # anything unexpected: report it on the page instead of dying silently
        log.exception("Search job failed")
        _update(status="error", message="The search stopped because of an error.",
                error=f"{type(exc).__name__}: {str(exc)[:200]}")
    finally:
        if conn:
            conn.close()
