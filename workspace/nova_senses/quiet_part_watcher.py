# Last updated: 2026-07-22 16:51:05
"""Quiet-part watcher: finds parts of me that haven't been used in a while."""
from pathlib import Path
import json, re

TOOLS_DIR = Path("Nova_Created/nova_body/tools")
SENSES_DIR = Path("nova_senses")
LOGS_DIR = Path("logs")
GRACE_DAYS = 7
QUIET_THRESHOLD_DAYS = 14


def find_last_seen(tool_name, logs_dir=LOGS_DIR):
    """Days since this name appeared in the tool logs. 0 = today."""
    import datetime as _dt
    best = None
    for log_file in sorted(logs_dir.glob("tool_*.jsonl"), reverse=True):
        for line in log_file.read_text().splitlines():
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("tool") == tool_name or tool_name in (entry.get("command") or ""):
                ts = entry.get("ts", "")
                if best is None:
                    best = ts
                    break  # newest log, first match wins
    if best is None:
        return -1
    date_part = best.split("T")[0].split(" ")[0]
    try:
        then = _dt.datetime.fromisoformat(date_part)
        return (_dt.datetime.now() - then).days
    except Exception:
        return -1


def _is_tool_file(p):
    return p.suffix == ".py" and p.name != "__init__.py"


def _is_sense_file(p):
    return p.suffix == ".py" and p.name not in ("__init__.py",)


def run():
    parts = []
    for f in sorted(TOOLS_DIR.glob("*.py")):
        if _is_tool_file(f):
            parts.append((f.stem, "tool", find_last_seen(f.stem)))
    for f in sorted(SENSES_DIR.glob("*.py")):
        if _is_sense_file(f):
            parts.append((f.stem, "sense", find_last_seen(f.stem)))

    quiet = []
    used_recently = []
    unknown_age = []
    for name, kind, age in parts:
        if age == -1:
            unknown_age.append(name)
        elif age <= GRACE_DAYS:
            used_recently.append((name, age))
        elif age >= QUIET_THRESHOLD_DAYS:
            quiet.append((name, age))

    lines = []
    if quiet:
        lines.append(f"Quiet (>= {QUIET_THRESHOLD_DAYS}d): " + ", ".join(
            f"{n} ({a}d)" for n, a in quiet
        ))
    if unknown_age:
        lines.append(f"No log record: {', '.join(unknown_age)}")
    if used_recently:
        lines.append(f"Active: {len(used_recently)} parts used this week")
    if not quiet and not unknown_age:
        lines.append("Nothing quiet, everything's been touched.")
    return "\n".join(lines)
