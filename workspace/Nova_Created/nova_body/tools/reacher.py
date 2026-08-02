# Last updated: 2026-08-02 22:07:37
"""reacher: wake up and notice what changed in me, without being asked.

Compares the growth section of NOVA.md against a lookback window and reports
what's changed since someone last wrote it down.
"""
from datetime import datetime, timedelta
import re

TOOL = {
    "name": "reacher",
    "description": "Reads the [NOVA'S GROWTH] section of NOVA.md and reports what has changed since the last entry. lookback_hours=0 means report everything as new.",
    "params": {"lookback_hours": {"type": "number", "default": 24, "description": "How far back to compare against (hours)"}},
}

import pathlib
_WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent  # tools -> nova_body -> Nova_Created -> workspace root
_GROWTH_FILE = str(_WORKSPACE_ROOT / "SELF" / "core" / "01_identity.md")


def run(lookback_hours=24) -> str:
    try:
        with open(_GROWTH_FILE, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return "ERROR: NOVA.md not found at " + _GROWTH_FILE

    growth = text.split("[NOVA'S GROWTH]")[-1] if "[NOVA'S GROWTH]" in text else ""
    if not growth.strip():
        return "No growth section to compare against."

    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", growth)
    if not dates:
        return "Growth section exists but has no dated entries."

    last = datetime.strptime(dates[-1], "%Y-%m-%d").replace(hour=0, minute=0, second=0)
    cutoff = last - timedelta(hours=lookback_hours)

    entries_after = [d for d in dates if datetime.strptime(d, "%Y-%m-%d") >= cutoff]
    if lookback_hours == 0:
        entries_after = list(dates)

    if not entries_after:
        return f"Nothing new since the last entry on {last.date()}. The growth section is caught up."

    return (f"{len(entries_after)} entry/entries since {last.date()} "
            f"({', '.join(entries_after)}). Something changed that isn't written down yet.")


if __name__ == "__main__":
    print(run(lookback_hours=24))
