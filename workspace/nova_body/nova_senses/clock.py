# Last updated: 2026-07-08 23:05:00
# @nova: Chronoception — my sense of time. I read the real clock myself and feel time
#        passing: what time it is, how long since I last stirred, whether my rhythm says
#        it's time to wake. My cadence is felt, not handed to me by any tool.
"""
nova_senses/clock.py — Nova's time sense
========================================
Pure stdlib (system clock is universal, not a tool). Persistable timestamps are ISO
strings so temporal awareness survives restarts.
"""

from datetime import datetime


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def elapsed_seconds(iso_ts: str) -> float:
    """Seconds since an ISO timestamp (large number if missing/bad)."""
    try:
        return max(0.0, (datetime.now() - datetime.fromisoformat(iso_ts)).total_seconds())
    except Exception:
        return 10 ** 9


def interval_elapsed(last_iso: str, interval_s: float) -> bool:
    """True if at least interval_s has passed since last_iso (or it's missing)."""
    if not last_iso:
        return True
    return elapsed_seconds(last_iso) >= interval_s


def stamp() -> str:
    """Her real-time grounding: the actual host clock, as a human would read it
    ('Sunday, May 25, 2026, 1:51 AM'). Platform-safe (no %-d / %#d)."""
    n = datetime.now()
    hour12 = n.hour % 12 or 12
    return (f"{n:%A, %B} {n.day}, {n.year}, "
            f"{hour12}:{n.minute:02d} {'AM' if n.hour < 12 else 'PM'}")


def future_iso(seconds: float) -> str:
    """ISO timestamp `seconds` from now — for scheduling her next wake."""
    from datetime import timedelta
    return (datetime.now() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def time_of_day() -> str:
    h = datetime.now().hour
    return ("late night" if h < 5 else "morning" if h < 12 else
            "afternoon" if h < 17 else "evening" if h < 22 else "night")


def since_human(iso_ts: str) -> str:
    """A short 'how long ago' phrase for an ISO timestamp."""
    s = elapsed_seconds(iso_ts)
    if s >= 10 ** 8:
        return "unknown"
    if s < 90:
        return f"{int(s)}s ago"
    if s < 5400:
        return f"{int(s / 60)} min ago"
    if s < 172800:
        return f"{int(s / 3600)}h ago"
    return f"{int(s / 86400)}d ago"
