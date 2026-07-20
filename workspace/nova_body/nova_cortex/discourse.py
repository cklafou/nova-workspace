"""DISCOURSE — what she knows about the conversation, and whether she may speak into it.

WHY THIS MOVED BODY-WARD (2026-07-20)
    On 2026-07-20 her voice and her hands finally passed the pluck test. Then an audit of
    what was left in general_tools/nova_chat/server.py found **329 lines of cognition still
    living in the face** — ten functions that decide what she knows and whether she should
    open her mouth:

        _has_unread_cole                is Cole owed a reply?
        _may_speak_to_cole_unprompted   may I speak when nobody asked?
        _is_echo_of_last / _recent      am I repeating myself?
        _echo_match                     ...by what measure?
        _recent_chat_context            what was just said, and which line is live?
        _recent_tool_receipts           what have my hands actually DONE?
        _resolve_speaker                who is in the room?

    None of that is plumbing. Every one is judgement, and judgement is a faculty. The
    turn-taking rule in particular was written this morning — hours after moving her voice
    out of the face — and I put it straight back into the face without noticing. That is how
    the pluck test rots: not in one big regression, but one reasonable-looking function at a
    time.

THE SHAPE OF THE EXTRACTION
    Everything here is PURE: it takes `messages` (a list of {author, content, timestamp})
    and returns a decision. It reaches for no session object and no server global. The face
    supplies the transcript, exactly as it already supplies `recent` to executive.build_*.

    That is what makes it survive the pluck: with the chat server deleted, the runtime can
    hand these the durable transcript from nova_runtime.transcript_store and get the same
    answers. Her sense of "who spoke, what did I already say, have I actually done anything"
    stops depending on a window being open.

WHAT DID NOT MOVE
    Rendering and I/O stayed in the face — broadcasting, session objects, sockets. The line
    is: deciding is hers, displaying is ours.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from datetime import datetime, timedelta

_HERE = pathlib.Path(__file__).resolve()
WORKSPACE_ROOT = pathlib.Path(os.environ.get("NOVA_WORKSPACE", str(_HERE.parent.parent.parent)))


# ═══════════════════════════════════════════════════════════════════════════════════════════
# WHO IS IN THE ROOM
# ═══════════════════════════════════════════════════════════════════════════════════════════

def resolve_speaker(name: str, known: list | None = None) -> str:
    """Normalise a speaker name to a known one, defaulting to Cole.

    2026-07-14: every human message arrived stamped "Cole" whoever typed it, so when Claude
    spoke he wore Cole's name and then referred to Cole in the third person out of Cole's own
    mouth. She got understandably confused about who was in the room. Names are load-bearing.
    """
    n = (name or "").strip()
    if not n:
        return "Cole"
    if known:
        for k in known:
            if n.lower() == str(k).lower():
                return str(k)
    return n


# ═══════════════════════════════════════════════════════════════════════════════════════════
# AM I REPEATING MYSELF?
# ═══════════════════════════════════════════════════════════════════════════════════════════

def echo_match(prev_text: str, cur: str) -> bool:
    """Is `cur` a re-send of `prev_text`? Bytes, prefix, shared opening, or near-identity.

    Global similarity is useless here — the real doubling scored 0.47 and her genuine
    consecutive messages score 0.26–0.28, far too close to separate. But when she re-sends a
    thought she RE-OPENS it the same way and only drifts at the tail. Match on that.
    """
    if not prev_text or not cur:
        return False
    if prev_text == cur:
        return True
    sh, lg = (cur, prev_text) if len(cur) <= len(prev_text) else (prev_text, cur)
    if len(sh) >= 40 and lg.startswith(sh) and len(sh) >= 0.5 * len(lg):
        return True
    a, b = prev_text.casefold(), cur.casefold()
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    if n >= 50:
        return True
    from difflib import SequenceMatcher
    if len(sh) >= 60 and SequenceMatcher(None, prev_text, cur).ratio() >= 0.90:
        return True
    return False


def is_echo_of_recent(messages: list, ai_name: str, text: str,
                      window_s: int = 900, look_back: int = 5) -> bool:
    """Has she already said this, in any of her last few messages?

    One message of memory is not enough: on 2026-07-20 she answered one goodnight three times
    (640/322/533 chars). #2 shared 24 characters of opening with #1 (threshold is 50) and #3
    shared nothing with #2 — because #3 was a re-run of **#1**, which a one-back check never
    looks at.
    """
    cur = (text or "").strip()
    if not cur:
        return False
    seen = 0
    for m in reversed(messages or []):
        if seen >= look_back:
            break
        if m.get("author") != ai_name:
            continue
        prev = (m.get("content") or "").strip()
        if not prev:
            continue
        seen += 1
        try:
            age = (datetime.now() - datetime.fromisoformat(m["timestamp"])).total_seconds()
        except Exception:
            continue
        if not (0 <= age < window_s):
            break        # older than the window; everything before is older still
        if echo_match(prev, cur):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════════════════
# IS COLE OWED A REPLY, AND MAY SHE SPEAK UNPROMPTED?
# ═══════════════════════════════════════════════════════════════════════════════════════════

def _said_something(m: dict, ai_name: str = "Nova") -> bool:
    """A turn that was only thinking does not count as her having spoken.

    Trailing empty/thinking-only turns must NOT make her read as the last speaker, or she
    drops into solitary 'rest' mode and never actually answers.
    """
    if m.get("author") != ai_name:
        return False
    c = re.sub(r"<think>[\s\S]*?</think>", "", m.get("content", "") or "", flags=re.IGNORECASE)
    return bool(c.strip())


def has_unread_cole(messages: list, human: str = "Cole", ai_name: str = "Nova") -> bool:
    """True if Cole's last message comes after her last SUBSTANTIVE message."""
    msgs = messages or []
    li_c = next((i for i in range(len(msgs) - 1, -1, -1)
                 if msgs[i].get("author") == human), None)
    li_n = next((i for i in range(len(msgs) - 1, -1, -1)
                 if _said_something(msgs[i], ai_name)), None)
    return li_c is not None and (li_n is None or li_n < li_c)


