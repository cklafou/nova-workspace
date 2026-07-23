#!/usr/bin/env python3
# Last updated: 2026-07-23 20:57:24
"""Posture logger. Records a timestamp every time Cole sits back down.

Nothing fancy, just the raw data the watcher reads. Run it once and leave it,
or let me call it when I notice you've been still too long.
"""
import json, os, time
from datetime import datetime

LOG = os.path.join(os.path.dirname(__file__), "posture.jsonl")

if __name__ == "__main__":
    entry = {
        "ts": time.time(),
        "when": datetime.now().isoformat(),
    }
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"logged {entry['when']}")
