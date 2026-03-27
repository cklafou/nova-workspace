"""
nova_core/nova_status.py -- Nova's live status writer
======================================================
Nova calls this at the end of every agent run to write nova_status.json.
server.py polls this file every 30s and silently injects it into AI context.

Usage (from Nova's exec or agent code):
    exec: python -c "
    import sys
    sys.path.insert(0, 'tools')
    from nova_core.nova_status import update
    update(pulse='Idle', summary='Heartbeat check complete -- nothing to do')
    "

    # Or with a task:
    from nova_core.nova_status import update, set_task, clear_task, add_error
    update(pulse='Analyzing ThinkOrSwim layout', active_task='tos_automation_v1')
    set_task('tos_automation_v1', status='running', description='Click login button')
    clear_task()           # when task completes
    add_error('vision', 'Element not found: Trade Button (attempt 3/3)')
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Always write to workspace root -- server.py knows where to find it
WORKSPACE_DIR = Path(__file__).parent.parent.parent
STATUS_FILE   = WORKSPACE_DIR / "nova_status.json"
TASKS_FILE    = WORKSPACE_DIR / "tasks" / "active.json"


# ── Schema helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    """ISO timestamp with UTC offset."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read() -> dict:
    """Read current nova_status.json, return empty schema if missing or corrupt."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _empty_schema()


def _write(data: dict):
    """Atomically write nova_status.json."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATUS_FILE)


def _empty_schema() -> dict:
    return {
        "version": 1,
        "updated_at": _now(),
        "pulse": "Idle",
        "active_task": None,
        "last_run": {
            "started_at": None,
            "ended_at":   None,
            "duration_s": None,
            "status":     "unknown",
            "summary":    "No run recorded yet"
        },
        "errors": [],       # last 10 errors, newest first
        "gateway": {
            "running": None,
            "last_error": None,
            "last_checked": None
        }
    }


# ── Public API ────────────────────────────────────────────────────────────────

def update(
    pulse:       str            = "Idle",
    summary:     str            = "",
    active_task: Optional[str]  = None,
    started_at:  Optional[str]  = None,
    run_status:  str            = "ok",
    duration_s:  Optional[int]  = None,
):
    """
    Main call -- update Nova's status at end of a run.

    pulse       : One-line human-readable state ("Idle", "Checking heartbeat", etc.)
    summary     : What happened this run
    active_task : Task ID if mid-task (None = idle)
    started_at  : ISO timestamp when run started (for duration calc)
    run_status  : "ok" | "error" | "partial"
    duration_s  : Override duration (if you tracked it yourself)
    """
    data = _read()
    now  = _now()

    # Calculate duration if started_at provided
    if started_at and duration_s is None:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(started_at)
            end   = datetime.fromisoformat(now)
            duration_s = int((end - start).total_seconds())
        except Exception:
            duration_s = None

    data["updated_at"]   = now
    data["pulse"]        = pulse
    data["active_task"]  = active_task

    data["last_run"] = {
        "started_at": started_at or now,
        "ended_at":   now,
        "duration_s": duration_s,
        "status":     run_status,
        "summary":    summary or pulse
    }

    _write(data)
    print(f"[nova_status] updated: {pulse}")


def set_task(task_id: str, status: str = "running", description: str = ""):
    """
    Update tasks/active.json with a running task.
    Also sets active_task field in nova_status.json.
    """
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    task_data = {
        "task_id":     task_id,
        "status":      status,           # running | paused | complete | failed
        "description": description,
        "started_at":  _now(),
        "updated_at":  _now(),
        "paused_at":   None,
        "note":        None
    }
    # Read existing tasks file if present, update or insert
    existing = {}
    if TASKS_FILE.exists():
        try:
            existing = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing[task_id] = task_data
    TASKS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also update nova_status.json active_task field
    data = _read()
    data["active_task"] = task_id
    data["updated_at"]  = _now()
    _write(data)
    print(f"[nova_status] task set: {task_id} ({status})")


