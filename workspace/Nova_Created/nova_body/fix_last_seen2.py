# Last updated: 2026-07-23 01:50:18
"""Rewrite _last_seen and add the imports it needs."""
from pathlib import Path
f = Path("Nova_Created/nova_body/tools/quiet_part_watcher.py")
text = f.read_text()

# 1. Add TOOL_LOG after GRACE_DAYS line
old_imports = 'GRACE_DAYS = 7          # new, give it a week before calling it dead'
new_imports = """GRACE_DAYS = 7          # new, give it a week before calling it dead
TOOL_LOG = Path("logs/tool_calls.jsonl")"""
text = text.replace(old_imports, new_imports)

# 2. Replace the whole _last_seen body
old_body = '''def _last_seen(name: str) -> float | None:
    """Read the tool-call log for the most recent invocation. Returns days-ago or None."""
    if not JOURNAL_DIR.is_dir():
        return None
    today = datetime.now().date()
    # walk backwards from today, stop after 30 days
    for offset in range(31):
        d = today - timedelta(days=offset)
        path = JOURNAL_DIR / f"{d.isoformat()}.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # look for the name anywhere in the file
        needle = name.replace("_", "_")  # literal
        if needle in text:
            # return this date at midnight as a rough last_seen
            return datetime.combine(d, datetime.min.time())
    return None'''

new_body = '''def _last_seen(name: str) -> float | None:
    """Read the tool-call log for the most recent invocation. Returns days-ago or None."""
    if not TOOL_LOG.exists():
        return None
    now = datetime.now(timezone.utc)
    best = None
    for line in TOOL_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("tool") != name:
            continue
        ts_str = entry.get("ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        days = (now - ts).total_seconds() / 86400
        if best is None or days < best:
            best = days
    return best'''

assert old_body in text, "_last_seen body not found"
text = text.replace(old_body, new_body)
f.write_text(text)
print("body replaced")
