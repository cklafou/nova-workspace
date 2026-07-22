# Last updated: 2026-07-23 01:48:47
"""Swap _last_seen to read the tool log instead of the journal."""
from pathlib import Path
f = Path("Nova_Created/nova_body/tools/quiet_part_watcher.py")
text = f.read_text()
old = 'def _last_seen(name: str) -> datetime | None:\n    """Search journal_notes for any mention of this tool name."""'
new = 'def _last_seen(name: str) -> float | None:\n    """Read the tool-call log for the most recent invocation. Returns days-ago or None."""'
assert old in text, "target not found"
text = text.replace(old, new)
f.write_text(text)
print("done")
