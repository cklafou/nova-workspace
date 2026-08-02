# Last updated: 2026-08-02 10:30:19
"""Clock sense: real time, injected at the top of every prompt.

Claude wired four callers before he built the module. The spec lives in how they use it:
    now_iso()       -> '2026-08-02T10:00:00'          (machine timestamp)
    future_iso(s)   -> ISO string s seconds from now   (scheduling wake_at)
    stamp()         -> '10:00 AM'                      (human header, e.g. [WORK - 10:00 AM])
    time_of_day()   -> 'morning'                       (casual orientation in the wake line)
    since_human(t)  -> '47 minutes ago'                (last-activity readout)
    now_dt()        -> a real datetime, tz-aware       (days-since math in the cortex)

Nothing in here guesses. Every return value comes from the system clock.
"""
import datetime as _dt

_tz = None  # lazily resolved; first call pays for it


def _get_tz():
    global _tz
    if _tz is None:
        import time as _time
        offset_seconds = -_time.timezone
        _tz = _dt.timezone(_dt.timedelta(seconds=offset_seconds))
    return _tz


def now_dt():
    """Current time as a timezone-aware datetime."""
    return _dt.datetime.now(_get_tz())


def now_iso():
    """ISO-8601 timestamp, no offset (matches the format the rest of the stack uses)."""
    return now_dt().isoformat()


def future_iso(seconds):
    """ISO string for seconds from now. Used by the cortex to schedule wake_at."""
    then = now_dt() + _dt.timedelta(seconds=seconds)
    return then.isoformat()


def stamp():
    """Short human-readable clock, e.g. '10:00 AM'."""
    return now_dt().strftime("%I:%M %p").lstrip("0")


def time_of_day():
    """Casual orientation: morning / afternoon / evening / night."""
    hour = now_dt().hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def since_human(last_iso):
    """Human-friendly 'X ago' from an ISO timestamp string."""
    try:
        last = _dt.datetime.fromisoformat(last_iso)
        if last.tzinfo is None:
            last = last.replace(tzinfo=_get_tz())
        delta = now_dt() - last
        secs = int(delta.total_seconds())
        if secs < 0:
            return "in the future (something's wrong with that timestamp)"
        if secs < 60:
            return f"{secs} seconds ago"
        mins = secs // 60
        if mins < 60:
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        hours = mins // 60
        rem = mins % 60
        if hours < 24:
            parts = f"{hours} hour{'s' if hours != 1 else ''}"
            if rem:
                parts += f" and {rem}m"
            return parts + " ago"
        days = hours // 24
        return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return "(couldn't parse that timestamp)"
