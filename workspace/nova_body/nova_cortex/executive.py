# @nova: Executive will — my self-direction. When my time-sense stirs me (or my
#        environment changes, or Cole speaks) I see my board + my senses + Cole's word,
#        and FREELY decide: work, switch, create, abandon, wait, or rest. I hold my own
#        autonomy on/off. A host tool merely drives this; it never decides for me.
"""
nova_cortex/executive.py — Nova's autonomy / executive faculty
==============================================================
Body-resident self-direction. PURE logic — depends only on her board
(nova_cortex.tasking) and senses (nova_senses.clock/environment). It makes ZERO
outward calls (no chat/server imports), so it survives the pluck-test. A host drives
it in three steps and owns all I/O:

    if executive.should_wake(cole_pending)[0]:
        situation = executive.build_situation(cole_pending, reason)
        reply     = <host runs Nova's mind on `situation`>          # the model
        outcome   = executive.apply_decision(reply, cole_pending)   # she acts
        if outcome["spoken"]: <host speaks outcome["spoken"] to Cole>
        <host logs outcome["summary"]>

Autonomy on/off + active focus persist in memory/autonomy_state.json — hers, not the
server's.
"""

import os
import re
import json
from typing import Optional
from pathlib import Path

from nova_cortex import tasking
from nova_senses import clock, environment

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parent.parent.parent)
_STATE = WORKSPACE_ROOT / "memory" / "autonomy_state.json"

_DEFAULT_CFG = {
    "sleep_interval_s": 300,
    "follow_gap_s": 30,
    "watch_paths": ["Tasking/tasks.json", "memory/interrupt_inbox.json",
                    "memory/cole_intent.json"],
}