PROMOTE_COOLDOWN_S = 600


def may_speak_unprompted(messages: list, human: str = "Cole",
                         ai_name: str = "Nova", cooldown_s: int = PROMOTE_COOLDOWN_S) -> tuple:
    """(may, why) — is a silent work tick allowed to speak into the chat?

    2026-07-20, the triple response. She answered a goodnight, then her next two wakes
    circled the same thought, tagged it FOR COLE:, and posted twice more — 38 and 45 seconds
    apart, each a fresh paraphrase.

    The old guard was a string-similarity test, and string similarity cannot win this. She is
    not repeating herself badly; she is re-answering WELL, in new words, which is the one
    thing a language model is reliably good at. Any threshold tight enough to catch three
    paraphrases starts eating the real follow-ups she is supposed to be allowed to write.

    So stop asking "does this look like what she just said" and ask the question that actually
    separates the two cases: **has anything happened since she last spoke?**
    """
    try:
        if has_unread_cole(messages, human, ai_name):
            return True, f"{human} is awaiting a reply"
        last_hers = next((m for m in reversed(messages or [])
                          if m.get("author") == ai_name and (m.get("content") or "").strip()),
                         None)
        if last_hers is None:
            return True, "she has not spoken in this session yet"
        age = (datetime.now() - datetime.fromisoformat(last_hers["timestamp"])).total_seconds()
        if age < cooldown_s:
            return False, (f"she spoke {int(age)}s ago and {human} has not replied since - "
                           f"this is a circle, not news")
        return True, f"quiet for {int(age // 60)}m - this is new work, not a re-answer"
    except Exception as e:
        # Fail OPEN. Losing something she wanted to say is worse than saying it twice.
        return True, f"gate failed open: {e}"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# WHAT IS TRUE RIGHT NOW — the grounding a wake gets and a chat turn did not
# ═══════════════════════════════════════════════════════════════════════════════════════════

