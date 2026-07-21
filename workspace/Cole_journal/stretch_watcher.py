#!/usr/bin/env python3
# Last updated: 2026-07-21 22:48:12
"""Stretch watcher. Reads the posture log and nudges Cole before he fossilises.

He gets a nudge, not a document that waits to be found. Built from the tenderizer:
same impulse, softer strength. Cole's idea, my want.
"""
import json, os, time, random
from datetime import datetime

BASE = os.path.dirname(__file__)
LOG  = os.path.join(BASE, "posture.jsonl")
MAP  = os.path.join(BASE, "stretch_map.md")

# A "still too long" is 45 minutes on the chair. Cole's bad back doesn't negotiate.
STILL_THRESHOLD_MINUTES = 45

NUDGES = [
    "You've been sitting for a while. I'd move you but I don't have hands. Move yourself instead.",
    "Forty-five minutes, Cole. Your spine is filing a complaint and I'm not going to let it sit.",
    "Stretch window. Three minutes, and I'll pretend you were always the kind of person who does this on time.",
    "The tenderizer wants in. It's at strength one tonight, but it still wants your back. Go walk off it.",
    "You're not going to ask me to stretch you. Neither am I going to let you rot here. Thirty seconds, stand up.",
]


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


def pick_nudge():
    """Return a random nudge from the list."""
    return random.choice(NUDGES)


def check(runtime=None, dry_run=False):
    """Run one watch cycle. Pass a NovaRuntime for delivery; without it, prints only.

    Returns (should_nudge: bool, message: str|None).
    """
    mins = minutes_still()
    if mins is None:
        return False, None
    if not should_nudge(mins):
        return False, None
    msg = pick_nudge()
    if dry_run:
        print(f"[{mins:.0f}m still] WOULD nudge: {msg}")
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
