# @nova: Persistent audit-review queue — records file-change events (rename/delete/new) for review by audit_scripts/restructure.
# Last updated: 2026-07-08 19:59:44
"""
general_tools/audit_queue.py — Persistent Audit Review Queue
=============================================================
Shared module used by watcher.py, restructure.py, and audit_scripts.py.

Stores file-change events (renames, deletes, new files) detected on each
git push. Items stay pending until resolved by restructure.py or manually
dismissed. audit_scripts.py surfaces pending items as HIGH REVIEW flags.

Queue file: workspace/memory/audit_queue.json

Event types:
  rename          — git detected a file rename (old_path → new_path)
  possible_rename — git missed it; _similarity() found a likely match
  delete          — file deleted, no similar replacement found
  new             — new file appeared, no similar predecessor found

Status values:
  pending   — not yet reviewed or resolved
  resolved  — fixed by restructure.py --rename (or equivalent action)
  dismissed — reviewed and intentionally left alone (e.g. file truly deleted)

Usage:
  from audit_queue import add_item, resolve, dismiss, pending_items, load, save

  # Add a rename event detected by watcher:
  add_item(event_type="rename", old_path="nova_cortex/brain.py",
           new_path="nova_cortex/prefrontal_cortex.py", confidence=0.97,
           commit="a1b2c3d4")

  # Resolve after restructure.py fixes references:
  resolve(item_id="abc12345", resolved_by="restructure.py --rename")

  # Get all items still waiting for review:
  for item in pending_items():
      print(item["event_type"], item["old_path"], item["confidence"])
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
QUEUE_PATH    = WORKSPACE_DIR / "memory" / "audit_queue.json"

# Max items to retain (pending + resolved + dismissed combined).
# Oldest resolved/dismissed items are pruned first when limit is hit.
MAX_QUEUE_SIZE = 500


# ── Schema helpers ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _empty_queue() -> dict:
    return {
        "version":    1,
        "updated_at": _now(),
        "items":      [],
    }


# ── Core I/O ──────────────────────────────────────────────────────────────────

def load() -> dict:
    """Load the queue from disk. Returns empty queue if file is missing or corrupt."""
    if QUEUE_PATH.exists():
        try:
            return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _empty_queue()


def save(data: dict) -> None:
    """Atomically write the queue to disk."""
    data["updated_at"] = _now()
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(QUEUE_PATH)


def _prune(data: dict) -> None:
    """Remove oldest resolved/dismissed items if queue exceeds MAX_QUEUE_SIZE."""
    items = data["items"]
    if len(items) <= MAX_QUEUE_SIZE:
        return
    closed = [i for i in items if i["status"] != "pending"]
    closed.sort(key=lambda i: i.get("resolved_at") or i.get("detected_at") or "")
    to_remove = len(items) - MAX_QUEUE_SIZE
    remove_ids = {i["id"] for i in closed[:to_remove]}
    data["items"] = [i for i in items if i["id"] not in remove_ids]


# ── Public API ─────────────────────────────────────────────────────────────────

def add_item(
    event_type:  str,
    commit:      str,
    confidence:  float,
    old_path:    Optional[str] = None,
    new_path:    Optional[str] = None,
    notes:       Optional[str] = None,
) -> dict:
    """
    Add a new event to the queue.

    event_type  : "rename" | "possible_rename" | "delete" | "new"
    commit      : short git commit hash (8 chars is fine)
    confidence  : 0.0–1.0  (git similarity or _similarity() score)
    old_path    : workspace-relative path of the original file (if applicable)
    new_path    : workspace-relative path of the new/renamed file (if applicable)
    notes       : optional free-text annotation

    Returns the new item dict.
    """
    item = {
        "id":          uuid.uuid4().hex[:8],
        "status":      "pending",
        "event_type":  event_type,
        "detected_at": _now(),
        "commit":      commit,
        "old_path":    old_path,
        "new_path":    new_path,
        "confidence":  round(confidence, 4),
        "resolved_by": None,
        "resolved_at": None,
        "notes":       notes,
    }
    data = load()
    data["items"].append(item)
    _prune(data)
    save(data)
    return item


def resolve(item_id: str, resolved_by: str = "manual") -> bool:
    """
    Mark a queue item as resolved.
    resolved_by: human-readable description, e.g. "restructure.py --rename nova_cortex.brain=..."
    Returns True if the item was found and updated.
    """
    data = load()
    for item in data["items"]:
        if item["id"] == item_id:
            item["status"]      = "resolved"
            item["resolved_by"] = resolved_by
            item["resolved_at"] = _now()
            save(data)
            return True
    return False


def dismiss(item_id: str, notes: str = "") -> bool:
    """
    Mark a queue item as dismissed (intentionally no action taken).
    Returns True if the item was found and updated.
    """
    data = load()
    for item in data["items"]:
        if item["id"] == item_id:
            item["status"]      = "dismissed"
            item["resolved_at"] = _now()
            if notes:
                item["notes"] = notes
            save(data)
            return True
    return False


def resolve_by_paths(
    old_path: Optional[str],
    new_path: Optional[str],
    resolved_by: str = "restructure.py",
) -> int:
    """
    Resolve all pending items whose old_path and new_path match.
    Useful for restructure.py to auto-resolve after applying a rename.
    Returns the number of items resolved.
    """
    data    = load()
    count   = 0
    changed = False
    for item in data["items"]:
        if item["status"] != "pending":
            continue
        path_match = (
            (old_path is None or item.get("old_path") == old_path)
            and (new_path is None or item.get("new_path") == new_path)
        )
        if path_match:
            item["status"]      = "resolved"
            item["resolved_by"] = resolved_by
            item["resolved_at"] = _now()
            count  += 1
            changed = True
    if changed:
        save(data)
    return count


def pending_items() -> list[dict]:
    """Return all items with status == 'pending', newest first."""
    data  = load()
    items = [i for i in data["items"] if i["status"] == "pending"]
    items.sort(key=lambda i: i.get("detected_at") or "", reverse=True)
    return items


def all_items() -> list[dict]:
    """Return all items regardless of status, newest first."""
    data = load()
    return sorted(data["items"], key=lambda i: i.get("detected_at") or "", reverse=True)


def get_item(item_id: str) -> Optional[dict]:
    """Return a single item by ID, or None if not found."""
    data = load()
    for item in data["items"]:
        if item["id"] == item_id:
            return item
    return None


# ── CLI (for manual inspection / dismissal) ────────────────────────────────────

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if not args or args[0] == "--list":
        items = pending_items()
        if not items:
            print("[audit_queue] No pending items.")
        else:
            print(f"[audit_queue] {len(items)} pending item(s):\n")
            for it in items:
                conf = f"{it['confidence']:.0%}"
                old  = it.get("old_path") or "—"
                new  = it.get("new_path")  or "—"
                print(f"  [{it['id']}] {it['event_type']:16s} {conf}  {old} → {new}")
                if it.get("notes"):
                    print(f"              note: {it['notes']}")

    elif args[0] == "--all":
        items = all_items()
        print(f"[audit_queue] {len(items)} total item(s):\n")
        for it in items:
            conf = f"{it['confidence']:.0%}"
            old  = it.get("old_path") or "—"
            new  = it.get("new_path")  or "—"
            print(f"  [{it['id']}] {it['status']:10s} {it['event_type']:16s} {conf}  {old} → {new}")

    elif args[0] == "--resolve" and len(args) >= 2:
        item_id = args[1]
        by      = args[2] if len(args) >= 3 else "manual"
        if resolve(item_id, resolved_by=by):
            print(f"[audit_queue] Resolved: {item_id}")
        else:
            print(f"[audit_queue] Item not found: {item_id}")

    elif args[0] == "--dismiss" and len(args) >= 2:
        item_id = args[1]
        note    = args[2] if len(args) >= 3 else ""
        if dismiss(item_id, notes=note):
            print(f"[audit_queue] Dismissed: {item_id}")
        else:
            print(f"[audit_queue] Item not found: {item_id}")

    else:
        print("Usage:")
        print("  python audit_queue.py --list              # pending items")
        print("  python audit_queue.py --all               # all items")
        print("  python audit_queue.py --resolve <id>      # mark resolved")
        print("  python audit_queue.py --dismiss <id> [note]  # mark dismissed")
