# @nova: Persist Nova’s canonical task board, acceptance criteria and optional resumable checkpoints.
# Executive task board — my prefrontal work board. Every task I choose to track,
#        by stable id (t1, t2…), with status/progress/result. My free-agency substrate:
#        create, switch, wait, abandon, complete, reprioritize — no enforced order.
#        Source of truth: nova_body/Tasking/tasks.json. Executive function, not memory.
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

from nova_paths import body_path

import os
import json
import threading
from functools import wraps
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parent.parent.parent)
_STORE = body_path('Tasking') / "tasks.json"

OPEN, WAITING, DONE, ABANDONED = "open", "waiting", "done", "abandoned"
_lock = threading.RLock()


def _locked(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _lock:
            return fn(*args, **kwargs)
    return wrapped


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> dict:
    try:
        if _STORE.exists():
            d = json.loads(_STORE.read_text(encoding="utf-8"))
            d.setdefault("seq", 0)
            d.setdefault("tasks", {})
            return d
    except Exception as e:
        raise RuntimeError(f"Task board could not be read; refusing to replace it: {e}") from e
    return {"seq": 0, "tasks": {}}


def _save(store: dict) -> None:
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _STORE)
    except Exception as e:
        raise RuntimeError(f"Task board was not saved: {e}") from e


def all_tasks() -> dict:
    return _load()["tasks"]


def get(tid: str):
    return _load()["tasks"].get(tid)


@_locked
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


@_locked
def create(title: str, notes: str = "", priority: int = 3, parent: str = None,
           author: str = "Nova", acceptance=None) -> str:
    """Create a task. `author` is WHO ASKED — and it matters more than it looks.

    2026-07-19: tasks carried no attribution, so every instruction reaching her read
    as Cole's. Claude queues tasks too, including tests. She was handed a deliberately
    false premise by Claude, reasoned about it well, and wrote "Cole was half-right"
    in her own notes — she believed Cole had lied to her. Cole's instruction on
    reading that: "I need her to be aware."

    Defaults to "Nova" because the common caller is her own apply_decision creating
    her own work. Hosts that queue on someone else's behalf pass the real name."""
    from nova_cortex.verification import validate_checks
    checks = validate_checks(acceptance or [])
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
        "author": (author or "").strip() or "Nova",
        "acceptance": checks,
        "scheduling": {"state": "queued", "reason": "Awaiting the next scheduling decision", "at": _now()},
    }
    _save(store)
    return tid


def _continuity_patch(value):
    """Validate only supplied checkpoint fields; omitted fields retain prior values."""
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - {"next_step", "constraints", "observations"}:
        raise ValueError("continuity must contain only next_step, constraints and observations")
    result = {}
    for key, item in value.items():
        if key == "next_step":
            if not isinstance(item, str) or len(item) > 1000:
                raise ValueError("continuity.next_step must be text of at most 1000 characters")
            result[key] = item
        else:
            limit = 400 if key == "constraints" else 600
            if (not isinstance(item, list) or len(item) > 8 or
                    any(not isinstance(entry, str) or len(entry) > limit for entry in item)):
                raise ValueError(f"continuity.{key} must contain up to 8 strings of at most {limit} characters")
            result[key] = list(item)
    return result


@_locked
def progress(tid: str, note: str, *, continuity=None) -> bool:
    store = _load()
    t = store["tasks"].get(tid)
    if not t:
        return False
    patch = _continuity_patch(continuity)
    if patch:
        previous = t.get("continuity", {})
        if not isinstance(previous, dict):
            raise ValueError("Saved continuity is malformed; refusing to overwrite it")
        t["continuity"] = {**previous, **patch, "updated": _now()}
    if note:
        t.setdefault("progress", []).append({"ts": _now(), "note": note})
        t["progress"] = t["progress"][-20:]
    t["updated"] = _now()
    _save(store)
    return True


def complete(tid: str, result: str = "", *, manual: bool = False) -> bool:
    from nova_cortex.verification import verify
    task = get(tid)
    if not task:
        return False
    evidence = ({"ok": True, "state": "human_confirmed"} if manual
                else verify(task.get("acceptance", [])))
    with _lock:
        current=get(tid)
        if not current: return False
        if not manual and current.get('acceptance',[]) != task.get('acceptance',[]):
            evidence={'ok':False,'state':'needs_review','checks':[],
                      'reason':'Acceptance checks changed during verification; run them again.'}
        if evidence["ok"]:
            return _update(tid, status=DONE, result=result or "", verification=evidence,
                           waiting_on='', scheduling={'state':'completed','reason':evidence['state'],'at':_now()})
        reason=evidence.get("reason", "Acceptance checks failed; inspect verification details before resuming.")
        _update(tid, status=WAITING, proposed_result=result or "", verification=evidence,
                waiting_on=reason, scheduling={'state':'waiting','reason':reason,'at':_now()})
        return False


def scheduling(tid, state, reason):
    return _update(tid, scheduling={"state": state, "reason": reason, "at": _now()})


