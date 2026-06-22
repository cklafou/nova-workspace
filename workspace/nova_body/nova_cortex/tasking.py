# Last updated: 2026-06-22 21:58:30
# @nova: Executive task board — my prefrontal work board. Every task I choose to track,
#        by stable id (t1, t2…), with status/progress/result. My free-agency substrate:
#        create, switch, wait, abandon, complete, reprioritize — no enforced order.
#        Source of truth: workspace/Tasking/tasks.json. Executive function, not memory.
"""
nova_cortex/tasking.py — Nova's executive task board
====================================================
Id-keyed single source of truth (Tasking/tasks.json). A task is identified by a stable
id assigned at creation; the title is a free label Nova may reword at will without
breaking identity (this kills the title-drift / key-mismatch bug class). No enforced
ordering — priority is HER weighting. Completed and abandoned tasks are KEPT
(remembered) so she never recreates or redoes them.

Pure file + logic — no chat/server dependency, so it survives the pluck-test and can
be used by any host.
"""

import os
import json
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parent.parent.parent)
_STORE = WORKSPACE_ROOT / "Tasking" / "tasks.json"

OPEN, WAITING, DONE, ABANDONED = "open", "waiting", "done", "abandoned"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> dict:
    try:
        if _STORE.exists():
            d = json.loads(_STORE.read_text(encoding="utf-8"))
            d.setdefault("seq", 0)
            d.setdefault("tasks", {})
            return d
    except Exception:
        pass
    return {"seq": 0, "tasks": {}}


def _save(store: dict) -> None:
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _STORE)
    except Exception as e:
        print(f"[tasking] save failed: {e}")


def all_tasks() -> dict:
    return _load()["tasks"]


def get(tid: str):
    return _load()["tasks"].get(tid)


def _update(tid: str, **fields) -> bool:
    store = _load()
    t = store["tasks"].get(tid)
    if not t:
        return False
    for k, v in fields.items():
        if v is not None:
            t[k] = v
    t["updated"] = _now()
    _save(store)
    return True


def create(title: str, notes: str = "", priority: int = 3, parent: str = None) -> str:
    store = _load()
    store["seq"] += 1
    tid = f"t{store['seq']}"
    try:
        pr = int(priority)
    except Exception:
        pr = 3
    # Keep a parent pointer only if it refers to a real, still-OPEN task — never nest a
    # subtask under a done/abandoned task (that buries live work under finished work, the
    # exact mis-parent bug we hit when she used an old done id as a stand-in).
    par = None
    if parent and parent in store["tasks"]:
        if store["tasks"][parent].get("status") not in (DONE, ABANDONED):
            par = parent
    store["tasks"][tid] = {
        "id": tid, "title": (title or "").strip() or f"(untitled {tid})",
        "notes": notes or "", "priority": pr, "status": OPEN, "parent": par,
        "progress": [], "created": _now(), "updated": _now(),
    }
    _save(store)
    return tid


def progress(tid: str, note: str) -> bool:
    store = _load()
    t = store["tasks"].get(tid)
    if not t:
        return False
    if note:
        t.setdefault("progress", []).append({"ts": _now(), "note": note})
        t["progress"] = t["progress"][-20:]
    t["updated"] = _now()
    _save(store)
    return True


def complete(tid: str, result: str = "") -> bool:
    return _update(tid, status=DONE, result=result or "")


def wait(tid: str, waiting_on: str = "") -> bool:
    return _update(tid, status=WAITING, waiting_on=waiting_on or "(unspecified)")


def abandon(tid: str, reason: str = "") -> bool:
    return _update(tid, status=ABANDONED, abandon_reason=reason or "(no reason given)")


def reopen(tid: str) -> bool:
    return _update(tid, status=OPEN)


def delete(tid: str) -> bool:
    """Remove a task from the board entirely. Nova herself never deletes (she completes
    or abandons, keeping history — see Design Principle #11); this exists only for Cole's
    manual board controls in the UI, where an explicit remove is sometimes wanted."""
    store = _load()
    if tid in store.get("tasks", {}):
        del store["tasks"][tid]
        _save(store)
        return True
    return False


def reprioritize(tid: str, priority: int) -> bool:
    try:
        return _update(tid, priority=int(priority))
    except Exception:
        return False


