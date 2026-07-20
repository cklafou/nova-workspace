# @nova: Persistent audit-review queue — records file-change events (rename/delete/new) for review by audit_scripts/restructure.
# Last updated: 2026-07-20 14:10:19
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
import re
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


# A pending item older than this is not a review backlog, it is litter. The rename it
# describes happened weeks ago; nobody is going to act on it now.
STALE_PENDING_DAYS = 14


def _prune(data: dict) -> None:
    """Enforce MAX_QUEUE_SIZE — for real this time.

    ── WHY THIS WAS REWRITTEN (2026-07-20) ─────────────────────────────────────────────
    The old version only ever removed items whose status was NOT pending:

        closed = [i for i in items if i["status"] != "pending"]
        remove_ids = {i["id"] for i in closed[:to_remove]}

    Which means the cap held only while something was resolving items. Nothing ever did —
    `resolve()` is called from exactly one place (restructure.py --rename) and that script
    has never been run automatically. So `closed` was always empty, `remove_ids` was always
    empty, and MAX_QUEUE_SIZE = 500 quietly capped nothing at all. The queue reached 6,563
    items and 2.6 MB before anyone looked.

    A bounded buffer whose bound depends on a consumer that may not exist is not bounded.
    So now: closed items go first (they're worthless), then stale pending, then oldest
    pending — and the cap holds no matter what else in the system is or isn't working.

    Dropping pending items IS lossy, which is why it says so out loud rather than doing it
    quietly. Silence about discarded data is how you end up trusting a queue that has been
    throwing things away for a month.
    """
    items = data["items"]

    # 1. Age out stale pending items regardless of size.
    if STALE_PENDING_DAYS:
        try:
            cutoff = datetime.now(timezone.utc).timestamp() - STALE_PENDING_DAYS * 86400
            fresh = []
            aged = 0
            for i in items:
                if i.get("status") == "pending":
                    try:
                        ts = datetime.fromisoformat(i.get("detected_at", "")).timestamp()
                        if ts < cutoff:
                            aged += 1
                            continue
                    except Exception:
                        pass
                fresh.append(i)
            if aged:
                print(f"[audit_queue] aged out {aged} pending item(s) older than "
                      f"{STALE_PENDING_DAYS} days")
            items = fresh
        except Exception:
            pass

    if len(items) <= MAX_QUEUE_SIZE:
        data["items"] = items
        return

    # 2. Closed items first — they have already served their purpose.
    closed = [i for i in items if i.get("status") != "pending"]
    closed.sort(key=lambda i: i.get("resolved_at") or i.get("detected_at") or "")
    to_remove = len(items) - MAX_QUEUE_SIZE
    remove_ids = {i["id"] for i in closed[:to_remove]}

    # 3. Still over? Then oldest PENDING go too. This is the line the old code was missing,
    #    and its absence is the entire bug.
    still = to_remove - len(remove_ids)
    if still > 0:
        pend = [i for i in items if i["id"] not in remove_ids and i.get("status") == "pending"]
        pend.sort(key=lambda i: i.get("detected_at") or "")
        dropped = pend[:still]
        remove_ids |= {i["id"] for i in dropped}
        print(f"[audit_queue] queue over {MAX_QUEUE_SIZE}; dropping {len(dropped)} oldest "
              f"PENDING item(s) — unreviewed. Oldest dropped: "
              f"{dropped[0].get('detected_at','?') if dropped else '-'}")

    data["items"] = [i for i in items if i["id"] not in remove_ids]


# ═══════════════════════════════════════════════════════════════════════════════════════════
# RECONCILE — the queue closes itself when the work is actually done
#
# ── WHY (2026-07-20, Cole: "clear her queue completely and look into WHY that queue exists
#    and what is needed to be done to fix this problem for the future") ──────────────────────
#
# Clearing it was the easy half. The queue refills because of a category error in what it
# records. It logs FILE OPERATIONS — every rename, every delete, every new file — and marks
# each one `pending` until a human personally signs it off. Nothing else closes an item;
# `resolve()` has exactly one caller (restructure.py --rename), which has never run
# automatically. So the queue only ever grows, and the number in the audit report measures
# how much work has happened, not how much is left.
#
# It hit 6,563 items that way. Today it refilled to 48 within hours of being emptied — and
# every one of those 48 was a file operation Cole had explicitly ordered that morning. The
# audit was asking him to confirm that the trash he told me to take out was meant to go out.
#
# But look at what the queue is FOR: catching the moment a file moves and leaves a stale
# reference pointing at where it used to be. That is a real hazard and worth a real alarm.
# The thing is, it is a hazard about REFERENCES, not about operations:
#
#     a rename nothing points at   -> already handled, close it
#     a rename something points at -> genuinely broken, RAISE IT
#     a brand-new file             -> cannot dangle anything, never actionable
#
# So stop asking "did a human bless this move?" and ask "is anything still pointing at the old
# path?" That question has an answer the machine can compute, it needs no human in the loop,
# and it goes false on its own the moment the references get fixed. A queue whose items expire
# when the underlying problem is solved stays honest by construction. One whose items expire
# only when a person clicks something becomes 6,563 rows of noise, and then it doesn't matter
# how good the alarm was, because nobody is reading it.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# Where a stale reference could actually hurt. Scanning the whole tree (models/, LanceDB,
# node_modules) would take minutes and find nothing.
_REF_SCAN_DIRS  = ("general_tools", "nova_body", "Orient", "SELF", "Tasking", "Nova_Created")
_REF_SCAN_EXTS  = (".py", ".md", ".json", ".ps1", ".cmd", ".bat", ".txt", ".html", ".js")
_REF_SCAN_SKIP  = ("__pycache__", ".git", "node_modules", "_admin/Trash", "_archive",
                   "nova_memory_db", "prompt_cache", "logs", "models", "llama")