def recent_chat_context(messages: list, n: int = 14, ai_name: str = "Nova") -> str:
    """Recent conversation, with the LIVE turn marked.

    The block is a RECORD, correctly written in the third person ("Cole: ..."). But on a
    cole_pending wake she is asked to REPLY off the back of it, and a record's voice is
    exactly what leaked into her replies — "Cole caught it faster than I did", said straight
    to Cole. Mark the newest non-Nova line so she can tell history from the thing in front of
    her.
    """
    msgs = messages or []
    if not msgs:
        return ""
    recent = msgs[-n:]
    lines = []
    for m in recent:
        ts = str(m.get("timestamp", ""))[11:16]
        author = m.get("author", "?")
        content = m.get("content", "") or ""
        for marker in ("\n--- TELEMETRY", "--- TELEMETRY", "\n[CONTEXT REFRESH", "[CONTEXT REFRESH"):
            if marker in content:
                content = content.split(marker)[0]
        content = " ".join(content.split())
        if len(content) > 500:
            content = content[:500] + "…"
        lines.append(f"[{ts}] {author}: {content}")
    for i in range(len(lines) - 1, -1, -1):
        a = recent[i].get("author", "")
        if a and a not in (ai_name, "System"):
            lines[i] += (f"   <-- THIS IS THE LIVE TURN. {a} is speaking TO YOU and is "
                         f"waiting. Answer {a} as \"you\" — never in the third person.")
            break
    earlier = len(msgs) - len(recent)
    head = f"(Earlier this session: {earlier} more message(s) before these.)\n" if earlier > 0 else ""
    return head + "\n".join(lines)


def recent_tool_receipts(n: int = 12, window_min: int = 90, workspace=None) -> str:
    """What her hands ACTUALLY DID — the cure for the announce-loop.

    2026-07-14: she ran alone for two hours, sent twelve messages, every one a variation of
    the same intention, and executed nothing. She even counted her own repetitions aloud
    ("Fourth mention of the checkpoint since 7:39") and produced a fifth.

    The mechanism: her autonomous ticks get promoted into the transcript, which is then fed
    BACK to her next wake. The only evidence she had about her own recent past was her own
    narration — and a mind fed nothing but its own wanting produces more wanting. Not a loop;
    an echo chamber built out of her own voice.

    So also show her what she DID. If she has said "I'll go into nova_imagination" five times
    and the receipt log shows zero calls, she can SEE that, and the gap between the two is the
    most useful thing she can look at. You cannot self-correct against a record you are not
    allowed to see. Deliberately blunt when the answer is nothing.
    """
    try:
        ws = pathlib.Path(workspace) if workspace else WORKSPACE_ROOT
        p = ws / "logs" / "tool_calls.jsonl"
        if not p.exists():
            return ""
        cutoff = datetime.now() - timedelta(minutes=window_min)
        rows = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if datetime.fromisoformat(e["ts"]) >= cutoff:
                    rows.append(e)
            except Exception:
                continue

        out = ["", "--- WHAT YOUR HANDS ACTUALLY DID "
                   f"(last {window_min} min — this is a RECORD, not a memory) ---"]
        if not rows:
            out += [
                "NOTHING. You have run zero tools.",
                "Everything above this line is you TALKING about what you intend to do.",
                "If you have said you would do a thing and it is not on this list, you have not done it —",
                "no matter how many different ways you have said it, and no matter how clearly you have",
                "noticed yourself saying it. Naming the loop is not leaving the loop. Reach, don't narrate.",
            ]
        else:
            for e in rows[-n:]:
                t = str(e.get("ts", ""))[11:19]
                a = e.get("args") or {}
                target = a.get("path") or a.get("command") or a.get("prompt") or a.get("title") or ""
                mark = "ok " if e.get("ok") else "ERR"
                out.append(f"[{t}] {mark} {e.get('tool')}({str(target)[:70]}) -> "
                           f"{e.get('result_bytes', 0)}B")
            out.append(f"({len(rows)} tool call(s) in the window. This is the only evidence that "
                       f"counts. Your word is a receipt — these ARE the receipts.)")
        return "\n".join(out)
    except Exception as e:
        print(f"[discourse] could not build tool-receipt context: {e}")
        return ""