# ── persisted body state (hers; survives restart) ──────────────────────────────
def _load_state() -> dict:
    base = {"enabled": False, "active": None, "last_activity": "",
            "wake_at": "", "last_fp": "", "rest_note": ""}
    try:
        if _STATE.exists():
            base.update(json.loads(_STATE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return base


def _save_state(s: dict) -> None:
    try:
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _STATE)
    except Exception as e:
        print(f"[executive] state save failed: {e}")


def autonomy_enabled() -> bool:
    return bool(_load_state().get("enabled"))


def set_autonomy(on: bool) -> None:
    """The on/off the server button merely flips — the state lives here, in her body."""
    s = _load_state()
    s["enabled"] = bool(on)
    _save_state(s)


def active_focus() -> Optional[str]:
    return _load_state().get("active")


def _set_active(tid: Optional[str]) -> None:
    s = _load_state()
    s["active"] = tid
    _save_state(s)


def _cfg() -> dict:
    return dict(_DEFAULT_CFG)


def note_activity() -> None:
    """Mark that Nova just acted (e.g. replied in chat) so her time-sense reflects her
    REAL last activity, not only autonomy wakes — otherwise 'since you last stirred'
    drifts (she'd think minutes passed right after answering). Also re-baselines the
    change fingerprint so files she just touched don't immediately re-wake her."""
    cfg = _cfg()
    s = _load_state()
    s["last_activity"] = clock.now_iso()
    s["last_fp"] = json.dumps(environment.fingerprint(cfg["watch_paths"]), default=list)
    # After she acts/replies, schedule a SOON follow-up think — don't go dormant for the
    # full interval right after responding (that looked like "sleeping without thinking").
    s["wake_at"] = clock.future_iso(cfg["follow_gap_s"])
    _save_state(s)


# ── cheap wake gate (no model) ─────────────────────────────────────────────────
def should_wake(cole_pending: bool = False) -> tuple:
    """Stage-1 gate (no model). Returns (should_wake: bool, reason: str)."""
    st, cfg = _load_state(), _cfg()
    if environment.cole_typing():
        return (False, "cole typing")
    if cole_pending:
        return (True, "cole")
    fp_now = json.dumps(environment.fingerprint(cfg["watch_paths"]), default=list)
    if fp_now != st.get("last_fp", ""):
        return (True, "change")
    wake_at = st.get("wake_at", "")
    if not wake_at or clock.now_iso() >= wake_at:
        return (True, "scheduled")
    return (False, "resting")


# ── present the moment (no model) ──────────────────────────────────────────────
def build_situation(cole_pending: bool, reason: str) -> str:
    st = _load_state()
    active_id = st.get("active")
    board = tasking.render_board(active_id)
    directive = environment.cole_directive()
    last = st.get("last_activity", "")

    # Is my active focus a live, in-progress task (not done/abandoned/waiting)?
    active_task = None
    if active_id:
        t = tasking.all_tasks().get(active_id)
        if t and t.get("status") == "open":
            active_task = t

    L = [f"[AUTONOMY WAKE — {reason}] Right now it is {clock.stamp()} ({clock.time_of_day()})."]
    if last:
        L.append(f"(You last acted {clock.since_human(last)}.)")
    L.append("You woke on your own. This is your time.")
    if directive:
        L += ["", f'COLE — PRIORITY 0 (his word comes first; weigh it): "{directive}"']
    L += ["", "YOUR BOARD:", board, ""]

    if active_task:
        # Work-biased framing — I'm mid-task, so DELIVER it, don't just explore it.
        prog = active_task.get("progress") or []
        steps = f"{len(prog)} step(s) logged" if prog else "no steps logged yet"
        dod = (active_task.get("notes") or "").strip() or \
            "(no explicit goal recorded — decide what 'done' means, state it, and drive to it)"
        stall = int(st.get("stall", 0))
        L += [
            f'ACTIVE TASK [{active_id}] "{active_task.get("title","")}" — {steps}.',
            f"DEFINITION OF DONE: {dod}",
            "First ask: is this DONE? If the deliverable already exists, `complete` it NOW "
            "with its path/result. If not, produce the SINGLE next concrete piece of that "
            "deliverable THIS tick with your tools (write the file, run the command — a real "
            "artifact), then log it as `progress`. Inspecting, re-reading, or exploring "
            "WITHOUT producing the deliverable or closing the task is the failure mode — do "
            "not do it. Every wake on this task MUST end with a `progress`, `complete`, "
            "`abandon`, or `wait` action — never just narration or tool-poking.",
        ]
        if stall >= 2:
            L += [f"!! You have spent {stall} wakes on this and delivered nothing concrete. "
                  "Stop exploring. THIS tick: produce the deliverable and `complete` it, or "
                  "`abandon` it honestly with a reason. Those are your only two options."]
    else:
        # Free-decision framing — no active task, so choose freely (rest included).
        L += [
            "Look at your board, your senses, and the moment, and decide FREELY what — if "
            "anything — is worth doing right now. You may advance, switch, create, "
            "reprioritize, wait, abandon, or complete tasks — or REST if nothing is "
            "genuinely worth acting on. Resting is a smart choice, not a failure. Do NOT "
            "invent busywork to look productive. If you DO take on a task, actually begin "
            "it with your tools this tick (read/run/write) rather than only announcing it. "
            "Use your memory, senses, logic, and intuition; act only on what you judge "
            "worthwhile.",
        ]

    L += ["",
          "Express your decisions in ONE block (omit keys you don't use):",
          'ACTIONS: {"create":[{"title":"...","notes":"...","priority":2}],'
          ' "progress":[{"id":"t1","note":"what you just did"}], "switch":"t1",'
          ' "wait":[{"id":"t2","waiting_on":"..."}],'
          ' "abandon":[{"id":"t3","reason":"..."}],'
          ' "complete":[{"id":"t1","result":"..."}],'
          ' "reprioritize":[{"id":"t4","priority":3}], "rest":"why you are resting"}',
          "A `progress` or `complete` note is ONLY valid if you ACTUALLY ran a tool and "
          "produced a result THIS tick. Never log work you only described — that is the "
          "one thing that breaks trust in your board.",
          "Your machine is Windows and your tools are workspace-relative: pass paths like "
          "`memory/STATUS.md` or `Tasking/tasks.json`, never absolute or Linux "
          "(/home/..., /mnt/...) paths. If unsure what exists, run `list_dir` on a folder "
          "first — don't guess a path and assume it failed."]
    if active_task:
        L.append("`rest` is NOT valid while you hold an active, open task — advance it, "
                 "`complete` it, `abandon` it, or `switch`. Rest is only for when your "
                 "board genuinely has nothing worth doing.")
    if cole_pending:
        L.append("Cole just spoke — reply to him in plain prose ABOVE the ACTIONS block.")
    else:
        L.append("To tell Cole something, put it on a line starting 'FOR COLE:'.")
    return "\n".join(L)


def _parse_actions(reply: str) -> dict:
    """Extract the first balanced ACTIONS JSON object from her reply."""
    if not reply or "ACTIONS:" not in reply:
        return {}
    after = reply.split("ACTIONS:", 1)[1]
    depth, start = 0, None
    for i, ch in enumerate(after):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(after[start:i + 1])
                except Exception:
                    return {}
    return {}


def _extract_for_cole(reply: str) -> str:
    """Pull what she wants spoken to Cole (prose before ACTIONS, or a FOR COLE: line)."""
    if not reply:
        return ""
    m = re.search(r"FOR COLE:\s*(.+)", reply, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).split("ACTIONS:")[0].strip()
    return reply.split("ACTIONS:", 1)[0].strip()


def apply_decision(reply: str, cole_pending: bool = False) -> dict:
    """Apply Nova's free decision (from her reply) to her board + state. Pure; the host
    handles any speaking/logging using the returned outcome. Returns:
      { summary, spoken, engaged, rested, log }"""
    actions = _parse_actions(reply)
    log, control = tasking.apply_actions(actions) if actions else ([], {})

    st = _load_state()
    active_id = st.get("active")

    # Resolve active focus from her decision.
    if control.get("switch"):
        active_id = control["switch"]; _set_active(active_id)
    elif not active_id:
        # Infer focus from her own action: progressing a task adopts it (continuity).
        prog = actions.get("progress") or []
        pid = (prog[0].get("id") if prog and isinstance(prog[0], dict) else None)
        if pid and pid in tasking.all_tasks():
            active_id = pid; _set_active(active_id)

    # What did she do to her active task THIS wake?
    def _ids(key):
        return [a.get("id") for a in (actions.get(key) or []) if isinstance(a, dict)]
    progressed_active = active_id in _ids("progress")
    completed_active  = active_id in _ids("complete")
    abandoned_active  = active_id in _ids("abandon")
    if completed_active or abandoned_active:
        _set_active(None)                                   # closed → free again next wake

    at = tasking.all_tasks().get(active_id) if active_id else None
    active_open = bool(at and at.get("status") == "open") and not (completed_active or abandoned_active)

    engaged = bool(log) or bool(control.get("switch"))
    cfg = _cfg()

    # ── Convergence / stall tracking ─────────────────────────────────────────
    # The failure we're killing: a committed (active, open) task that she merely
    # *explores* wake after wake without delivering or closing. A wake on such a
    # task that produced no progress AND no close is a STALL — come back SOON and
    # escalate, never long-nap or call it "rest".
    if active_open and not (progressed_active or completed_active or abandoned_active):
        stall = int(st.get("stall", 0)) + 1
        rested = False
        gap = cfg["follow_gap_s"]
    else:
        stall = 0
        rested = not engaged                                 # true rest only when idle
        gap = cfg["follow_gap_s"] if engaged else cfg["sleep_interval_s"]

    st["stall"] = stall
    st["last_activity"] = clock.now_iso()
    st["last_fp"] = json.dumps(environment.fingerprint(cfg["watch_paths"]), default=list)
    st["wake_at"] = clock.future_iso(gap)
    st["rest_note"] = control.get("rest", "") if rested else ""
    _save_state(st)

    # Cole's standing directive: mark attended once she acted or genuinely rested.
    if environment.cole_directive() and (log or rested):
        environment.consume_cole_directive()

    spoken = ""
    if cole_pending or "FOR COLE:" in (reply or ""):
        spoken = _extract_for_cole(reply)

    if rested:
        summary = "rested: " + (control.get("rest") or "nothing worth acting on")
    elif stall:
        summary = f"stalled on {active_id} (wake {stall} with no progress/close)"
    else:
        summary = "; ".join(log) or "engaged"
    return {"summary": summary, "spoken": spoken, "engaged": engaged,
            "rested": rested, "stall": stall, "log": log}
