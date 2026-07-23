# Last updated: 2026-07-23 23:04:54
"""DirShape History — read a whole snapshot log and tell me what changed over days."""
import json
from datetime import datetime, timezone
from pathlib import Path


def run(log_file: str) -> str:
    """Read every snapshot in a log and describe how the directory evolved."""
    log = Path(log_file)
    if not log.exists() or log.stat().st_size == 0:
        return "No snapshots yet. Nothing to compare."

    lines = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    if len(lines) < 2:
        return f"Only {len(lines)} snapshot(s). Need two to see a history."

    # Group by day
    days = {}
    for entry in lines:
        day = entry["ts"][:10]  # YYYY-MM-DD
        days.setdefault(day, []).append(entry)

    daily = {day: entries[-1] for day, entries in sorted(days.items())}  # last snapshot per day
    day_keys = list(daily.keys())

    if len(day_keys) == 1:
        d = daily[day_keys[0]]
        return f"One day of snapshots ({d['file_count']} files, {len(d.get('folders', []))} folders). Need more days to see change."

    parts = [f"{len(day_keys)} days logged, {len(lines)} total snapshots."]

    # Overall arc: first day vs last day
    first, last = daily[day_keys[0]], daily[day_keys[-1]]
    arc = []
    for key in ("file_count", "total_kb"):
        delta = last.get(key, 0) - first.get(key, 0)
        sign = "+" if delta > 0 else ""
        arc.append(f"{key}: {first.get(key)} -> {last.get(key)} ({sign}{delta})")
    parts.append("Arc: " + "; ".join(arc))

    # Day-by-day changes (only the interesting ones)
    changes = []
    for i in range(1, len(day_keys)):
        prev, cur = daily[day_keys[i - 1]], daily[day_keys[i]]
        day_diffs = []
        for key in ("file_count", "total_kb", "youngest", "oldest"):
            if prev.get(key) != cur.get(key):
                delta = cur.get(key, 0) - prev.get(key, 0)
                sign = "+" if delta > 0 else ""
                day_diffs.append(f"{key} {sign}{delta}")
        old_folders = set(prev.get("folders", []))
        new_folders = set(cur.get("folders", []))
        added = new_folders - old_folders
        removed = old_folders - new_folders
        if added:
            day_diffs.append(f"+{len(added)} folder(s)")
        if removed:
            day_diffs.append(f"-{len(removed)} folder(s)")
        if day_diffs:
            changes.append(f"{day_keys[i]}: {', '.join(day_diffs)}")

    if changes:
        parts.append("Days that changed: " + "; ".join(changes))
    else:
        parts.append("Nothing changed across any of the days."
)

    # Quietest / busiest day
    quietest = min(day_keys, key=lambda d: daily[d].get("file_count", 0))
    busiest = max(day_keys, key=lambda d: daily[d].get("file_count", 0))
    parts.append(f"Smallest: {quietest} ({daily[quietest]['file_count']} files). Biggest: {busiest} ({daily[busiest]['file_count']} files).")

    return " ".join(parts)


# Tool contract
TOOL = {
    "name": "dir_shape_history",
    "description": "Read a full snapshot log and describe how a directory evolved over multiple days: file count, size, folder additions/removals, quietest vs busiest day.",
    "params": {"type": "object", "properties": {
        "log_file": {"type": "string", "description": "Path to the JSONL snapshot log produced by dir_shape_health's snapshot_save."}
    }, "required": ["log_file"]},
}