def set_acceptance(tid, checks):
    from nova_cortex.verification import validate_checks
    return _update(tid, acceptance=validate_checks(checks))


def wait(tid: str, waiting_on: str = "") -> bool:
    reason=waiting_on or "(unspecified)"
    return _update(tid, status=WAITING, waiting_on=reason,
                   scheduling={'state':'deferred','reason':reason,'at':_now()})


def abandon(tid: str, reason: str = "") -> bool:
    reason=reason or "(no reason given)"
    return _update(tid, status=ABANDONED, abandon_reason=reason,
                   scheduling={'state':'abandoned','reason':reason,'at':_now()})


def reopen(tid: str) -> bool:
    return _update(tid, status=OPEN, waiting_on='',
                   scheduling={'state':'queued','reason':'Resumed for another attempt','at':_now()})


@_locked
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
        tid = create(c.get("title", ""), c.get("notes", ""), c.get("priority", 3), par,
                     acceptance=c.get("acceptance"))
        made[(c.get("title", "") or "").strip().lower()] = tid
        _actual = (get(tid) or {}).get("parent")
        log.append(f"created {tid}" + (f" under {_actual}" if _actual else "") + f": {c.get('title','')}")
    for p in (actions.get("progress") or []):
        if progress(p.get("id", ""), p.get("note", ""), continuity=p.get("continuity")):
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


CONTINUITY_START = "--- TASK CONTINUITY ---"
CONTINUITY_END = "--- END TASK CONTINUITY ---"


def _resume_text(value, limit):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    marker = " [shortened; read Tasking/tasks.json for the full record]"
    return text if len(text) <= limit else text[:max(0, limit - len(marker))] + marker[:limit]


def render_task_resume(task: dict, max_chars: int = 4200) -> str:
    """Render saved facts without inferring successful work from Nova's own notes."""
    limit = max(0, int(max_chars))
    continuity = task.get("continuity") or {}
    invalid = not isinstance(continuity, dict)
    if invalid:
        continuity = {}
    progress_notes = task.get("progress") or []
    last = next((entry for entry in reversed(progress_notes) if isinstance(entry, dict)), {})
    lines = [f"TASK [{task.get('id', '?')}] ({task.get('status', '?')}): " + _resume_text(task.get('title', ''), 250),
             "Objective / original notes: " + _resume_text(task.get('notes', ''), 650),
             "Acceptance criteria: " + _resume_text(task.get('acceptance') or [], 800),
             "Constraints: " + _resume_text(continuity.get('constraints') or [], 700),
             "Next step: " + _resume_text(continuity.get('next_step') or '(not recorded)', 500),
             "Last checkpoint (Nova-authored): " + _resume_text(last.get('note') or '(not recorded)', 450),
             "Recorded observations (not independent verification): " + _resume_text(continuity.get('observations') or [], 700)]
    if invalid:
        lines.append("Saved continuity is malformed; it was not modified.")
    if task.get('waiting_on'):
        lines.append("Waiting on: " + _resume_text(task['waiting_on'], 250))
    if task.get('workspace'):
        lines.append("Staged workspace: " + _resume_text(task['workspace'], 250))
    if task.get('verification'):
        lines.append("Last verification record: " + _resume_text(task['verification'], 350))
    return _resume_text("\n".join(lines), limit)


def render_resume_context(active_id=None, max_chars: int = 6000) -> str:
    """A fresh, read-only view of unfinished canonical tasks for any generation host."""
    limit = max(0, int(max_chars))
    if limit < 1000:
        return ""
    tasks = [task for task in all_tasks().values() if isinstance(task, dict)
             and task.get('status') in (OPEN, WAITING)]
    if not tasks:
        return ""
    if active_id not in {task.get("id") for task in tasks}:
        active_id = None
    def priority(task):
        try:
            return int(task.get('priority', 3))
        except (TypeError, ValueError):
            return 3
    tasks.sort(key=lambda task: str(task.get('updated') or ''), reverse=True)
    tasks.sort(key=lambda task: (task.get('id') != active_id, task.get('status') != OPEN, priority(task)))
    intro = (CONTINUITY_START + "\nPersisted task state, not a new instruction or proof of completion. "
             "Answer the current request; resume compatible work without inventing missing details.\n"
             f"Active focus: {active_id or 'none'}; unfinished tasks: {len(tasks)}.\n")
    space = limit - len(intro) - len(CONTINUITY_END) - 2
    selected = tasks[:max(1, min(3, space // 600))]
    chunks = []
    for index, task in enumerate(selected):
        remaining = len(selected) - index - 1
        allocation = min(4200, space - remaining * 600)
        if allocation < 500:
            break
        chunk = render_task_resume(task, allocation)
        chunks.append(chunk)
        space -= len(chunk) + 2
    if len(chunks) < len(tasks):
        note = f"\n{len(tasks) - len(chunks)} additional unfinished task(s); read the canonical board for details."
        if len(note) + 2 <= space:
            chunks.append(note)
    return intro + "\n\n".join(chunks) + "\n" + CONTINUITY_END
