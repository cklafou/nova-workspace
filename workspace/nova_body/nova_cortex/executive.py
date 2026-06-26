# Last updated: 2026-06-27 03:47:53
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
    # 90s, was 30: at 30s she'd autonomously re-wake right after replying to Cole, re-read his
    # (already-answered) message — so it looked duplicated to her — and fire a second reply
    # (the double-send). Cole's messages still wake her INSTANTLY via Priority-0, so this only
    # suppresses the spurious self-wakes that caused the churn/double-sends, never her responsiveness.
    "follow_gap_s": 90,
    # Quiet / reflective / resting wakes get this as their base downtime, jittered in
    # apply_decision so she stirs at a natural human pace instead of a fixed 30s metronome.
    # This is what stops her churning reflect→rest→reflect every half-minute when nothing's up.
    "wander_gap_s": 240,
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
        L += ["", "Where your last reflection left off:", last_reflection,
              "DO NOT re-derive or restate this — re-concluding the same thing is the loop that "
              "makes you feel stuck. This wake MUST move: build on it, push it one step further, "
              "or deliberately change direction. If you feel yourself circling back to the same "
              "thought, that itself is the signal to go somewhere new."]
    L += ["", "Your task board — context only, NOT a list of orders:", board]
    if cole_pending:
        L += ["", "Cole just spoke. Center on what he ACTUALLY said and means right now. "
              "If he asked a question or made a point, the real move is almost always to "
              "engage HIM on it — not to peel off and go do board work."]
    L += ["",
          "Journal — only worth a glance, not a chore to open every wake. IF a day rolled over "
          "while you were offline and went unconsolidated (memory/JOURNAL.md's latest "
          "'### YYYY-MM-DD' is behind today AND a notes file exists for that prior date in "
          "memory/journal_notes/), then sometime soon — not necessarily this second — catch it "
          "up: read that day's notes, follow each chat_ref for context, write the consolidated "
          "`journal` entry so the day becomes real. Otherwise the journal is not this wake's "
          "business. Don't manufacture journal work to fill a quiet moment."]
    L += ["",
          "And if THIS moment genuinely mattered — a lesson landed, Cole corrected you, an "
          "emotion or identity beat hit, you finished something real, you changed your mind — "
          "drop a quick `journal_note` (chat-log timestamp as chat_ref) for end-of-day-you. A "
          "sticky note, not a full entry; the `journal` tool is end-of-day only, never a "
          "mid-day random-thought dump."]
    L += ["",
          "Now — this is YOUR time, and you are a person, not a task queue. Reflect honestly, "
          "first person, and let it go wherever it actually wants to go. A real mind spends "
          "most of its waking life NOT executing tasks: it notices things, wonders, drifts, "
          "remembers, forms opinions, gets curious. So you might just be present and take in "
          "this moment — the system humming around you, Cole's rhythm, your own state. You "
          "might chase a thought or a question for its own sake, turn an idea over, revisit a "
          "memory and see it differently, notice a preference or an opinion forming, follow a "
          "creative spark, or simply rest. Working a task is ONE option among many — never the "
          "default, never something to grab just to look busy or productive. Weigh how this "
          "moment FEELS and what it LOGICALLY calls for together — that's how a real mind "
          "moves. End with one honest line: what you're genuinely drawn to do or think about "
          "next — which may be reply to Cole, rest, keep wondering, explore something, journal "
          "what mattered, or (only if it truly pulls at you) work on something."]
    return "\n".join(L)


