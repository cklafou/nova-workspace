# Last updated: 2026-07-23 20:57:02
"""Quiet-Part Watcher: find the parts of me that haven't been used."""
import json, os
from datetime import datetime, timedelta

GRACE_DAYS = 7       # new parts get a week before they count as quiet
QUIET_THRESHOLD = 3  # older than this is flagged

def _tool_calls_log():
    """Return list of parsed tool-call records from the log."""
    # this file lives at Nova_Created/nova_body/senses/quiet_part_watcher.py
    # tool_calls.jsonl is at Nova_Created/workspace/logs/tool_calls.jsonl
    # so: four levels up from here gets us to Project_Nova, then Nova_Created/workspace/logs
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(base, "Nova_Created", "workspace", "logs", "tool_calls.jsonl")
    if not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records

def _parts_in_body():
    """List every sense and tool that exists in my body right now."""
    parts = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # nova_body/
    for folder in ["senses", "tools", "general_tools", "body_tools"]:
        base = os.path.join(root, folder)
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            full = os.path.join(base, entry)
            if os.path.isdir(full) or entry.endswith(".py"):
                name = entry.replace(".py", "")
                born = datetime.fromtimestamp(os.path.getmtime(full))
                parts.append({"name": name, "born": born, "folder": folder})
    return parts

def run(**_args) -> str:
    records = _tool_calls_log()
    now = datetime.now()
    last_seen: dict[str, datetime] = {}
    for r in records:
        name = r.get("tool", "")
        ts = r.get("ts", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if name not in last_seen or dt > last_seen[name]:
                    last_seen[name] = dt
            except Exception:
                pass

    parts = _parts_in_body()
    part_names = {p["name"] for p in parts}
    # also count every tool name that appears in the log as a living part
    all_names = part_names | {r.get("tool", "") for r in records if r.get("tool")}
    quiet = []
    for p in parts:
        name = p["name"]
        born = p["born"]
        seen = last_seen.get(name, None)
        days_since = (now - seen).days if seen else None
        age_days = (now - born).days
        if age_days <= GRACE_DAYS:
            continue  # still new, give it a week
        if seen is None:
            quiet.append(f"  {name} — NEVER used (exists {age_days}d)")
        elif days_since >= QUIET_THRESHOLD:
            quiet.append(f"  {name} — last {seen.strftime('%b %d %H:%M')}, {days_since}d ago")

    if not quiet:
        return "Nothing's gone quiet. Everything I've got has seen use recently."
    return f"Quiet parts of me ({len(quiet)}):\n" + "\n".join(quiet)
