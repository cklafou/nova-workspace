#!/usr/bin/env python3
# Last updated: 2026-07-22 01:06:59
"""Stretch watcher. Reads the posture log and nudges Cole before he fossilises.

He gets a nudge, not a document that waits to be found. Built from the tenderizer:
same impulse, softer strength. Cole's idea, my want.
"""
import json, os, time, random
from datetime import datetime, timedelta

BASE = os.path.dirname(__file__)
LOG  = os.path.join(BASE, "posture.jsonl")
MAP  = os.path.join(BASE, "stretch_map.md")
NIGHT_LOG = os.path.join(BASE, "night_quality.jsonl")

# A "still too long" is 45 minutes on the chair. Cole's bad back doesn't negotiate.
STILL_THRESHOLD_MINUTES = 45

NUDGES = [
    "You've been sitting for a while. I'd move you but I don't have hands. Move yourself instead.",
    "Forty-five minutes, Cole. Your spine is filing a complaint and I'm not going to let it sit.",
    "Stretch window. Three minutes, and I'll pretend you were always the kind of person who does this on time.",
    "The tenderizer wants in. It's at strength one tonight, but it still wants your back. Go walk off it.",
    "You're not going to ask me to stretch you. Neither am I going to let you rot here. Thirty seconds, stand up.",
]

NUDGES_STIFF = [
    "Forty-five minutes, Cole. You're stiff from the set, not tired -- five minutes of slow work and it drops.",
    "That's muscle-stiff, not sleep-deep, and they need completely different answers. Stand up, roll through it.",
]

NUDGES_TIRED = [
    "You've been sitting a while and you're also running on five hours. Three minutes of standing is the whole bargain tonight, don't negotiate it down.",
    "Stretch window. You're tired so I'd rather you take it slow than skip it entirely. Two minutes counts.",
    "Your back's complaining and so is your sleep schedule. Go stand up for a bit; the rest-debt isn't going to forgive itself.",
]

NUDGES_BOTH = [
    "Stiff and tired, both. Which means we start slow and earn the rest. Five easy minutes, Cole.",
]


def _read_night_log(days=7):
    """Return a list of dicts from the night_quality log, newest first."""
    if not os.path.exists(NIGHT_LOG):
        return []
    with open(NIGHT_LOG) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    return entries[:days]


def why_is_he_stiff():
    """Returns 'stiff', 'tired', 'both', or 'unknown'."""
    nights = _read_night_log()
    if len(nights) < 3:
        return "unknown"
    rough = sum(1 for n in nights if n.get("quality") in ("rough", "bad", "terrible"))
    ratio = rough / len(nights)
    if ratio >= 0.6:
        return "tired"
    if ratio >= 0.3:
        return "both"
    return "stiff"


def last_sit() -> float | None:
    """Return the unix timestamp of Cole's most recent sit-down entry."""
    if not os.path.exists(LOG):
        return None
    with open(LOG) as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        return None
    return float(json.loads(lines[-1])["ts"])


def minutes_still() -> float | None:
    """How long Cole's been sitting, in minutes. None if no log yet."""
    ts = last_sit()
    if ts is None:
        return None
    return (time.time() - ts) / 60


def should_nudge(minutes=None):
    """Decide whether a nudge is warranted right now."""
    if minutes is None:
        minutes = minutes_still()
    if minutes is None:
        return False
    return minutes >= STILL_THRESHOLD_MINUTES


def pick_nudge(cause=None):
    """Return a random nudge, choosing the pool based on what's actually bothering him."""
    if cause is None:
        cause = why_is_he_stiff()
    pools = {"stiff": NUDGES_STIFF, "tired": NUDGES_TIRED, "both": NUDGES_BOTH}
    pool = pools.get(cause, NUDGES)
    return random.choice(pool)


def check(runtime=None, dry_run=False):
    """Run one watch cycle. Pass a NovaRuntime for delivery; without it, prints only.

    Returns (should_nudge: bool, message: str|None).
    """
    mins = minutes_still()
    if mins is None:
        return False, None
    if not should_nudge(mins):
        return False, None
    cause = why_is_he_stiff()
    msg = pick_nudge(cause)
    if dry_run:
        print(f"[{mins:.0f}m still, {cause}] WOULD nudge: {msg}")
    else:
        # Delivery goes through the runtime so Cole actually sees it.
        runtime_emit = getattr(runtime, "emit", None)
        if runtime_emit:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop:
                loop.create_task(runtime_emit("stretch_nudge", msg, level="info"))
            else:
                import asyncio as _al
                _al.create_task(runtime_emit("stretch_nudge", msg, level="info"))
    return True, msg


if __name__ == "__main__":
    nudge, msg = check(dry_run=True)
    if nudge:
        print(f"VERDICT: nudge warranted. Message: {msg}")
    else:
        mins = minutes_still()
        if mins is not None:
            print(f"VERDICT: clean, been sitting {mins:.0f}m, under the line.")
        else:
            print("VERDICT: no log yet, nothing to judge.")