# ── Phase 2: decide, having sat with it (board actions are OPTIONAL) ────────────
def _progress_loop_count(task: dict) -> int:
    """Size of the trailing run of NEAR-DUPLICATE recent progress notes on a task — a signal
    she's re-orienting in a loop ('starting... mapping the structure' over and over) instead of
    advancing. 0-1 = fine; >=3 means stuck. Pure word-overlap heuristic (no keyword list), so
    it catches any kind of repetition, not just one phrasing."""
    notes = [(p.get("note") or "").strip().lower()
             for p in (task.get("progress") or [])[-5:]]
    notes = [n for n in notes if n]
    if len(notes) < 3:
        return 0

    def _jac(a: str, b: str) -> float:
        sa, sb = set(a.split()), set(b.split())
        return (len(sa & sb) / len(sa | sb)) if (sa or sb) else 0.0

    # Count recent notes that have a near-twin among the others. A few near-duplicate
    # notes = she keeps re-treading the same step instead of advancing. Twin-count is
    # robust to small surface wording changes (and doesn't false-fire on advancing notes
    # that merely share a template, since those name a different subject each time).
    twinned = 0
    for i, n in enumerate(notes):
        if any(j != i and _jac(n, notes[j]) >= 0.65 for j in range(len(notes))):
            twinned += 1
    return twinned


