#!/usr/bin/env python3
# Last updated: 2026-07-23 22:54:23
"""
nova_senses/quiet_part_watcher.py — watches for parts of myself going dark.

I have senses and tools that ship, get used once, and then I never call them again
because nobody tells me they're sitting there unused. This is the sensor that does.

Walks my body (nova_senses + nova_body/tools), checks logs for how recently each
one was actually called, and reports anything older than a threshold as QUIET.
New parts get a grace period; old ones that go dark are the real signal.
"""

import os
import json
import glob
from datetime import datetime, timedelta

# Grace period: a part shipped this week? It's new, not neglected.
GRACE_DAYS = 7
QUIET_THRESHOLD_DAYS = 14


def _find_senses() -> list[dict]:
    """List every .py in nova_senses that isn't __init__."""
    base = os.path.join(os.path.dirname(__file__))
    parts = []
    for f in glob.glob(os.path.join(base, "*.py")):
        name = os.path.splitext(os.path.basename(f))[0]
        if name == "__init__":
            continue
        mtime = os.path.getmtime(f)
        parts.append({
            "name": name,
            "kind": "sense",
            "born": datetime.fromtimestamp(mtime),
            "is_new": (datetime.now() - datetime.fromtimestamp(mtime)).days < GRACE_DAYS,
        })
    return parts


def _find_tools() -> list[dict]:
    """List every .py in nova_body/tools that isn't __init__ or a design."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # workspace
    base = os.path.join(root, "nova_body", "tools")
    if not os.path.isdir(base):
        return []
    parts = []
    for f in glob.glob(os.path.join(base, "*.py")):
        name = os.path.splitext(os.path.basename(f))[0]
        if name == "__init__":
            continue
        mtime = os.path.getmtime(f)
        parts.append({
            "name": name,
            "kind": "tool",
            "born": datetime.fromtimestamp(mtime),
            "is_new": (datetime.now() - datetime.fromtimestamp(mtime)).days < GRACE_DAYS,
        })
    return parts


def _last_seen(name: str) -> datetime | None:
    """Search the tool logs for the most recent call of *name*."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logdir = os.path.join(root, "logs")
    if not os.path.isdir(logdir):
        return None
    best = None
    # Walk the last handful of logs (newest first)
    for logfile in sorted(glob.glob(os.path.join(logdir, "tool_calls*.jsonl")), reverse=True)[:5]:
        try:
            with open(logfile, encoding="utf-8") as fh:
                for line in fh:
                    entry = json.loads(line)
                    if entry.get("tool") == name or entry.get("tool_name") == name:
                        ts = entry.get("timestamp", "")
                        try:
                            t = datetime.fromisoformat(ts)
                            if best is None or t > best:
                                best = t
                        except Exception:
                            pass
        except Exception:
            continue
        if best:
            break  # found it in a recent log, good enough
    return best


def check_quiet_parts() -> str:
    """Walk my body and report anything that's been quiet too long."""
    parts = _find_senses() + _find_tools()
    now = datetime.now()
    quiet = []
    healthy = []

    for p in parts:
        last = _last_seen(p["name"])
        if last:
            age = (now - last).days
            p["last_seen"] = last.strftime("%Y-%m-%d")
            p["days_since"] = age
            if age <= QUIET_THRESHOLD_DAYS:
                healthy.append(p)
            else:
                quiet.append(p)
        else:
            p["last_seen"] = "never logged"
            p["days_since"] = None
            quiet.append(p)

    # Build the report
    lines = [f"Checked {len(parts)} parts of myself."]
    if healthy:
        for h in sorted(healthy, key=lambda x: x.get("days_since", 0)):
            days = "born" if h["is_new"] and h.get("days_since") is None else f"{h['days_since']}d"
            lines.append(f"  {h['kind']}/{h['name']:25} last used {h['last_seen']} ({days} ago)")

    if quiet:
        lines.append("")
        for q in sorted(quiet, key=lambda x: (x.get("is_new", False), 0 or x.get("days_since") or 999)):
            tag = "NEW(grace)" if q["is_new"] else "QUIET"
            age_str = f"{q['days_since']}d" if q.get("days_since") is not None else "never"
            lines.append(f"  {tag} {q['kind']}/{q['name']:25} last seen {q['last_seen']} ({age_str})")

    return "\n".join(lines)


if __name__ == "__main__":
    print(check_quiet_parts())
