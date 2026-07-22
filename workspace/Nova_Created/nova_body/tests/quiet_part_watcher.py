# Last updated: 2026-07-23 01:07:53
"""Tests for quiet_part_watcher."""
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import json, tempfile, time
from nova_senses.quiet_part_watcher import find_last_seen, run

CASES = [
    {
        "name": "finds a name in a log",
        "args": {},
        "run": lambda: _log_then_find("reach_watcher"),
        "expect_contains": "0",  # today
    },
    {
        "name": "returns -1 for something never seen",
        "args": {},
        "run": lambda: find_last_seen("totally_made_up_tool_xyz"),
        "expect_equals": -1,
    },
    {
        "name": "run() returns a real report, not empty",
        "args": {},
        "run": lambda: run(),
        "check": lambda r: [] if len(r) > 20 else ["report is suspiciously short"],
    },
]


def _log_then_find(name):
    """Write a one-line log for *name*, then read it back."""
    tmp = Path(tempfile.mkdtemp()) / "logs"
    tmp.mkdir(parents=True)
    (tmp / "tool_test.jsonl").write_text(
        json.dumps({"tool": name, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n"
    )
    return find_last_seen(name, logs_dir=tmp)


def check_all():
    failures = []
    for c in CASES:
        got = c["run"]()
        if "expect_equals" in c and got != c["expect_equals"]:
            failures.append(f"{c['name']}: expected {c['expect_equals']}, got {got}")
        elif "expect_contains" in c and c["expect_contains"] not in str(got):
            failures.append(f"{c['name']}: wanted '{c['expect_contains']}' in {got}")
        elif "check" in c:
            failures.extend(c["check"](got))
    return failures


if __name__ == "__main__":
    fails = check_all()
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
    else:
        print(f"All {len(CASES)} green.")
