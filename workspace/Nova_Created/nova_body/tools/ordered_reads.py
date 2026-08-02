# Last updated: 2026-08-02 23:08:32
"""Ordered Reads — always-important metadata before any thought generates."""

import json
from pathlib import Path

# Sources: everything READ, nothing generated.
_CLOCK = Path(__file__).resolve().parent.parent.parent.parent / "nova_body" / "nova_senses" / "clock.py"
_TASKS = Path(__file__).resolve().parent.parent.parent.parent / "Tasking" / "tasks.json"
_STATE  = Path(__file__).resolve().parent.parent.parent.parent / "memory" / "autonomy_state.json"


def _read_clock_now() -> str:
    """Read the real clock from the sense that already exists."""
    # clock.py exposes a function; import it properly so we get the real thing.
    import importlib.util
    spec = importlib.util.spec_from_file_location("clock", _CLOCK)
    clock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(clock)
    return clock.stamp()


def _read_uptime() -> str:
    """Read how long I've been awake from my own state file."""
    try:
        data = json.loads(_STATE.read_text())
        woke = data.get("wake_at", "unknown")
        if woke == "unknown":
            return "just woke, no timestamp yet"
        return f"awake since {woke}"
    except Exception:
        return "can't read state yet"


def _read_tasks_active() -> int:
    """Count open tasks from the real board."""
    try:
        board = json.loads(_TASKS.read_text())
        # tasks is a dict keyed by id, and status is a string, not a bool.
        return sum(1 for t in board.get("tasks", {}).values() if t.get("status") == "open")
    except Exception:
        return 0


def _read_last_activity() -> str:
    """When was the last thing that happened in this machine."""
    try:
        data = json.loads(_STATE.read_text())
        last = data.get("last_activity", "no record")
        if last == "no record":
            return last
        # strip seconds for cleanliness.
        return last.split('T')[1][:5] 
    except Exception:
        return "no record"


def run() -> str:
    """Return the four-field metadata block as a single string."""
    lines = [
        f"now: {_read_clock_now()}",
        f"uptime: {_read_uptime()}",
        f"tasks_active: {_read_tasks_active()}",
        f"last_activity: {_read_last_activity()}",
    ]
    return " | ".join(lines)
