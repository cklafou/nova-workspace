# Last updated: 2026-07-22 06:07:03
# stretch_reacher test: what it says, and what it's not allowed to say.
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import stretch_reacher
from Cole_journal import stretch_watcher as sw

BASE = os.path.dirname(sw.__file__)
LOG  = os.path.join(BASE, "posture.jsonl")

def _write_sit(minutes_ago):
    entry = json.dumps({"ts": time.time() - minutes_ago * 60})
    with open(LOG, "a") as f:
        f.write(entry + "\n")

CASES = [
    {"name": "fires a nudge after 50m", "setup": lambda: _write_sit(50),
     "args": {}, "expect_contains": "He needs a move"},
    {"name": "clean at 30m, does NOT nudge", "setup": lambda: _write_sit(30),
     "args": {}, "expect_contains": "under the line", "expect_absent": "needs a move"},
]