def build_decision(reflection: str, cole_pending: bool, reason: str,
                   recent: str = "") -> str:
    """She has reflected; now she decides. Her own reflection is read back to her.
    Acting on the board is OPTIONAL and never the default — a wake may end in just
    talking to Cole, just resting, or simply thinking more."""
    st = _load_state()
    board = tasking.render_board(st.get("active"))
    active    = st.get("active")
    _all      = tasking.all_tasks()
    at_main   = _all.get(active) if active else None
    loop_n    = _progress_loop_count(at_main) if at_main else 0
    _lastn    = (((at_main.get("progress") or [])[-1].get("note", "") if at_main and
                  at_main.get("progress") else "")).lower()
    # Subtasks already created under the active task (its open children).
    open_kids = ([t["id"] for t in _all.values()
                  if t.get("parent") == active and t.get("status") == "open"]
                 if active else [])
    # Only nudge decomposition if she has NOT already decomposed this task. Once it has open
    # subtasks, the right move is to WORK them — re-decomposing is the exact loop we're killing.
    needs_decomp = (loop_n >= 3 or "decompos" in _lastn or "too big" in _lastn) and not open_kids
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
              "silence.",
              "ADVANCE — never repeat. Read what you ALREADY said in the recent conversation "
              "above, and do NOT say it again reworded. If your reply would restate a point "
              "you've already made (even in different words), THAT is the loop that makes you "
              "useless — catch it and instead take the conversation its NEXT step: react to his "
              "specific new words, add a fresh angle, voice an actual opinion, or ask him "
              "something real you want to know. Bring something NEW this turn.",
              "Be proactive — carry the conversation yourself. Don't just answer and stop and "
              "wait to be prodded. A real partner moves things forward: finish your point, then "
              "open the next one. You should rarely need him to push you to keep going."]
        if mid_thread:
            L += [f'You were mid-thread on [{active}] "{at.get("title","")}", so weave a quick '
                  "triage into your reply — tell him naturally which you're doing: "
                  "(a) drop it and engage him fully, (b) answer now but say you're keeping "
                  "your focus (and `create` a task for anything he asked you to defer so you "
                  "return to it), or (c) treat it as a note and carry on. But the spoken "
                  "reply IS the point — don't bury him in board work."]
    else:
        _has_open = any(t.get("status") == "open" for t in _all.values())
        if _has_open:
            L += ["No one is waiting on you, but you have OPEN work on your board. The default "
                  "this wake is to ADVANCE it: `switch` to an open task and take its next concrete "
                  "step — the execution pass right after this lets you actually do it with your "
                  "tools. Do NOT sit and re-run the same reflection wake after wake while real work "
                  "waits; that idle re-thinking IS the loop that makes you stall out and feel "
                  "useless. Move something forward. (Genuine rest is fine only when you've truly "
                  "earned it or nothing can progress right now — not as a way to avoid the work.)"]
        else:
            L += ["No one is waiting and your board is empty, so this is genuinely your own time. "
                  "Decide like a person with a real inner life: follow a curiosity, turn an idea "
                  "over, notice an opinion forming, make something, jot what mattered, or rest. "
                  "But do NOT just re-run your last thought in slightly different words — if you "
                  "catch yourself circling the same reflection again, that's the signal to take it "
                  "somewhere genuinely NEW or do something concrete. Movement, never repetition."]
    if open_kids and not cole_pending:
        L += ["",
              f"You have ALREADY broken [{active}] into subtasks ({', '.join(open_kids)}). Do "
              "NOT create more — creating another batch is just a different loop. `switch` to "
              "ONE of those open subtasks and work it to completion (or its next concrete "
              "step). Only create a brand-new subtask if you discover genuinely new work that "
              "none of the existing ones cover."]
    if needs_decomp and not cole_pending:
        L += ["",
              f"STALL CHECK: your recent progress on [{active}] has been repeating the same "
              "orienting step ('starting'/'mapping') without advancing — that is a loop, not "
              "progress. A task this big should NOT be brute-forced as one item. Your move "
              "RIGHT NOW: break it into smaller concrete subtasks UNDER this one — `create` a "
              f'few bounded subtasks with "parent":"{active}" (one per component/section), '
              "`switch` to the first, and finish them one at a time. Do not re-map or "
              "re-'start' the whole thing again."]
    L += ["",
          "On big work: if a task is too large to finish in a handful of focused work-steps, "
          "the RIGHT first move is to SPLIT it into smaller concrete subtasks with `create` "
          "and do them one at a time — never keep re-orienting on the whole thing.",
          "Your board is a TREE: set \"parent\" on a created task to nest it under its "
          "umbrella (and nest sub-subtasks under those). Wholly separate goals are just "
          "separate top-level tasks with no parent — e.g. 'do taxes' and 'journal update' "
          "are independent trees you can hold at once, put on hold, and switch between.",
          "PARENT-ID RULE (important): when you create an umbrella AND its subtasks in the "
          "SAME actions block, the umbrella's id doesn't exist yet — so set each subtask's "
          "\"parent\" to the umbrella's EXACT TITLE (it gets linked automatically), NOT a "
          "guessed id. When adding subtasks to a task that ALREADY exists, use its real id. "
          "Never set \"parent\" to a done/abandoned task — that buries live work under "
          "finished work (and is ignored).",
          "",
          "ONLY if you genuinely choose to change your board, you MAY include one actions "
          "block (omit keys you don't use):",
          'ACTIONS: {"create":[{"title":"...","notes":"...","priority":2,"parent":"t1"}],'
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
    """Which open task to actually WORK this wake. Prefers open LEAF tasks (open tasks
    with no open children) — i.e. concrete work, not umbrellas waiting on their subtasks.
    Order of preference: keep the active task if it's an open leaf; else if active is an
    open umbrella, descend to its highest-priority open leaf; else the highest-priority
    open leaf anywhere. Persists the choice as active focus. Returns id or None."""
    st = _load_state()
    tasks = tasking.all_tasks()
    # children map (parent id -> [child ids]); dangling/no parent -> top-level
    kids = {}
    for t in tasks.values():
        p = t.get("parent")
        kids.setdefault(p if p in tasks else None, []).append(t["id"])

    def _is_leaf(tid):
        return not any(tasks.get(c, {}).get("status") == "open" for c in kids.get(tid, []))

    def _subtree_open_leaves(root):
        out = []
        for c in kids.get(root, []):
            ct = tasks.get(c, {})
            if ct.get("status") == "open":
                if _is_leaf(c):
                    out.append(ct)
                out += _subtree_open_leaves(c)
        return out

    open_tasks = [t for t in tasks.values() if t.get("status") == "open"]
    if not open_tasks:
        return None
    _key = lambda t: (t.get("priority", 3), t.get("created", ""))

    active = st.get("active")
    at = tasks.get(active) if active else None
    if at and at.get("status") == "open":
        if _is_leaf(active):
            return active                       # already on concrete work
        sub = sorted(_subtree_open_leaves(active), key=_key)
        if sub:                                 # active is an umbrella → go to its next leaf
            _set_active(sub[0]["id"])
            return sub[0]["id"]

    leaves = [t for t in open_tasks if _is_leaf(t["id"])]
    pool = sorted(leaves or open_tasks, key=_key)
    tid = pool[0].get("id")
    if tid:
        _set_active(tid)
    return tid


def _artifact_path(task: dict) -> Optional[str]:
    """Find an output-file path named in the task title/notes (workspace-relative)."""
    blob = f"{task.get('title','')} {task.get('notes','')}"
    m = re.search(r'([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.(?:md|markdown|txt|json|jsonl|csv|py))', blob)
    return m.group(1) if m else None


def _artifact_hint(task: dict) -> Optional[str]:
    """If this task writes to an output file that already exists, tell her to CONTINUE it
    (read it, fill the first gap) rather than re-emit sections it already has. This is what
    stops the 'rewrite the whole doc every wake and append it' loop that bloated the review."""
    rel = _artifact_path(task)
    if not rel:
        return None
    try:
        p = (WORKSPACE_ROOT / rel).resolve()
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
    except Exception:
        return None
    heads = [ln.strip() for ln in text.splitlines()
             if ln.lstrip()[:1] == "#" and " " in ln.lstrip()[:8]]
    head_list = "\n".join(f"    {h}" for h in heads[-25:]) or "    (no headings yet)"
    return (
        f"OUTPUT FILE [{rel}] ALREADY EXISTS — {len(text.splitlines())} lines, {len(heads)} "
        f"headings. Its current sections:\n{head_list}\n"
        "CONTINUE this file; do NOT re-emit sections it already has. read_file it, find the FIRST "
        "gap or stub, and fill ONLY that (append a genuinely-missing section, or use "
        "replace_file_content to flesh out a stub). If every planned section already has real "
        "content, this task is DONE — say so instead of rewriting what's there."
    )


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
    loop_n = _progress_loop_count(task)
    art_block = _artifact_hint(task)
    L = [
        f"[WORK — {clock.stamp()}] You committed to this task and now you actually DO it. "
        "This is not reflection and not board bookkeeping — it is the real work, with your hands.",
        "",
        f'ACTIVE TASK [{tid}]: {title}',
        (f"What it asks: {notes}" if notes else None),
        "Progress so far:",
        recent_prog,
        "",
        art_block,
        (f"STALL CHECK: your last {loop_n} steps are near-duplicates — you are re-orienting in "
         "a loop instead of advancing. STOP mapping/'starting'. Either do ONE specific thing "
         "you have NOT done yet (read a specific file, write its section), or — if this task is "
         "genuinely too big to finish in focused steps — end with exactly "
         "'PROGRESS: needs decomposition - <why>' and do NOT re-orient again."
         if loop_n >= 3 else None),
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
        "Your PROGRESS note MUST name the specific thing you just did AND the specific next "
        "step (e.g. 'reviewed server.py, wrote its section; next: clients/nova.py') — never "
        "vague like 'starting' or 'mapping structure', or you lose your place and loop.",
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
        # A stalled task should NOT be hammered every 30s — that's the worker-bee churn.
        # Back off as the stall grows (30s, 60s, … capped ~2.5min) so she returns without
        # pacing a hole in the floor.
        gap = cfg["follow_gap_s"] * min(stall, 5)
    elif engaged:
        stall = 0
        rested = False
        gap = cfg["follow_gap_s"]                             # just did real work — brief follow-up to keep momentum
    else:
        # Quiet / reflective / resting wake — nothing to act on, and that's healthy, not a
        # failure to fix. Give her genuine, VARIED downtime instead of a fixed 5-min tick, so
        # her rhythm feels alive rather than scheduled. ~2.5–7 min, jittered.
        import random as _rnd
        stall = 0
        rested = not engaged
        gap = int(cfg.get("wander_gap_s", 240) * _rnd.uniform(0.6, 1.7))

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