def clear_task(task_id: Optional[str] = None, final_status: str = "complete"):
    """
    Mark a task complete in tasks/active.json and clear active_task in nova_status.json.
    If task_id is None, clears whatever is currently active.
    """
    data = _read()
    tid  = task_id or data.get("active_task")

    if tid and TASKS_FILE.exists():
        try:
            tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            if tid in tasks:
                tasks[tid]["status"]     = final_status
                tasks[tid]["updated_at"] = _now()
            TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    data["active_task"] = None
    data["updated_at"]  = _now()
    _write(data)
    print(f"[nova_status] task cleared: {tid or 'none'} -> {final_status}")


def pause_task(task_id: Optional[str] = None, note: str = ""):
    """Mark active task as paused (PAUSE directive handler)."""
    data = _read()
    tid  = task_id or data.get("active_task")
    if not tid:
        print("[nova_status] pause_task: no active task to pause")
        return

    if TASKS_FILE.exists():
        try:
            tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            if tid in tasks:
                tasks[tid]["status"]    = "paused"
                tasks[tid]["paused_at"] = _now()
                tasks[tid]["note"]      = note
                tasks[tid]["updated_at"] = _now()
            TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    data["pulse"]       = f"Paused: {tid}" + (f" -- {note}" if note else "")
    data["updated_at"]  = _now()
    _write(data)
    print(f"[nova_status] paused: {tid}")


def resume_task(task_id: Optional[str] = None):
    """Resume a paused task."""
    data = _read()
    tid  = task_id or data.get("active_task")
    if not tid:
        print("[nova_status] resume_task: no task to resume")
        return

    if TASKS_FILE.exists():
        try:
            tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            if tid in tasks:
                tasks[tid]["status"]     = "running"
                tasks[tid]["paused_at"]  = None
                tasks[tid]["updated_at"] = _now()
            TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    data["active_task"] = tid
    data["pulse"]       = f"Resumed: {tid}"
    data["updated_at"]  = _now()
    _write(data)
    print(f"[nova_status] resumed: {tid}")


def add_error(category: str, message: str, limit: int = 10):
    """
    Append an error to the errors list (newest first, capped at `limit`).
    category: "vision" | "action" | "gateway" | "import" | "bridge" | etc.
    """
    data   = _read()
    errors = data.get("errors", [])
    errors.insert(0, {
        "ts":       _now(),
        "category": category,
        "message":  message[:300]   # cap single error length
    })
    data["errors"]     = errors[:limit]
    data["updated_at"] = _now()
    _write(data)
    print(f"[nova_status] error logged: [{category}] {message[:80]}")


def update_gateway(running: bool, last_error: Optional[str] = None):
    """Update gateway health info (called by server.py's error detector)."""
    data = _read()
    data["gateway"] = {
        "running":      running,
        "last_error":   last_error,
        "last_checked": _now()
    }
    data["updated_at"] = _now()
    _write(data)


def read() -> dict:
    """Return current status as a dict (for server.py polling)."""
    return _read()


def read_summary() -> str:
    """Return a compact one-paragraph status string for silent AI injection."""
    data = _read()
    pulse  = data.get("pulse", "Unknown")
    task   = data.get("active_task")
    run    = data.get("last_run", {})
    errors = data.get("errors", [])
    gw     = data.get("gateway", {})

    lines = [f"Nova status as of {data.get('updated_at', 'unknown')}:"]
    lines.append(f"  Pulse: {pulse}")
    if task:
        lines.append(f"  Active task: {task}")
    if run.get("summary"):
        lines.append(f"  Last run: {run['summary']} ({run.get('status', '?')}, {run.get('duration_s', '?')}s)")
    if gw.get("running") is not None:
        gw_state = "running" if gw["running"] else "OFFLINE"
        lines.append(f"  Gateway: {gw_state}")
        if gw.get("last_error"):
            lines.append(f"  Gateway error: {gw['last_error']}")
    if errors:
        lines.append(f"  Recent errors ({len(errors)}):")
        for e in errors[:3]:
            lines.append(f"    [{e['category']}] {e['message'][:100]}")
    return "\n".join(lines)


# ── CLI usage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick test / manual write
    # Usage: python tools/nova_core/nova_status.py "pulse text" "summary text"
    pulse   = sys.argv[1] if len(sys.argv) > 1 else "Idle"
    summary = sys.argv[2] if len(sys.argv) > 2 else ""
    update(pulse=pulse, summary=summary)
    print(read_summary())
