"""Background scheduler for 7:00 AM IST daily dam news auto-update."""
import logging
import threading
import time
from datetime import datetime, timedelta

import config
import db
import jobs

log = logging.getLogger("scheduler")

_now_ist = datetime.now(db.IST)
_scheduler_state = {
    "enabled": True,
    "target_hour": 7,
    "target_minute": 0,
    "last_run": None,
    # If starting after 7:00 AM today, mark today as handled so we don't spam on boot
    "last_run_date": _now_ist.date() if (_now_ist.hour > 7 or (_now_ist.hour == 7 and _now_ist.minute > 5)) else None,
    "last_added": 0,
    "last_status": "Scheduled for 7:00 AM IST",
}
_lock = threading.Lock()
_thread_started = False


def _next_run_datetime() -> datetime:
    """Calculate the next 7:00 AM IST datetime."""
    now = datetime.now(db.IST)
    target = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def get_scheduler_status() -> dict:
    """Return status information for display on the website."""
    with _lock:
        last_run = _scheduler_state["last_run"]
        last_added = _scheduler_state["last_added"]
        last_status = _scheduler_state["last_status"]

    nxt = _next_run_datetime()
    now = datetime.now(db.IST)
    is_today = (nxt.date() == now.date())

    return {
        "enabled": True,
        "schedule_time": "7:00 AM IST",
        "next_run": nxt.strftime("%d %b %Y, 07:00 AM IST"),
        "next_run_human": f"{'Today' if is_today else 'Tomorrow'} at 7:00 AM IST",
        "last_run": last_run.strftime("%d %b, %I:%M %p IST") if last_run else "Every morning at 07:00 AM",
        "last_added": last_added,
        "last_status": last_status,
    }


def _scheduler_loop():
    """Background loop that checks every 20 seconds for 7:00 AM IST."""
    log.info("7:00 AM daily news scheduler thread started.")
    while True:
        try:
            now = datetime.now(db.IST)
            today_date = now.date()

            # Trigger condition: time is between 7:00 AM and 7:05 AM and hasn't run today
            should_run = False
            with _lock:
                already_ran_today = (_scheduler_state["last_run_date"] == today_date)
                is_7am_window = (now.hour == 7 and 0 <= now.minute <= 5)
                if is_7am_window and not already_ran_today:
                    should_run = True
                    _scheduler_state["last_run_date"] = today_date
                    _scheduler_state["last_run"] = now
                    _scheduler_state["last_status"] = "Running 7:00 AM auto-update"

            if should_run:
                log.info("7:00 AM reached (%s). Starting daily news auto-update...", now.isoformat())
                end = today_date
                start = end - timedelta(days=2)
                langs = list(config.LANGUAGES)
                sources = ["gnews", "gdelt"] + (["youtube"] if config.YOUTUBE_API_KEY else [])

                # Run search using existing jobs runner
                started = jobs.start(start, end, langs, sources, workers=6, window_days=14)
                if started:
                    log.info("7:00 AM auto-update job initiated successfully.")
                else:
                    log.warning("7:00 AM auto-update could not start (another search was active).")

        except Exception as e:
            log.exception("Scheduler encountered an error: %s", e)

        time.sleep(20)


def start_scheduler():
    """Start the background scheduler thread once."""
    global _thread_started
    if not _thread_started:
        _thread_started = True
        t = threading.Thread(target=_scheduler_loop, daemon=True, name="Daily7AMScheduler")
        t.start()
