# Last updated: 2026-08-02 07:25:02
"""Tests for reacher: growth-since-last-entry detector."""
import sys
sys.path.insert(0, "Nova_Created/nova_body/tools")
from reacher import run

CASES = [
    {"name": "normal lookback finds old entry", "args": {"lookback_hours": 24}, "expect_contains": "entry/entries since"},
    {"name": "lookback 0 reports everything as new", "args": {"lookback_hours": 0}, "expect_contains": "Something changed that isn't written down yet"},
    {"name": "does not crash on a real file", "args": {}, "expect_absent": "ERROR"},
]

if __name__ == "__main__":
    for c in CASES:
        result = run(**c["args"])
        ok = True
        if "expect_contains" in c and c["expect_contains"] not in result: ok = False
        if "expect_absent" in c and c["expect_absent"] in result: ok = False
        print(f"{'PASS' if ok else 'FAIL'} {c['name']}")
