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
    "watch_paths": ["Tasking/tasks.json", "memory/interrupt_inbox.json",
                    "memory/cole_intent.json"],
}


# ── persisted body state (hers; survives restart) ──────────────────────────────
def _load_state() -> dict:
    base = {"enabled": False, "active": None, "last_wake": "",
            "last_fp": "", "rest_note": ""}
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
    s = _load_state()
    s["last_wake"] = clock.now_iso()
    s["last_fp"] = json.dumps(environment.fingerprint(_cfg()["watch_paths"]), default=list)
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
    if clock.interval_elapsed(st.get("last_wake", ""), cfg["sleep_interval_s"]):
        return (True, "interval")
    return (False, "resting")


# ── present the moment (no model) ──────────────────────────────────────────────
def build_situation(cole_pending: bool, reason: str) -> str:
    st = _load_state()
    board = tasking.render_board(st.get("active"))
    directive = environment.cole_directive()
    last = st.get("last_wake", "")
    L = [f"[AUTONOMY WAKE — {reason}] Right now it is {clock.stamp()} ({clock.time_of_day()})."]
    if last:
        L.append(f"(You last acted {clock.since_human(last)}.)")
    L.append("You woke on your own. This is your time.")
    if directive:
        L += ["", f'COLE — PRIORITY 0 (his word comes first; weigh it): "{directive}"']
    L += ["", "YOUR BOARD:", board, "",
          "Look at your board, your senses, and the moment, and decide FREELY what — if "
          "anything — is worth doing right now. You may advance, switch, create, "
          "reprioritize, wait, abandon, or complete tasks — or REST if nothing is "
          "genuinely worth acting on. Resting is a smart choice, not a failure. Do NOT "
          "invent busywork to look productive. Use your memory, senses, logic, and "
          "intuition; act only on what you judge worthwhile.",
          "",
          "Express your decisions in ONE block (omit keys you don't use):",
          'ACTIONS: {"create":[{"title":"...","notes":"...","priority":2}],'
          ' "progress":[{"id":"t1","note":"what you just did"}], "switch":"t1",'
          ' "wait":[{"id":"t2","waiting_on":"..."}],'
          ' "abandon":[{"id":"t3","reason":"..."}],'
          ' "complete":[{"id":"t1","result":"..."}],'
          ' "reprioritize":[{"id":"t4","priority":3}], "rest":"why you are resting"}',
          "Actually DO each step with your tools BEFORE reporting it."]
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

    if control.get("switch"):
        _set_active(control["switch"])
    engaged = bool(log) or bool(control.get("switch"))
    rested = not engaged

    st = _load_state()
    st["last_wake"] = clock.now_iso()
    st["last_fp"] = json.dumps(environment.fingerprint(_cfg()["watch_paths"]), default=list)
    st["rest_note"] = control.get("rest", "") if rested else ""
    _save_state(st)

    # If she engaged with Cole's standing directive (or consciously rested on it),
    # mark it attended-to so it stops re-surfacing forever (a source of the old loop).
    if environment.cole_directive() and (log or rested):
        environment.consume_cole_directive()

    spoken = ""
    if cole_pending or "FOR COLE:" in (reply or ""):
        spoken = _extract_for_cole(reply)

    summary = (("rested: " + (control.get("rest") or "nothing worth acting on"))
               if rested else ("; ".join(log) or "engaged"))
    return {"summary": summary, "spoken": spoken, "engaged": engaged,
            "rested": rested, "log": log}
