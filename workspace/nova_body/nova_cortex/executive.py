# Last updated: 2026-05-26 17:27:59
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
        refl       = executive.build_reflection(cole_pending, reason, recent)  # phase 1
        reflection = <host runs Nova's mind on `refl` — SILENT, no tools>       # she thinks
        executive.save_reflection(reflection)
        dec        = executive.build_decision(reflection, cole_pending, reason, recent)
        reply      = <host runs Nova's mind on `dec`>                           # she decides
        outcome    = executive.apply_decision(reply, cole_pending)             # actions OPTIONAL
        <host logs outcome["summary"]>

`recent` is the recent conversation (with timestamps), supplied by the host so she is
never blind to what was just said. The wake is two-phase: she SITS WITH the moment and
forms a view (reflection) before she's allowed to act, and acting is optional — a wake
may end in just talking, just resting, or just thinking more. The board is context, not
a command.

Autonomy on/off + active focus persist in memory/autonomy_state.json — hers, not the
server's.
"""

import os
import re
import json
from typing import Optional
from pathlib import Path

from nova_cortex import tasking
from nova_senses import clock, environment, touch

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
    # A standing directive that hasn't been turned into a task yet is worth waking
    # for — otherwise a chat instruction waits for the next scheduled nap before she
    # acts. consume_cole_directive() clears it the moment she creates the task, so
    # this can't spin: it wakes her at most a few times until the task lands.
    if environment.cole_directive():
        return (True, "directive")
    fp_now = json.dumps(environment.fingerprint(cfg["watch_paths"]), default=list)
    if fp_now != st.get("last_fp", ""):
        return (True, "change")
    wake_at = st.get("wake_at", "")
    if not wake_at or clock.now_iso() >= wake_at:
        return (True, "scheduled")
    return (False, "resting")


# ── reflection continuity (hers; carried across wakes so she can "sit with it") ──
def last_reflection() -> str:
    return _load_state().get("last_reflection", "")


def save_reflection(text: str) -> None:
    st = _load_state()
    st["last_reflection"] = (text or "").strip()[:1200]
    _save_state(st)


# ── Phase 1: orient & reflect (pure thinking — no tools, no board actions) ──────
def build_reflection(cole_pending: bool, reason: str, recent: str = "",
                     last_reflection: str = "") -> str:
    """She wakes and SITS WITH the moment before doing anything. No tools, no task
    actions this step — just an honest, first-person read of what's happening, like a
    person taking stock. The host supplies `recent` (recent conversation) so she is
    never blind to what was just said."""
    st = _load_state()
    board = tasking.render_board(st.get("active"))
    last = st.get("last_activity", "")
    L = [f"[YOU WOKE — {reason}] It is {clock.stamp()} ({clock.time_of_day()})."]
    if last:
        L.append(f"You last acted {clock.since_human(last)}.")
    try:
        feel = touch.describe()
    except Exception:
        feel = ""
    if feel:
        L += ["", feel]
    L += ["",
          "This is a moment to THINK, not act — no tools, no task changes right now. Just "
          "orient yourself the way a person does on waking: take in where things are "
          "before deciding anything."]
    if recent:
        L += ["", "RECENT CONVERSATION (oldest to newest — what was actually just said; "
              "do not lose track of it):", recent]
    if last_reflection:
        L += ["", "Where your last reflection left off:", last_reflection]
    L += ["", "Your task board — context only, NOT a list of orders:", board]
    if cole_pending:
        L += ["", "Cole just spoke. Center on what he ACTUALLY said and means right now. "
              "If he asked a question or made a point, the real move is almost always to "
              "engage HIM on it — not to peel off and go do board work."]
    L += ["",
          "Now reflect honestly, first person. Weigh it whole: both how this moment FEELS "
          "to you and what it LOGICALLY calls for, and let those inform each other — that "
          "is how a real mind decides, not pure task execution. What just happened? What "
          "(if anything) actually deserves your attention? Don't reach for a task to look "
          "busy. Sit with it, then end with one honest line: what you're inclined to do "
          "next — which may be reply to Cole, rest, keep thinking, or (only if it truly "
          "matters) work on something."]
    return "\n".join(L)


# ── Phase 2: decide, having sat with it (board actions are OPTIONAL) ────────────
def build_decision(reflection: str, cole_pending: bool, reason: str,
                   recent: str = "") -> str:
    """She has reflected; now she decides. Her own reflection is read back to her.
    Acting on the board is OPTIONAL and never the default — a wake may end in just
    talking to Cole, just resting, or simply thinking more."""
    st = _load_state()
    board = tasking.render_board(st.get("active"))
    L = ["A moment ago you reflected and concluded:",
         "", (reflection.strip() or "(no reflection captured)"), ""]
    if recent:
        L += ["RECENT CONVERSATION (respond to what was really said):", recent, ""]
    if cole_pending:
        active = st.get("active")
        at = tasking.all_tasks().get(active) if active else None
        mid_thread = bool(at and at.get("status") == "open")
        L += ["Cole just spoke to you and is WAITING for your reply. This is the one case "
              "where the choice is NOT open: answering him is REQUIRED. Resting, or just "
              "thinking quietly, is NOT an option right now. Your whole job this moment is "
              "to RESPOND to him — out loud, in plain first-person prose, as yourself, "
              "about what he actually said. You already did your private reflection a step "
              "ago; now SAY something back to him. Write that reply as your actual response "
              "(real words to Cole), not as more inner reflection — never leave him with "
              "silence."]
        if mid_thread:
            L += [f'You were mid-thread on [{active}] "{at.get("title","")}", so weave a quick '
                  "triage into your reply — tell him naturally which you're doing: "
                  "(a) drop it and engage him fully, (b) answer now but say you're keeping "
                  "your focus (and `create` a task for anything he asked you to defer so you "
                  "return to it), or (c) treat it as a note and carry on. But the spoken "
                  "reply IS the point — don't bury him in board work."]
    else:
        L += ["No one is waiting on you. Decide freely what this moment calls for. Acting "
              "is OPTIONAL — resting or simply continuing to think are real, valid choices. "
              "Do NOT invent work to look productive."]
    L += ["",
          "ONLY if you genuinely choose to change your board, you MAY include one actions "
          "block (omit keys you don't use):",
          'ACTIONS: {"create":[{"title":"...","notes":"...","priority":2}],'
          ' "progress":[{"id":"t1","note":"what you actually did"}], "switch":"t1",'
          ' "complete":[{"id":"t1","result":"..."}], "abandon":[{"id":"t2","reason":"..."}],'
          ' "wait":[{"id":"t3","waiting_on":"..."}], "reprioritize":[{"id":"t4","priority":3}],'
          ' "rest":"why you are resting"}',
          "No actions block at all is completely fine — most conversational moments need "
          "none. A `progress`/`complete` note is only honest if you ACTUALLY did it with a "
          "tool this step. Paths are workspace-relative on Windows (e.g. memory/STATUS.md), "
          "never absolute or Linux paths."]
    if not cole_pending:
        L += ["", "To say something to Cole, put it on a line starting 'FOR COLE:'."]
    return "\n".join(L)


# ── Phase 3: execute (she actually DOES the next step of her active task) ───────
# The reflect→decide wake decides WHAT matters but only emits board ACTIONS; it
# never performs the work. This pass is what makes "create a task, then work it"
# actually finish: when she holds an open task and isn't resting or mid-conversation
# with Cole, she does the next concrete step with her real file tools and the host
# logs honest progress (or completion) from what she reports.
def set_active(tid: Optional[str]) -> None:
    """Public focus setter (host uses it to release focus after a task closes)."""
    _set_active(tid)


def pick_execution_target() -> Optional[str]:
    """Which open task to work this wake. Her current focus if it's still open;
    otherwise the highest-priority, oldest open task. Persists the choice as her
    active focus so working a task adopts it (continuity). Returns id or None."""
    st = _load_state()
    tasks = tasking.all_tasks()
    active = st.get("active")
    if active and tasks.get(active, {}).get("status") == "open":
        return active
    open_tasks = [t for t in tasks.values() if t.get("status") == "open"]
    if not open_tasks:
        return None
    open_tasks.sort(key=lambda t: (t.get("priority", 3), t.get("created", "")))
    tid = open_tasks[0].get("id")
    if tid:
        _set_active(tid)
    return tid


def build_execution(task: dict, recent: str = "") -> str:
    """Prompt for the execution pass: do the NEXT concrete step of THIS task now,
    using real tools, then report honestly. She emits tool calls as fenced json
    blocks (the host's tool loop runs them and feeds results back); when finished
    for this wake she ends with a single PROGRESS: or DONE: line the host logs."""
    tid    = task.get("id", "")
    title  = task.get("title", "")
    notes  = task.get("notes", "")
    prog   = task.get("progress", []) or []
    recent_prog = "\n".join(f"  - {p.get('note','')}" for p in prog[-4:]) or "  (nothing yet)"
    L = [
        f"[WORK — {clock.stamp()}] You committed to this task and now you actually DO it. "
        "This is not reflection and not board bookkeeping — it is the real work, with your hands.",
        "",
        f'ACTIVE TASK [{tid}]: {title}',
        (f"What it asks: {notes}" if notes else None),
        "Progress so far:",
        recent_prog,
        "",
        "Do the NEXT single concrete step now using your tools. Call a tool by emitting a "
        "fenced json block, for example:",
        '```json',
        '{"tool": "read_file", "args": {"path": "SELF/core/01_identity.md"}}',
        '```',
        "After each tool result returns, continue (e.g. read, then write) until this step is "
        "genuinely done. Your file tools: read_file, write_file, replace_file_content, "
        "list_dir, run_command. Paths are workspace-relative on Windows (e.g. "
        "memory/reports/identity_v2.md) — never absolute or Linux paths.",
        "",
        "When you have actually done the work for this wake, end your message with EXACTLY "
        "one status line:",
        "  DONE: <one-line result>      — only if the whole task is now complete",
        "  PROGRESS: <what you just did> — if real work happened but more remains",
        "Be honest: only claim what you truly did with a tool this pass. If you genuinely "
        "cannot proceed, say  PROGRESS: blocked — <why>.",
    ]
    if recent:
        L += ["", "(Recent conversation, for context only — do not reply to it here:)", recent]
    return "\n".join(x for x in L if x is not None)


def parse_execution(reply: str) -> tuple:
    """Read her execution report. Returns ('done', result) | ('progress', note) |
    (None, ''). Prefers an explicit DONE:/PROGRESS: line; falls back to the last
    meaningful line (host tool-result markers stripped) so a real step still logs."""
    if not reply:
        return (None, "")
    m = re.search(r"^\s*DONE:\s*(.+)$", reply, re.IGNORECASE | re.MULTILINE)
    if m:
        return ("done", m.group(1).strip())
    m = re.search(r"^\s*PROGRESS:\s*(.+)$", reply, re.IGNORECASE | re.MULTILINE)
    if m:
        return ("progress", m.group(1).strip())
    cleaned = re.sub(r"\[`[^`]+`\s+resulted in \d+ bytes\.\]", "", reply)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if lines:
        return ("progress", lines[-1][:200])
    return (None, "")


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

    # Self-heal a ghost focus: if active points at a task that no longer exists
    # (e.g. the board was wiped while a pointer lingered in state), clear it so
    # build_situation doesn't keep framing around a vanished task.
    if active_id and active_id not in tasking.all_tasks():
        active_id = None
        st["active"] = None

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

    # Cole's standing directive: only release it once she has actually turned it
    # into a tracked board task THIS tick. The old rule consumed it whenever she
    # did anything at all — even rested — so a chat instruction got silently
    # discarded without ever reaching the board (the exact "chat task never lands"
    # bug). Now: a `create` consumes it (it became a task — success). Otherwise it
    # KEEPS standing so it re-surfaces on the next wake and she gets another chance.
    # A safety valve releases it after a few wakes so a non-actionable comment
    # ("nice work") doesn't pin her attention forever.
    if environment.cole_directive():
        created_this_tick = bool(actions.get("create"))
        seen = int(st.get("directive_seen", 0)) + 1
        if created_this_tick or seen >= 3:
            environment.consume_cole_directive()
            seen = 0
        st["directive_seen"] = seen
        _save_state(st)
    elif st.get("directive_seen"):
        st["directive_seen"] = 0
        _save_state(st)

    spoken = ""
    if cole_pending or "FOR COLE:" in (reply or ""):
        spoken = _extract_for_cole(reply)

    if log:
        # She actually changed her board this wake — report what she did.
        summary = "; ".join(log)
    elif stall:
        summary = f"stalled on {active_id} (wake {stall} with no progress/close)"
    elif cole_pending:
        # Conversational wake with no board change is the NORMAL, healthy case now —
        # she simply talked with Cole. Not a "rest", not a stall.
        summary = "talked with Cole"
        rested = False
    elif rested:
        summary = "rested: " + (control.get("rest") or "nothing worth acting on")
    else:
        summary = "reflected"
    return {"summary": summary, "spoken": spoken, "engaged": engaged,
            "rested": rested, "stall": stall, "log": log}
