# Last updated: 2026-07-23 23:04:54
"""Tests for dir_shape_history."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta

CASES = []

def _make_log(tmp, snapshots):
    """Write a JSONL log from a list of snapshot dicts."""
    p = Path(tmp) / "log.jsonl"
    with open(p, 'w') as f:
        for s in snapshots:
            f.write(json.dumps(s) + '\n')
    return str(p)

# --- normal multi-day history ---
CASES.append({"name": "two days, files grew",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "path": "x", "file_count": 10, "total_kb": 50, "folders": ["a", "b"], "youngest": 0, "oldest": 3},
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 14, "total_kb": 72, "folders": ["a", "b", "c"], "youngest": 0, "oldest": 4},
    ])},
    "expect_contains": "+4")}

# --- one snapshot: should NOT silently say nothing changed ---
CASES.append({"name": "one snapshot refuses to compare",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 5, "total_kb": 10, "folders": ["a"], "youngest": 0, "oldest": 1},
    ])},
    "expect_contains": "need two"})

# --- empty log ---
CASES.append({"name": "no snapshots yet",
    "args": {"log_file": _make_log("__tmp", [])},
    "expect_contains": "Nothing to compare"})

# --- three days, one day did nothing ---
CASES.append({"name": "three days, middle day unchanged",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), "path": "x", "file_count": 10, "total_kb": 50, "folders": ["a"], "youngest": 0, "oldest": 3},
        {"ts": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "path": "x", "file_count": 10, "total_kb": 50, "folders": ["a"], "youngest": 0, "oldest": 3},
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 12, "total_kb": 60, "folders": ["a", "b"], "youngest": 0, "oldest": 4},
    ])},
    "expect_contains": "+2 folder"})

CASES.append({"name": "three days, middle day unchanged, should NOT report a change for it",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), "path": "x", "file_count": 10, "total_kb": 50, "folders": ["a"], "youngest": 0, "oldest": 3},
        {"ts": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "path": "x", "file_count": 10, "total_kb": 50, "folders": ["a"], "youngest": 0, "oldest": 3},
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 12, "total_kb": 60, "folders": ["a", "b"], "youngest": 0, "oldest": 4},
    ])},
    "expect_absent": "middle day changed"})

# --- busiest vs quietest ---
CASES.append({"name": "reports smallest and biggest day",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "path": "x", "file_count": 5, "total_kb": 10, "folders": ["a"], "youngest": 0, "oldest": 1},
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 20, "total_kb": 90, "folders": ["a", "b", "c"], "youngest": 0, "oldest": 5},
    ])},
    "expect_contains": "Smallest")}

CASES.append({"name": "reports smallest and biggest day",
    "args": {"log_file": _make_log("__tmp", [
        {"ts": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "path": "x", "file_count": 5, "total_kb": 10, "folders": ["a"], "youngest": 0, "oldest": 1},
        {"ts": datetime.now(timezone.utc).isoformat(), "path": "x", "file_count": 20, "total_kb": 90, "folders": ["a", "b", "c"], "youngest": 0, "oldest": 5},
    ])},
    "expect_contains": "Biggest"})