# A module stem this common is not evidence of anything. "nova" appears in nearly every file
# in a project called Nova.
_STEM_STOPWORDS = {"nova", "main", "utils", "util", "test", "tests", "core", "app", "run",
                   "server", "client", "config", "setup", "index", "base", "common", "tools"}


def _stem_pattern(stem: str):
    """Match a module stem only where it is being USED as a module, never as prose.

    ── WHY NOT A PLAIN SUBSTRING (2026-07-20) ────────────────────────────────────────────────
    First version searched for the bare stem anywhere in the text. `general_tools/nova_chat/
    clients/nova.py` reduces to the stem "nova", and the reconciler dutifully reported that it
    was still referenced by — among everything else — the file doing the reporting. In a
    project named Nova, "nova" is not a signal.

    Worse than the noise: a reconciler that reports everything as dangling never closes
    anything, which lands it in precisely the state it was written to fix. The check has to be
    able to say NO, or it isn't a check.

    So require import-shaped context. A real broken reference looks like `import x`,
    `from x import`, `x.attr`, or a quoted "x" in a path/registry. Prose saying "we moved x
    today" does not, and prose is most of what these files contain.
    """
    s = re.escape(stem)
    return re.compile(
        rf"(?:^|\n)\s*(?:from|import)\s+{s}\b"      # import x / from x import ...
        rf"|\bimport\s+{s}\b"                        # inline import
        rf"|\b{s}\s*\."                              # x.attr  (module attribute access)
        rf"|['\"][^'\"\n]*\b{s}(?:\.py)?['\"]"       # "x" / "pkg/x.py" in a path or registry
    )


def _still_referenced(old_path: str, root: Path) -> Optional[str]:
    """Return the first file that still mentions `old_path`, or None.

    Matches on the full path AND — for .py files — on the module stem in import position,
    because a broken import reads `from nova_chat import server`, never
    `general_tools/nova_chat/server.py`. Checking only the full path would miss every import
    breakage, which is the exact failure this queue exists to catch.
    """
    if not old_path:
        return None
    path_needle = old_path.replace("\\", "/")
    p = Path(old_path)
    stem_re = None
    if (p.suffix == ".py" and p.stem not in ("__init__", "__main__")
            and p.stem.lower() not in _STEM_STOPWORDS and len(p.stem) >= 5):
        stem_re = _stem_pattern(p.stem)
    self_names = {QUEUE_PATH.name, Path(__file__).name}

    for d in _REF_SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in _REF_SCAN_EXTS:
                continue
            rel = str(f.relative_to(root)).replace("\\", "/")
            if any(s in rel for s in _REF_SCAN_SKIP) or f.name in self_names:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if path_needle in text:
                return rel
            if stem_re is not None and stem_re.search(text):
                return rel
    return None


def reconcile(root: Optional[Path] = None, verbose: bool = True) -> dict:
    """Close every pending item that no longer describes a live problem.

    Returns {"closed_new": n, "closed_clean": n, "still_broken": [...]}.
    Safe to run repeatedly; it only ever moves items pending -> resolved.
    """
    root = Path(root) if root else WORKSPACE_DIR
    data = load()
    out = {"closed_new": 0, "closed_clean": 0, "still_broken": []}

    for item in data["items"]:
        if item.get("status") != "pending":
            continue

        # A new file cannot leave a dangling reference. There is nothing to review, and
        # 19 of today's 48 were exactly this.
        if item.get("event_type") == "new":
            item.update(status="resolved", resolved_by="reconcile: new file, nothing can dangle",
                        resolved_at=_now())
            out["closed_new"] += 1
            continue

        old = item.get("old_path")
        if not old:
            item.update(status="resolved", resolved_by="reconcile: no old path to dangle",
                        resolved_at=_now())
            out["closed_clean"] += 1
            continue

        hit = _still_referenced(old, root)
        if hit is None:
            item.update(status="resolved",
                        resolved_by="reconcile: no remaining references to the old path",
                        resolved_at=_now())
            out["closed_clean"] += 1
        else:
            # THIS is what the queue was built to find. Keep it pending and say where.
            item["notes"] = (f"STILL REFERENCED by {hit} — fix that reference, "
                             f"then this closes itself.")
            out["still_broken"].append({"id": item["id"], "old_path": old, "referenced_by": hit})

    save(data)
    if verbose:
        n = out["closed_new"] + out["closed_clean"]
        print(f"[audit_queue] reconcile: closed {n} item(s) "
              f"({out['closed_new']} new-file, {out['closed_clean']} no-longer-referenced); "
              f"{len(out['still_broken'])} genuinely dangling")
        for b in out["still_broken"]:
            print(f"    DANGLING  {b['old_path']}  still referenced by  {b['referenced_by']}")
    return out


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