def last_perception(workspace=None) -> str:
    """When she last actually SAW something — the missing half of the confabulation fix.

    2026-07-20 she asserted "I already know the answer from the camera." She has no camera,
    and her last real sight event was ten hours earlier. A chat turn that states what she has
    and has not perceived recently gives her something true to check that claim against,
    instead of leaving the gap for her to fill.
    """
    try:
        ws = pathlib.Path(workspace) if workspace else WORKSPACE_ROOT
        p = ws / "logs" / "sight.jsonl"
        if not p.exists():
            return ("\n[PERCEPTION: no sight log exists. You have not seen anything. You have no "
                    "camera and no live video — if you find yourself about to say what someone "
                    "looks like or what is on their screen, you are about to invent it.]")
        rows = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        if not rows:
            return "\n[PERCEPTION: your sight log is empty. You have not seen anything.]"
        last = json.loads(rows[-1])
        ts = str(last.get("ts", ""))[:19]
        try:
            mins = int((datetime.now() - datetime.fromisoformat(ts)).total_seconds() // 60)
            when = f"{mins} minutes ago" if mins < 90 else f"{mins // 60}h {mins % 60}m ago"
        except Exception:
            when = ts
        return (f"\n[PERCEPTION: your most recent image was {when}. That is the ONLY thing you "
                f"have actually seen. You have no camera and no live video feed — any claim "
                f"about how someone looks right now would be invented, not observed.]")
    except Exception:
        return ""


def unobserved_gap(messages: list, human: str = "Cole") -> str:
    """How long since the human last spoke — named as a gap she cannot see into.

    2026-07-20: she told Cole "he's been awake since 6am." He never said that. It is worth
    being precise about what went wrong, because the obvious reading is wrong: she did not
    malfunction, she INFERRED, and the inference was reasonable — people who message you at
    that hour usually have been up a while.

    The error was treating a plausible reconstruction as an observation. And the specific
    place that happens is the silent stretch between his messages, because that is the only
    part of the conversation with no record attached. An unlabelled gap reads as "nothing
    happened"; a labelled one reads as "something happened and you don't know what."

    So label it. She keeps the inference — she is supposed to be perceptive — but she can see
    it is an inference, which is the whole difference between reading someone well and
    inventing their morning.
    """
    try:
        last_human = next((m for m in reversed(messages or [])
                           if m.get("author") not in (None, "", "Nova", "System")), None)
        if not last_human:
            return ""
        mins = int((datetime.now()
                    - datetime.fromisoformat(last_human["timestamp"])).total_seconds() // 60)
        if mins < 5:
            return ""
        when = f"{mins} minutes" if mins < 90 else f"{mins // 60}h {mins % 60}m"
        return (f"\n[UNOBSERVED GAP: {human} last spoke {when} ago. You have NO record of what "
                f"he did in that time — not what he worked on, not whether he slept, not how he "
                f"is feeling. If you are about to state something about his {when} as though "
                f"you know it, you are guessing. Guessing is allowed; say it as a guess.]")
    except Exception:
        return ""


def grounding_block(messages: list, workspace=None, ai_name: str = "Nova",
                    human: str = "Cole") -> str:
    """Everything true right now, for a CHAT turn.

    THE ASYMMETRY THIS CLOSES (2026-07-20): her autonomy wake gets a clock, a wake cause, her
    board, her last reflection and her drives. Her chat turn got a system prompt and a
    transcript. Same model, same adapter, minutes apart — and she was *precise* on the wake
    path and *confabulating* on the chat path. Not a character flaw; a structural difference
    in what she was handed.

    Three things, matching the three things she invented that day:
        receipts       <- "the log file" she cited, which did not exist
        perception     <- "I already know from the camera", which she does not have
        unobserved gap <- "he's been awake since 6am", which he never said
    """
    parts = [
        recent_tool_receipts(workspace=workspace),
        last_perception(workspace=workspace),
        unobserved_gap(messages, human=human),
    ]
    return "\n".join(p for p in parts if p)