def apply_actions(actions: dict):
    """Apply Nova's agency verbs to the board. Returns (log, control) where control
    carries the non-board decisions ('switch' focus id, 'rest' reason) for the
    executive faculty to handle (active focus + rest live in autonomy_state, not here)."""
    log, control = [], {}
    made = {}                       # title(lower) -> new id, for in-batch parent references
    _existing = all_tasks()
    for c in (actions.get("create") or []):
        par = c.get("parent")
        # If `parent` isn't a real task id, it may be a reference to an umbrella created
        # EARLIER in this same batch — resolve it by that task's title (her id won't exist
        # yet when she writes the block). Falls through unchanged if it's already a real id.
        if par and par not in _existing:
            par = made.get(str(par).strip().lower(), par)
        tid = create(c.get("title", ""), c.get("notes", ""), c.get("priority", 3), par)
        made[(c.get("title", "") or "").strip().lower()] = tid
        _actual = (get(tid) or {}).get("parent")
        log.append(f"created {tid}" + (f" under {_actual}" if _actual else "") + f": {c.get('title','')}")
    for p in (actions.get("progress") or []):
        if progress(p.get("id", ""), p.get("note", "")):
            log.append(f"progress {p.get('id')}: {(p.get('note') or '')[:60]}")
    for w in (actions.get("wait") or []):
        if wait(w.get("id", ""), w.get("waiting_on", "")):
            log.append(f"waiting {w.get('id')}: {w.get('waiting_on','')}")
    for a in (actions.get("abandon") or []):
        if abandon(a.get("id", ""), a.get("reason", "")):
            log.append(f"abandoned {a.get('id')}: {a.get('reason','')}")
    for d in (actions.get("complete") or []):
        if complete(d.get("id", ""), d.get("result", "")):
            log.append(f"completed {d.get('id')}")
    for r in (actions.get("reprioritize") or []):
        if reprioritize(r.get("id", ""), r.get("priority", 3)):
            log.append(f"reprioritized {r.get('id')} -> P{r.get('priority')}")
    if actions.get("switch"):
        control["switch"] = actions["switch"]
    if "rest" in actions:
        control["rest"] = actions.get("rest") or ""
    return log, control


def _children_map(tasks: dict) -> dict:
    """parent-id -> [child task dicts]. Tasks with no/dangling parent hang under None
    (top-level). Independent goals are simply separate top-level trees."""
    kids = {}
    for t in tasks.values():
        p = t.get("parent")
        p = p if (p in tasks) else None
        kids.setdefault(p, []).append(t)
    return kids


def render_board(active_id: str = None, max_notes: int = 1) -> str:
    """Nova's cognition view of her board as a TREE — umbrellas with their subtasks
    (and sub-subtasks) nested beneath, so she sees which work feeds what and why.
    Independent goals are separate top-level trees (e.g. 'do taxes' vs 'journal update').
    Settled tasks stay visible (compactly) so she never recreates or redoes them."""
    tasks = all_tasks()
    if not tasks:
        return ("YOUR BOARD is empty — no tasks yet. If something is worth doing, "
                "create it; if nothing is, that's fine.")
    kids   = _children_map(tasks)
    glyph  = {OPEN: "[ ]", WAITING: "[~]", DONE: "[x]", ABANDONED: "[-]"}
    order  = {OPEN: 0, WAITING: 1, DONE: 2, ABANDONED: 3}

    def _done_count(tid):
        ch = kids.get(tid, [])
        return sum(1 for c in ch if c.get("status") in (DONE, ABANDONED)), len(ch)

    L = []
    af = tasks.get(active_id) if active_id else None
    L.append(f"ACTIVE FOCUS: {active_id} — {af['title']}" if af
             else "ACTIVE FOCUS: none (you're not focused on anything right now)")
    L += ["", "YOUR BOARD (tree — subtasks nest under their parent; separate trees are "
          "independent goals):"]

    def _sortkey(t):
        return (order.get(t.get("status"), 9), t.get("priority", 3), t.get("created", ""))

    def render(t, depth, seen):
        tid = t["id"]
        if tid in seen or depth > 8:
            return
        seen.add(tid)
        ind = "  " * depth
        stat = t.get("status", OPEN)
        line = f"{ind}{glyph.get(stat,'[ ]')} {tid} [P{t.get('priority',3)}] {t['title']}"
        done, total = _done_count(tid)
        if total:
            line += f"  ({done}/{total} subtasks done)"
        if tid == active_id:
            line += "   <-- active"
        if stat == DONE and t.get("result"):
            line += f"  — {(t.get('result') or '')[:70]}"
        if stat == ABANDONED:
            line += f"  — dropped: {(t.get('abandon_reason') or '?')[:50]}"
        if stat == WAITING:
            line += f"  — waiting on: {t.get('waiting_on','?')}"
        L.append(line)
        # last progress note only for OPEN leaves (concrete in-flight work)
        if stat == OPEN and not kids.get(tid):
            notes = (t.get("progress") or [])[-max_notes:]
            for n in notes:
                L.append(f"{ind}      ↳ {n.get('note','')}")
            if not notes:
                L.append(f"{ind}      ↳ (not started)")
        for c in sorted(kids.get(tid, []), key=_sortkey):
            render(c, depth + 1, seen)

    seen = set()
    for root in sorted(kids.get(None, []), key=_sortkey):
        render(root, 0, seen)
    return "\n".join(L)
