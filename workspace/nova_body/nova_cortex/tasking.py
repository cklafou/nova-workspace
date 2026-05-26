# Last updated: 2026-05-26 14:46:05
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


def create(title: str, notes: str = "", priority: int = 3) -> str:
    store = _load()
    store["seq"] += 1
    tid = f"t{store['seq']}"
    try:
        pr = int(priority)
    except Exception:
        pr = 3
    store["tasks"][tid] = {
        "id": tid, "title": (title or "").strip() or f"(untitled {tid})",
        "notes": notes or "", "priority": pr, "status": OPEN,
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
    for c in (actions.get("create") or []):
        tid = create(c.get("title", ""), c.get("notes", ""), c.get("priority", 3))
        log.append(f"created {tid}: {c.get('title','')}")
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


def render_board(active_id: str = None, max_notes: int = 2) -> str:
    """Nova's cognition view of her board — what she sees each wake to decide freely.
    Shows her active focus, what's open to advance/switch, what's parked, and what's
    settled (so she never recreates or redoes it)."""
    tasks = all_tasks()
    if not tasks:
        return ("YOUR BOARD is empty — no tasks yet. If something is worth doing, "
                "create it; if nothing is, that's fine.")
    buckets = {OPEN: [], WAITING: [], DONE: [], ABANDONED: []}
    for t in tasks.values():
        buckets.get(t.get("status", OPEN), buckets[OPEN]).append(t)
    L = []
    af = tasks.get(active_id) if active_id else None
    L.append(f"ACTIVE FOCUS: {active_id} — {af['title']}" if af
             else "ACTIVE FOCUS: none (you're not focused on anything right now)")
    if buckets[OPEN]:
        L += ["", "OPEN (yours to advance, switch among, reprioritize, or leave):"]
        for t in sorted(buckets[OPEN], key=lambda x: x.get("priority", 3)):
            L.append(f"  {t['id']} [P{t.get('priority',3)}] {t['title']}")
            notes = (t.get("progress") or [])[-max_notes:]
            for n in notes:
                L.append(f"        ↳ {n.get('note','')}")
            if not notes:
                L.append("        ↳ (not started)")
    if buckets[WAITING]:
        L += ["", "WAITING (parked — outside your hands; resume when it clears):"]
        for t in buckets[WAITING]:
            L.append(f"  {t['id']} {t['title']} — waiting on: {t.get('waiting_on','?')}")
    if buckets[DONE]:
        L += ["", "DONE (finished — do NOT recreate or redo):"]
        for t in buckets[DONE]:
            extra = f" — {(t.get('result') or '')[:80]}" if t.get("result") else ""
            L.append(f"  {t['id']} {t['title']}{extra}")
    if buckets[ABANDONED]:
        L += ["", "ABANDONED (you dropped these — do NOT recreate or redo):"]
        for t in buckets[ABANDONED]:
            L.append(f"  {t['id']} {t['title']} — reason: {t.get('abandon_reason','?')}")
    return "\n".join(L)
