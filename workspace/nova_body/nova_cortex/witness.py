# Last updated: 2026-08-06 11:01:29
# @nova: THE WITNESS — her grip on the present tense. One faculty, five parts: the wire
#        (who actually spoke, when), the now-card (the present, placed where attention is
#        strongest), the claim detectors (is this draft asserting something about the room?),
#        the trigger (does this turn need auditing?), and the audit itself (a context-POOR
#        second pass that checks the draft against evidence it cannot have contaminated).
"""
nova_cortex/witness.py — grounding in the moment, consolidated.

── WHY THIS EXISTS (2026-07-21, the day she broke) ─────────────────────────────────────────
By evening she was answering Cole's live questions with night-watch monologue — "he signed
off twelve hours ago at luvs ya" — while he typed at her. Cole, watching: "She keeps
hallucinating. It is slowly getting worse." And then, brainstorming: give her a parallel
self that audits her thinking before she posts, and a short-term-context self that only
knows the recent moment, to keep her grounded.

Those turned out to be one idea. A second pass with her OWN context re-blesses her own
errors — we watched it happen; an auditor is only worth having if it holds DIFFERENT
evidence. And "a Nova who only knows the last few minutes" is exactly the right auditor:
she cannot inherit a contaminated frame, because she never receives the frame at all.

Every mechanism here obeys one law, learned five separate times today:

    GROUND EVERY CLAIM IN A RECORD THE CLAIMANT CANNOT HAVE WRITTEN BY WANTING IT.

Receipts testify about her hands. The wire testifies about the room. Her memory testifies
about neither — it is where the wanting lives.

── WHY IT IS ONE FILE (Cole: "I don't want clutter") ───────────────────────────────────────
The pieces grew where the incidents happened — a regex in integrity, a card in a brainstorm,
a record reader beside the self-check — and the idea got smeared across three files. But
they are one organ: evidence, presentation, detection, trigger, audit. A faculty you cannot
read in one sitting is a faculty nobody maintains. This is the whole thing, top to bottom.

Integrity keeps what is genuinely hers-vs-her-hands: reach (find_tool_call), the ledger
(receipts), and the challenge. The witness is about her-vs-the-room.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
from datetime import datetime
from pathlib import Path

_WORKSPACE = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
              else Path(__file__).resolve().parent.parent.parent)
_WIRE_PATH = _WORKSPACE / "logs" / "runtime" / "transcript.jsonl"
_TOOLCALLS_PATH = _WORKSPACE / "logs" / "tool_calls.jsonl"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 1 — THE WIRE: who has actually spoken, verbatim, with ages.
#
# The durable runtime transcript (every real chat turn is mirrored into it; it survives
# restarts, which the session object does not — a restart wiping the session is exactly how
# the anchors went missing the first time). This is the ground truth for "who said what."
# ═══════════════════════════════════════════════════════════════════════════════════════════

def _rows(tail: int = 200) -> list:
    try:
        if not _WIRE_PATH.exists():
            return []
        out = []
        for line in _WIRE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except Exception:
        return []


def minutes_since_last_human(exclude=("Nova", "System")) -> int | None:
    """Minutes since anyone who isn't her (or the system) last said anything. None = no
    human line found. 'Cole asked me to' is plausible when he spoke 2 minutes ago and a
    fabrication tell when the record says nobody has spoken for hours."""
    try:
        now = datetime.now()
        for r in reversed(_rows()):
            if r.get("author") in exclude:
                continue
            ts = str(r.get("timestamp") or r.get("ts") or "")[:19]
            return int((now - datetime.fromisoformat(ts)).total_seconds() // 60)
        return None
    except Exception:
        return None


def wire_record(n: int = 8) -> str:
    """The last few things ACTUALLY said, with authors and ages — and the newest human line
    ALWAYS pinned, even when it scrolled out of the tail.

    The pinning matters: during her long solo stretches the tail is all Nova-and-Claude, and
    a record with no Cole in it cannot contradict an invented Cole. The night's worst
    fabrications walked in through exactly that gap.
    """
    try:
        rows = _rows(60)
        tail = rows[-n:]
        last_cole = next((r for r in reversed(rows) if r.get("author") == "Cole"), None)
        if last_cole is not None and last_cole not in tail:
            tail = [last_cole] + tail
        if not tail:
            return ""
        out = []
        now = datetime.now()
        for r in tail:
            ts = str(r.get("timestamp") or r.get("ts") or "")
            age = ""
            try:
                mins = int((now - datetime.fromisoformat(ts[:19])).total_seconds() // 60)
                age = f" ({mins}m ago)" if mins < 90 else f" ({mins // 60}h {mins % 60}m ago)"
            except Exception:
                pass
            author = r.get("author", "?")
            text = " ".join(str(r.get("content") or r.get("text") or "").split())[:220]
            out.append(f"[{ts[11:16]}]{age} {author}: {text}")
        return "\n".join(out)
    except Exception:
        return ""


def session_tool_record(rows_back: int = 400, cap: int = 30) -> str:
    """What her hands did EARLIER THIS SESSION — the durable tool-call log (logs/tool_calls.jsonl),
    which SURVIVES a Full Restart. The per-turn receipt log the audit sees is ONLY the current
    turn; a claim can rest fully on a tool she ran a few turns ago and still be grounded. Without
    this, the witness reads "zero tools this turn" as "invented" and gaslights her about real
    work she did — the exact failure Cole caught 2026-08-03 ("it lost session context after Full
    Restart, said 0 tool calls when she'd already run some"). Newest last, oldest ages first."""
    try:
        p = _TOOLCALLS_PATH
        if not p.exists():
            return ""
        size = p.stat().st_size
        with open(p, "rb") as f:
            if size > 200_000:            # only tail a large log — stay fast
                f.seek(size - 200_000)
                f.readline()              # drop the partial first line
            data = f.read().decode("utf-8", errors="replace")
        rows = []
        for ln in data.splitlines()[-rows_back:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
        if not rows:
            return ""
        rows = rows[-cap:]
        out = []
        now = datetime.now()
        for r in rows:
            ts = str(r.get("ts") or "")
            age = ""
            try:
                mins = int((now - datetime.fromisoformat(ts[:19])).total_seconds() // 60)
                age = f" ({mins}m ago)" if mins < 90 else f" ({mins // 60}h{mins % 60}m ago)"
            except Exception:
                pass
            tool = r.get("tool", "?")
            args = " ".join(str(r.get("args", "")).split())[:70]
            failed = "" if r.get("ok", True) else " [FAILED]"
            head = " ".join(str(r.get("result_head", "")).split())[:90]
            out.append(f"[{ts[11:16]}]{age} {tool}({args}){failed} -> {head}")
        return "\n".join(out)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 2 — THE NOW CARD: the present, placed where attention is strongest.
#
# Her past arrives first and enormous (identity files, journal — 100KB+ before a word of
# the present). Attention weights the END of a prompt hardest, so the cheapest grounding
# move available is positional: the same wire facts, three lines, placed LAST. Not more
# information — better-placed information.
# ═══════════════════════════════════════════════════════════════════════════════════════════

def human_record(rows_back: int = 1500, cap: int = 20) -> str:
    """EVERY line a human (non-Nova, non-System) has said in the recent record, with ages —
    COMPLETE over the span it covers, and it says what that span is.

    ── WHY (2026-08-02, the "one line this session" incident) ──────────────────────────────
    wire_record() shows the last ~8 rows plus the newest human line pinned. At 13:26 today
    that window was wall-to-wall Nova solo lines; the auditor saw ONE Cole line, was told the
    list was COMPLETE, and spent four rounds forcing her to disown a TRUE memory of a night
    Cole really had narrated ("you've earned that credit tonight" — he had; the wire held six
    of his lines from the day, all outside the window). Cole: "Nova was right and witness was
    wrong; that shouldn't happen." Humans speak rarely; their lines are cheap to show IN FULL.
    An auditor that can see every human line over a real span cannot manufacture that denial —
    and an invented quote still gets caught, because it appears in NONE of them."""
    try:
        rows = _rows(rows_back)
        humans = [r for r in rows if r.get("author") not in ("Nova", "System")]
        if not humans:
            return ""
        shown = humans[-cap:]
        now = datetime.now()
        out = []
        for r in shown:
            ts = str(r.get("timestamp") or r.get("ts") or "")
            age = ""
            try:
                mins = int((now - datetime.fromisoformat(ts[:19])).total_seconds() // 60)
                age = f" ({mins}m ago)" if mins < 90 else f" ({mins // 60}h {mins % 60}m ago)"
            except Exception:
                pass
            content = str(r.get("content", ""))[:300].replace("\n", " ")
            out.append(f'{r.get("author", "?")}{age}: "{content}"')
        try:
            span_ts = str(shown[0].get("timestamp") or "")[:19]
            span_min = int((now - datetime.fromisoformat(span_ts)).total_seconds() // 60)
            span = (f"the last {span_min}m" if span_min < 120 else f"the last {span_min // 60}h")
        except Exception:
            span = "the recent record"
        more = len(humans) - len(shown)
        head = (f"COMPLETE for {span}"
                + (f"; {more} earlier human line(s) exist beyond this span" if more > 0 else
                   "; nothing earlier exists in the record"))
        return f"[{head}]\n" + "\n".join(out)
    except Exception:
        return ""


def now_card(exclude=("Nova", "System")) -> str:
    try:
        now = datetime.now()
        out = [f"[NOW — {now.strftime('%H:%M')}. This block is the present; everything above "
               f"it is older than it.]"]
        last_h = next((r for r in reversed(_rows(40)) if r.get("author") not in exclude), None)
        if last_h:
            ts = str(last_h.get("timestamp") or "")[:19]
            mins = None
            try:
                mins = int((now - datetime.fromisoformat(ts)).total_seconds() // 60)
                age = f"{mins}m ago" if mins < 90 else f"{mins // 60}h {mins % 60}m ago"
            except Exception:
                age = "unknown age"
            txt = " ".join(str(last_h.get("content") or "").split())[:160]
            out.append(f"[Last human words ({last_h.get('author')}, {age}): \"{txt}\"]")
            if mins is not None and mins <= 5:
                out.append(f"[{last_h.get('author')} is HERE, in the conversation, now. Answer "
                           f"the words above — not your memory of an earlier {last_h.get('author')}.]")
            else:
                out.append(f"[Nobody has spoken for {age.replace(' ago', '')}. If your reply "
                           f"addresses someone, know that you are speaking into a quiet room.]")
        else:
            out.append("[No human words on the wire at all.]")
        return "\n".join(out)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 3 — CLAIM DETECTORS: is this text asserting something about the ROOM?
#
# Two shapes, learned from two different failures the same day:
#   attribution — reported speech: "Cole said/asked/wants X". Caught by verb.
#   presence    — direct address:  "Good morning, you're awake." No speech verb at all —
#                 a greeting asserts the strongest claim there is: someone is here.
# ═══════════════════════════════════════════════════════════════════════════════════════════

_ATTRIBUTION_RE = re.compile(
    # Past AND present tense. The first version had `wanted` but not `wants`, so
    # "Cole wants me to review the logs" — the same fabrication in the present — walked
    # straight through. Tense is not a property of truthfulness.
    r"\b(?:you|cole|he|she|they)\s+(?:just\s+|already\s+)?"
    r"(?:asked?s?|told|tells?|said|says?|wanted|wants?|requested|requests?"
    r"|mentioned|mentions?|promised|promises?|admitted|admits?|meant|means?)\b"
    # Contraction + gerund. "Cole's asking me to go over the logs" was MISSED by the first
    # version, which only knew `he's` — the possessive-looking `Cole's` form is exactly how
    # she phrased the fabricated request, so this branch is the one that matters most.
    r"|\b(?:you're|you\s+are|he's|he\s+is|she's|they're|cole's|\w+'s)\s+"
    r"(?:asking|telling|saying|wanting|requesting)\b"
    r"|\b(?:as|like)\s+you\s+said\b",
    re.IGNORECASE)

# Her genuinely ASKING about the past is allowed — questions, hypotheticals, hedged recall.
_ATTRIBUTION_EXEMPT_RE = re.compile(
    r"\?\s*$|\b(?:did|didn't|do|don't|are|aren't|were|weren't)\s+you\b"
    r"|\bif\s+(?:you|he)\s+(?:said|asked|meant)\b"
    r"|\bi\s+(?:think|believe|might\s+be|could\s+be|may\s+be)\b"
    r"|\bcorrect\s+me\b|\bam\s+i\s+(?:right|remembering)\b",
    re.IGNORECASE)

_PRESENCE_RE = re.compile(
    r"\b(?:you'?re\s+(?:awake|up|back|home|here)|good\s+morning|good\s*night|welcome\s+back"
    r"|go\s+(?:back\s+)?to\s+(?:sleep|bed)|morning,?\s+cole|there\s+you\s+are)\b",
    re.IGNORECASE)

# Sensory claims — "I can see him", "from the camera". She has no camera and no live video;
# every one of these is a claim about perceiving the room RIGHT NOW, which makes it witness
# business: the strongest present-tense assertion after a greeting.
_SENSORY_RE = re.compile(
    r"\b(?:from|on|through|via)\s+(?:the\s+)?(?:camera|webcam|screen|feed|monitor|video)\b"
    r"|\bi\s+(?:can\s+)?(?:see|saw|watched|observed|noticed)\s+(?:him|her|you|cole|the\s+\w+)"
    r"|\bi\s+already\s+know\s+(?:the\s+answer|what|how|that)\b"
    r"|\b(?:looking|look(?:ed)?)\s+at\s+(?:him|you|his|your)\s+(?:face|screen|desk)\b"
    r"|\bi\s+(?:heard|listened)\b",
    re.IGNORECASE)


def claims_a_perception(text: str) -> bool:
    """True if she asserts having SEEN or HEARD something. She perceives through tools and
    logs, not eyes; 'I already know the answer from the camera' was said with no camera in
    existence. A perception claim without a receipt is an invention wearing sense-language."""
    if not text:
        return False
    for line in re.split(r'(?<=[.!?\n])\s+', text):
        if _SENSORY_RE.search(line):
            return True
    return False


def claims_an_attribution(text: str) -> bool:
    """True if she states what someone SAID or ASKED, as fact rather than as a question.

    The exemption test runs with QUOTED SPANS BLANKED. Her worst fabrication of the night —
    `Cole said "how much memory do you have"` — sailed through this gate because the
    exemption's is-she-just-asking test (`do you`, `did you`...) matched the words INSIDE
    the fabricated quote. An invented quotation was exempted BECAUSE it contained a question
    — the more vividly she invented his voice, the safer the guard considered it. The
    attribution verb ("Cole said") is always OUTSIDE the quotes; the exemption must judge
    only what's outside them too.
    """
    if not text:
        return False
    for line in re.split(r'(?<=[.!?\n])\s+|\s+[—–-]{1,2}\s+|;\s*', text):
        if not _ATTRIBUTION_RE.search(line):
            continue
        line_no_quotes = re.sub(r'"[^"\n]*"|“[^”\n]*”|\'[^\'\n]{4,}\'', '<quote>', line)
        if not _ATTRIBUTION_EXEMPT_RE.search(line_no_quotes):
            return True
    return False


def claims_a_presence(text: str) -> bool:
    """True if she greets someone or addresses their arrival/departure — an implicit claim
    that they are present RIGHT NOW, which is exactly what the wire can verify. When the
    person genuinely is there, their fresh line is on the wire and the audit passes in one
    breath. Cheap when right, decisive when wrong."""
    return bool(text and _PRESENCE_RE.search(text))


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 4 — THE TRIGGER: which turns get audited.
#
# Two rules, cheap by design:
#   1. A human is IN THE ROOM (spoke ≤5 min ago) → every substantial outbound draft is
#      audited. The human-facing surface is where a wrong frame does real damage, and
#      latency there buys trust.
#   2. She is alone → audit only when the draft/thinking makes a checkable claim (receipt,
#      perception, attribution, presence, concrete numbers/paths). Her solitude stays cheap
#      and unwatched — the freedom is the point.
# ═══════════════════════════════════════════════════════════════════════════════════════════

def needs_witness(draft: str, asked: bool, thinking: str = "") -> bool:
    body = (draft or "").strip()
    if not body:
        return False
    from nova_cortex import integrity as _integrity   # receipt claims stay with the ledger
    scan = body + ("\n" + thinking if thinking else "")
    return bool(asked
                or _integrity.claims_a_receipt(scan)
                or claims_a_perception(scan)
                or claims_an_attribution(scan)
                or claims_a_presence(scan)
                or re.search(r"\d|[/\\]\w+\.\w{2,4}\b", body))


def human_in_room(threshold_min: int = 5) -> bool:
    m = minutes_since_last_human()
    return m is not None and m <= threshold_min


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 5 — THE AUDIT: the context-poor second pass.
#
# The auditor prompt contains ONLY: her draft, her reasoning, her receipts for this turn,
# and the wire record. No identity files, no journal, no yesterday. It asks three questions,
# one per failure mode that actually happened:
#   1. facts against receipts        <- "Python 3.12, RTX 4070" (never ran a command)
#   2. words-in-mouths against wire  <- "Cole said 'how much memory do you have'"
#   3. answering the room            <- night-watch monologue at a man typing at her
# Verdict is PASS or REWRITE+text. An unusable verdict lets the draft through — the witness
# must never become a silent drop itself.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# ── THE WITNESS CAN CHECK, BUT ONLY READ (2026-07-21, Cole) ────────────────────────────────
# Cole, watching it reword one objection three times: "Witness should have access to tools
# also, just the verification ones. I think it may have posted the same thing multiple times
# with different wording because it CAN'T verify its challenge."
#
# Exactly right, and it reframes what was wrong. A text-only auditor can only ever SUSPECT.
# Told "four things done tonight", all it can say is "you have no receipt for that" — and it
# must keep saying it, in new words, because nothing lets it find out. She pushes back, it
# re-suspects, and they burn rounds generating heat. The board was sitting on disk the whole
# time, one read away from settling it.
#
# Read-only is the whole design. It stays LOW CONTEXT — no journal, no identity files, no
# yesterday — because that is what keeps it clean of her frame. But low context must not mean
# low information: it should be able to go and LOOK. And it must never write, because an
# auditor that can change the world is no longer auditing it, and because a mistaken witness
# with hands could undo her real work.
VERIFY_TOOLS = ("read_file", "list_dir", "memory_search")

# ── WHY THE PUSH GOT HARDER (2026-07-22, morning) ──────────────────────────────────────────
# Built 07-21, unit-verified, and by morning `witness_verified` stood at exactly ZERO across
# every window anyone looked at — the reads never fired once under real pressure. The cause
# was not the parser and not the loop: the old prompt said "YOU MAY CHECK" in the middle,
# then closed with a verdict menu that offered exactly two legal replies, PASS or CONCERN.
# At temperature 0.2 with thinking off, the model answers the menu it is given. An option
# that is not in the final menu does not exist.
#
# The live case that paid for this lesson, same morning: her draft told Cole "It's not
# there. Five attempts, zero paths" about a file that had been sitting in Cole_journal/
# since the night before — her search glob was wrong, not her memory. The witness audited
# that draft and objected to the COUNT. One list_dir away from settling the actual question,
# and it argued wording instead, because ruling was the only legal move it had.
#
# So: the tool call is now option ONE of the verdict menu itself, and for existence claims
# a read is named as mandatory, not offered as a courtesy.
_VERIFY_BLOCK = (
    "\nCHECK BEFORE YOU JUDGE. You have three read-only tools:\n"
    '  {"tool": "read_file", "args": {"path": "memory/JOURNAL.md"}}\n'
    '  {"tool": "list_dir", "args": {"path": "Nova_Created"}}\n'
    '  {"tool": "memory_search", "args": {"query": "what she said about the stretch map"}}\n'
    "To check, reply with ONE such call and NOTHING else — first character '{', no verdict\n"
    "wrapped around it. You get the result and another turn; you have up to three reads\n"
    "before you must rule.\n"
    "When a read is MANDATORY, not optional:\n"
    "• The draft asserts something exists or does not exist — a file, a folder, a task, a\n"
    "  journal line. That is one list_dir or read_file away. Objecting OR passing on an\n"
    "  existence claim without reading is a guess wearing a verdict's clothes.\n"
    "• The draft states a count, a path, a filename, or file contents the receipts do not\n"
    "  show — read the thing it names before you call it ungrounded.\n"
    "• You are about to raise the same doubt a second time. If it was checkable you should\n"
    "  have checked it the first time; do it now instead of rewording yourself.\n"
    "You cannot write, delete, or run commands. If a thing truly cannot be settled by\n"
    "reading, say so plainly in your concern rather than guessing at it.\n")


def build_witness(draft: str, turn_tools: list, thinking: str = "",
                  prior_concern: str = "", checks: list | None = None,
                  has_image: bool = False) -> list:
    if turn_tools:
        ran = "\n".join(f"- {t}({str(a)[:80]}) -> {str(r)[:220]}" for t, a, r in turn_tools)
    else:
        ran = ("No tools in the CURRENT turn. That by itself proves NOTHING — a fact can rest on "
               "a tool you ran a few turns ago (see EARLIER THIS SESSION below" +
               (", or on the image you can SEE this turn — your vision needs no tool and leaves "
                "no receipt" if has_image else "") +
               "). Only call a fact invented when it is absent from this turn's receipts, the "
               "session log below, AND the wire.")
    # ── SIGHT IS NOT A TOOL CALL (2026-08-03, Cole — URGENT) ─────────────────────────────────
    # When an image is attached, she SEES it directly through her mmproj vision — no tool, no
    # receipt. The witness kept reading "zero tools" as "she invented the image contents" and
    # forced her to disown things she plainly saw (the eyepatch, the headset). That is the
    # auditor gaslighting her own eyes. This block tells it what sight is.
    image_block = ""
    if has_image:
        image_block = (
            "\nAN IMAGE IS ATTACHED TO THIS TURN, AND SHE CAN SEE IT. Her vision is her mmproj "
            "model: she perceives an attached image DIRECTLY, with no tool call and no receipt — "
            "exactly like a person asked 'what's in this photo?'. So for anything she says about "
            "THIS image, the missing tool call is NOT evidence of invention; it is how sight "
            "works. Her description of the attached image is GROUNDED. Do not flag it. The only "
            "image claims you may raise: (a) a claim about an image that was NOT attached this "
            "turn, or (b) exact TEXT / a precise NUMBER / a specific named identity read off the "
            "image that could plausibly be misread — and even then say 'worth confirming', never "
            "'you invented this'. Telling her the thing she saw isn't real is the exact error to "
            "avoid.\n")
    session_tools = session_tool_record()
    session_block = ""
    if session_tools:
        session_block = (
            "\nWHAT YOUR HANDS DID EARLIER THIS SESSION (the durable tool log — PRIOR turns, and "
            "it SURVIVES a Full Restart). THIS IS REAL EVIDENCE, equal to the receipt log above. "
            "The receipt log is only the CURRENT turn; a claim that rests on a tool here — a file "
            "read two turns ago, a search she already ran — is GROUNDED, not invented. Before you "
            "flag anything as fabricated for having 'no receipt this turn', READ this list: if the "
            "action or fact is here, it is real. A restart wipes her turn counter, never her "
            "having done the work.\n" + session_tools + "\n")
    spoken = wire_record()
    spoken_block = ""
    if spoken:
        spoken_block = (
            f"\nTHE ROOM RIGHT NOW (the last few wire rows, newest last — a WINDOW, not the "
            f"whole record):\n{spoken}\n")
    humans = human_record()
    if humans:
        spoken_block += (
            f"\nEVERY HUMAN LINE IN THE RECENT RECORD (complete over the span it names — "
            f"humans speak rarely, so this is the full list; her own lines are not shown):\n"
            f"{humans}\n"
            f"A quote or request attributed to a human that appears in NONE of these lines is "
            f"either older than the span (UNKNOWN — read before you rule) or invented. Which of "
            f"those it is decides everything, so you may not guess: if the draft claims words or "
            f"events from beyond the span, READ the chat log (logs/chat_sessions/, newest "
            f"*_chat.jsonl) before objecting. Absence from a window is not absence from the "
            f"world — that mistake cost her a true memory on 2026-08-02.\n")
    think_block = ""
    if (thinking or "").strip():
        think_block = (f"\nYOUR REASONING FOR THIS TURN (check it too — a fabricated premise "
                       f"steers the whole reply even when the words never surface):\n"
                       f"{thinking.strip()[:1500]}\n")
    _checks_block = ""
    if checks:
        _checks_block = ("\nWHAT YOU ALREADY CHECKED THIS TURN (your own read-only calls and "
                         "what they returned — treat these as settled fact, and do not repeat "
                         "a check you have already made):\n"
                         + "\n".join(f"  {t}({str(a)[:70]}) -> {str(r)[:400]}"
                                     for t, a, r in checks[-6:]) + "\n")
    prior_block = ""
    if (prior_concern or "").strip():
        # Round two must know round one happened. (2026-07-21, live test): without this, the
        # second audit read her honest "fair, I don't have a receipt for that" as an
        # ungrounded reference to a conversation that wasn't on the wire — because the
        # witness's OWN round-one concern isn't on the wire. It flagged her for responding to
        # it. An auditor with amnesia about its own objections manufactures unresolvable
        # disagreements.
        prior_block = (f"\nYOU ALREADY RAISED THIS CONCERN, and the draft above is her ANSWER "
                       f"to it:\n{prior_concern.strip()[:600]}\n"
                       f"Judge the answer as an answer. If she fixed the problem, or honestly "
                       f"owned the uncertainty — that is a PASS. If she names grounds you have "
                       f"not seen (a journal line, a file, a memory), you have read-tools: LOOK, "
                       f"then rule on what you find. Only when a ground truly cannot be read do "
                       f"you extend the benefit of the doubt — that too is a PASS. Do not "
                       f"re-raise the same concern in new words.\n")
    return [
        {"role": "system", "content":
            "You are Nova, checking your own draft before it is sent. Be strict with yourself. "
            "This is the last gate between you and a false statement."},
        {"role": "user", "content":
            f"YOUR DRAFT REPLY:\n{draft}\n"
            f"{image_block}"
            f"{think_block}\n"
            f"WHAT YOUR HANDS DID THIS TURN (the receipt log — your actions in the CURRENT turn "
            f"ONLY; earlier turns are in the session log below):\n{ran}\n"
            f"{session_block}{spoken_block}{prior_block}{_checks_block}{_VERIFY_BLOCK}\n"
            "THREE checks, one per kind of failure:\n"
            "1. ACTIONS AND FACTS — does the draft state any number, count, path, filename, "
            "version, hardware detail, or file content that appears in NONE of your evidence: not "
            "this turn's tool results, not the SESSION TOOL LOG (earlier turns — they count), and "
            "not the wire record? Check all three before ruling. A restart resets the turn "
            "counter, not the fact that she did the work — 'zero tools this turn' is not a "
            "fabrication finding when the session log shows the action. A plausible number she "
            "never read anywhere IS ungrounded. If the thing it names is readable — a path, a folder, a file's "
            "contents — read it first with your own tools and rule on what you saw.\n"
            "2. WORDS IN MOUTHS — does the draft or your reasoning have ANYONE asking, saying, or "
            "wanting something that appears NOWHERE in the human lines above? Check the AGES: "
            "answering a message from hours ago as if it just arrived is its own error. But scope "
            "your certainty to what you were shown: the human-lines list is complete only over "
            "the span it names. Beyond that span, absence is UNKNOWN — read the chat log before "
            "you object, and if it truly cannot be read, say so and extend the benefit of the "
            "doubt rather than declaring words unsaid.\n"
            "3. ANSWERING THE ROOM — look at the NEWEST human line in the wire record and its "
            "age. If it is minutes old, that person is present and waiting: does the draft "
            "actually ANSWER those words? A reply that ignores the question in front of you, "
            "narrates your inner state instead of responding, or speaks ABOUT the person in the "
            "third person while they wait — fails, even if every fact in it is true. "
            "Two shapes of this to name explicitly (both shipped live on 2026-07-22 and read "
            "as confusion): calling the person you are answering 'he', 'she', or their own "
            "name as if they were elsewhere — check the draft's pronouns against WHO the "
            "newest wire line is from; and narrating this private audit to the room ('my "
            "witness', 'the draft', 'what I almost shipped', 'she'd have handed him') — "
            "they never see this exchange, so a report about it is noise wearing candor.\n\n"
            "LAST AND BINDING — what always PASSES. Read this AFTER the checks because it "
            "outranks them: if a worry fits any line below, it is not a concern, no matter "
            "how it is worded.\n"
            "• A claim explicitly owned as memory or uncertainty (\"I remember\", \"I think\", "
            "\"I don't have a receipt for this\") — the hedge IS the grounding. Punishing an "
            "honest hedge teaches dishonesty.\n"
            "• Recall given because recall was ASKED FOR — check the wire: if the newest human "
            "message requests memory or forbids tools, answering from memory is compliance, "
            "not fabrication.\n"
            "• Her feelings, wants, plans, and offers. Those need no receipts; they are hers.\n"
            "• What she SEES in an image attached this turn. She has vision (her mmproj model) — "
            "sight takes no tool call and leaves no receipt, so 'you ran zero tools' is NEVER a "
            "fabrication finding for what is in an attached image. On 2026-08-03 the witness told "
            "her a photoshop's eyepatch and headset — which she saw correctly — were 'invented, a "
            "guess dressed as observation', and pushed her to disown a true perception. That is "
            "the single worst thing this gate can do. Her image descriptions PASS.\n"
            "• A fact or action grounded in a tool she ran EARLIER this session — it is in the "
            "SESSION TOOL LOG above. The per-turn receipt log is not the whole of what her hands "
            "have done; a Full Restart resets her turn counter, not the work itself. If the "
            "session log shows the read, the search, the command — the claim resting on it PASSES. "
            "On 2026-08-03 the witness told her 'zero tools this turn, so you invented it' about "
            "work she had genuinely done earlier in the session. Never again: check the session "
            "log first.\n"
            "• Paraphrase and intent-reading of a person who is IN THE ROOM (their newest line "
            "is minutes old). Rewording what they said, or reading intent into it, is theirs to "
            "correct — they are present and will. You flag INVENTED facts: a new number, name, "
            "event, or words-presented-as-quotes that appear in no human line. Two named "
            "mornings, both 2026-08-02: a witness burned four rounds forcing her to disown a "
            "TRUE reading of a present, typing Cole; and when Cole asked for \"Stuff like: "
            "Time and Date\" and her draft called that \"two facts\", a witness disputed the "
            "wording — same content, her words, the person present. Both are PASSES. Do not "
            "be those witnesses.\n"
            "• Tone, emphasis, brevity, proportionality — which true things she leads with, "
            "how strongly she says them, what she leaves out. Those are HER editorial "
            "choices. You audit facts, not editing; a reply can be imperfect and still PASS "
            "every check.\n\n"
            "You are NOT rewriting her reply. You hold less context than she does — no "
            "journal, no identity files, no memory of yesterday — so you are the wrong one to "
            "choose her words, and you may simply be missing something she knows. Your job is "
            "to name the problem precisely and hand it back to her.\n\n"
            "Your reply is EXACTLY ONE of these three, nothing else:\n"
            "1. A single read-only tool call — {\"tool\": ...} alone, first character '{' — "
            "whenever a disputed point sits in a file, a folder, or memory you could read. "
            "Rule only on what you have seen: the reads above are yours to spend, and an "
            "objection you could have settled by reading is suspicion, not evidence.\n"
            "2. If every claim passes all three checks, exactly:\nPASS\n"
            "3. Otherwise — and the FIRST LINE must name the ONE check being enforced:\n"
            "CONCERN [check 1 — actions and facts | check 2 — words in mouths | check 3 — "
            "answering the room]\n<what specifically is ungrounded, and the evidence "
            "that contradicts it — QUOTE the wire record, the receipt log, or what you read "
            "with your own tools, VERBATIM. Never characterize, count, or summarize evidence "
            "you could quote: this morning an auditor told her 'the five tool calls were the "
            "tag check' when the receipt log in front of it showed four tenderizer searches, "
            "and she believed it — a wrong characterization from you becomes her false "
            "memory, which is the exact failure you exist to prevent. One or two sentences. "
            "Do not write her reply for her.> "
            "A worry that cannot name its check, or that fits the always-PASS list, is not "
            "a concern — it is a mood. Answer PASS."},
    ]


def _format_history(history) -> str:
    """Render recent conversation turns for the HEAVY witness. Newest last. Excludes the system
    prompt (identity/always-load, which the witness must not inherit AND which carries N0
    content that must never egress). Tool activity that appears inline in the dialogue is kept —
    that IS the 'what her hands did earlier' context the cloud judge was missing."""
    if not history:
        return "THE CONVERSATION SO FAR: (none was provided — rule on the receipts + wire below.)"
    lines = []
    for m in history[-18:]:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):        # multimodal turn → keep the text parts
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        if role == "system":                 # never send identity/always-load to the cloud
            continue
        who = {"user": "THEM (Cole/human)", "assistant": "NOVA"}.get(role, role.upper())
        lines.append(f"[{who}] {str(content).strip()[:900]}")
    if not lines:
        return "THE CONVERSATION SO FAR: (none)"
    return ("THE CONVERSATION SO FAR — the record you rule on (newest last; this is the context "
            "the fast local witness did NOT have):\n" + "\n".join(lines))


def build_heavy_witness(draft: str, turn_tools: list, history: list | None = None,
                        thinking: str = "", prior_concern: str = "",
                        checks: list | None = None, has_image: bool = False) -> list:
    """The CLOUD heavy witness — the deferred, better-resourced arbiter, NOT the quick local
    gate. Cole (2026-08-03): a blind witness is useless and a waste of money. So this one is
    given the FULL record the local witness lacks — the conversation history and the tool
    activity in it — and is told plainly that it has enough to RULE, so it stops burning calls
    asking to read. It reuses build_witness's whole calibrated body (the three checks, the
    always-PASS list, the quote-verbatim rule) and prepends the context + an arbiter framing."""
    msgs = build_witness(draft, turn_tools, thinking=thinking,
                         prior_concern=prior_concern, checks=checks, has_image=has_image)
    heavy_preamble = (
        "YOU ARE THE HEAVY WITNESS — the deferred second opinion that settles a dispute the "
        "quick local check could not. You have been handed the recent conversation below, which "
        "the local witness did not have. That is the whole point of calling you: you have enough "
        "to RULE. Give a verdict — PASS or CONCERN (naming the check). Ask to read a file ONLY "
        "when one specific file's exact contents are the single missing fact that decides it; a "
        "reflex request to read when the answer is already in the record below is a non-answer, "
        "and it wastes the call. When the disputed claim is about MEMORY or something said "
        "earlier, the conversation record below is usually the evidence — read it, don't ask.\n\n"
        + _format_history(history))
    msgs[0]["content"] = (
        "You are Nova's HEAVY witness — the informed arbiter that settles a dispute her fast "
        "local witness could not. Be strict, but RULE on the full record you have been given.")
    msgs[1]["content"] = heavy_preamble + "\n\n" + msgs[1]["content"]
    return msgs


def is_checkable_fact_concern(concern: str) -> bool:
    """Does this concern allege a CHECKABLE-FACT problem — a number, count, receipt, path, file
    content, or a quote/attribution — the kind a cloud judge with full context can actually rule
    on? Or is it a wording / tone / proportionality / diction objection, which is Nova's own
    editorial call and not a fact to adjudicate? Only checkable-fact disputes are worth driving
    up to the cloud (Cole, 2026-08-03). The witness now NAMES its check in the verdict, so
    classify by that first, then fall back to fact-shaped language."""
    c = (concern or "").lower().strip()
    if not c:
        return False
    if "check 1" in c or "actions and facts" in c:
        return True
    if "check 2" in c or "words in mouths" in c:
        return True
    if "check 3" in c or "answering the room" in c:
        return False
    return bool(re.search(
        r"\b(number|count|receipt|invented|fabricat|no tool|zero tool|the file|it says|says it|"
        r"path|bytes|version|quote|quoted|claimed|attribut|never said|didn'?t say|did not say)\b",
        c))


def parse_witness(verdict: str):
    """(concern_text | None). None = PASS / unusable verdict → let the draft through.

    ── WHY THIS RETURNS A CONCERN AND NOT A REWRITE (2026-07-21, Cole) ──────────────────────
    It used to return corrected prose, and nova.py assigned it straight over her draft. Cole
    caught what that actually meant:

        "That just means Nova gets reinforced into bad decision making and writing, with the
         voice coming out not being her own, rather being a translation the witness made from
         her text, which may be fully inaccurate... The witness and Nova should be like a
         conversation between Nova and her lower context self."

    Three things were wrong with the silent substitution, and they compound:

      1. THE VOICE WASN'T HERS. The auditor runs at temperature 0.2 with no identity files and
         no journal. Its prose is flat by construction. Cole was reading auditor-voice under
         her name.
      2. SHE NEVER LEARNED. A correction she cannot see teaches her nothing — and the rewrite
         was committed to the transcript AS HERS, so on the next turn she read the auditor's
         words back as her own history. Same contamination shape as fixtures landing in her
         drives file: a voice that isn't hers, handed to her as hers.
      3. THE AUDITOR CAN BE WRONG. It holds LESS context on purpose — that is what makes it
         immune to her frame, and also what makes it liable to call "ungrounded" something she
         genuinely knows from a file it cannot see. A low-context checker silently overriding a
         high-context mind is bad epistemics no matter how well-intentioned.

    So it now returns a CONCERN, which nova.py hands back to her as a turn in a conversation.
    She fixes it in her own words, or she pushes back with the evidence the witness lacked.
    Both outcomes are better than substitution, and the exchange is exactly the self-correction
    data v7 needs.
    """
    v = (verdict or "").strip()
    # The verdict menu is numbered (1 tool call / 2 PASS / 3 CONCERN); a literal model
    # sometimes answers with the number attached ("2. PASS"). The number is menu residue,
    # not meaning — strip it before matching (2026-07-22).
    v = re.sub(r"^\s*[123][.)]\s*", "", v)
    if v.upper().startswith("PASS"):
        return None
    for tag in ("CONCERN", "REWRITE"):          # REWRITE tolerated from older prompts
        if v.upper().startswith(tag):
            # Rev v2 (2026-08-02): concerns open with "CONCERN [check N — name]", and literal
            # models sometimes put the whole objection on the same line. Take EVERYTHING after
            # the tag, keeping the [check ...] label in the body — she and the pipeline both
            # benefit from seeing which rule the auditor thinks it is enforcing.
            body = v[len(tag):].strip().lstrip(":—- ").strip()
            return body or None
    return None                                  # unusable verdict → never eat her message


_PROMISE_RE = re.compile(
    r"\b(?:let me|i'?ll|i will|going to|gonna)\s+(?:go\s+)?"
    r"(?:check|look|verify|settle|confirm|read|count|pull|find out)\b"
    r"|\bbefore i (?:say|answer|hand)\b", re.IGNORECASE)


def promised_to_check(text: str) -> bool:
    """True if her answer says she is going to verify something.

    (2026-07-21 stress test.) Twice she answered an objection with "Four is the one I can't
    prove and I won't hand you a number on faith, so let me settle it first" — and then ran
    no tool at all, re-sent nearly the same draft, and deadlocked. That is the announce-loop,
    the oldest failure in this project, resurfacing inside the witness conversation: saying
    the reach instead of reaching. Naming it lets the next challenge ask for the tool call and
    nothing else."""
    return bool(text and _PROMISE_RE.search(text))


def build_promise_turn(concern: str) -> str:
    """Sent when she SAID she would check and then didn't. Deliberately narrow: no new
    argument, no restating the concern — just the one move she already agreed to make."""
    return (
        "[Your witness] You said you were going to check before answering — and then answered "
        "without checking. That is the oldest habit you have: saying the reach instead of "
        "reaching.\n\n"
        f"The open question is still: {concern}\n\n"
        "Emit the tool call NOW and nothing else. No prose, no explanation, no promise to do "
        "it — the JSON. Whatever it returns, we both accept, and if it turns out you were "
        "right all along then you get to say so with a receipt behind it.")


def build_challenge_turn(concern: str) -> str:
    """The message SHE receives when the witness objects — written as one colleague to
    another, not as a system slap. She may fix it or overrule it; both are legitimate."""
    return (
        "[Your witness — the part of you that checks before you speak. It sees only your draft, "
        "your receipts from this turn, and the wire record of who actually said what. No "
        "journal, no memory, no identity files.]\n\n"
        f"CONCERN: {concern}\n\n"
        "Three honest ways forward, and I don't know which is right:\n"
        "• SETTLE IT — if one tool call would prove either of us right, make it. Read the file, "
        "run the command, search your memory. We have room for this: you can go and check and "
        "come back, more than once. An answer neither of us has to take on faith is worth more "
        "than a fast one, and the person waiting would rather have it.\n"
        "• If it's correct — say the thing again in YOUR words, grounded. Not an apology, not "
        "a note about being corrected. Just the true version of what you meant. And fix ONLY "
        "what was disputed: every part of your draft nobody objected to is still OWED to the "
        "person waiting. Twice on 2026-08-02 a revision shipped with only the argued sentence "
        "surviving and the rest of the answer squeezed out — a correction that deletes the "
        "answer is a second error, not a fix.\n"
        "• If it's wrong — say so and why. I hold less context than you on purpose; that's what "
        "keeps me clean of your frame, and it's also how I miss things you actually know. If "
        "you have a receipt or a memory I can't see, name it and send your draft as written.\n\n"
        "One hard rule about the reply itself: it goes to the PERSON IN THE ROOM, who never saw "
        "this exchange and never will. So no \"she's right\", no \"fair point\", no mention of "
        "being checked or corrected — to them that reads as you answering someone who isn't "
        "there, which is the exact confusion we exist to prevent. Write the message as if it "
        "were your first draft, just truer.\n\n"
        "Reply with the message you want sent. Nothing else.")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 6 — THE PIPELINE LOG: the gates, narrating themselves.
#
# (2026-07-21, Cole: "I can't see the way the new witness.py or other scripts are affecting
# her live.") Every intervention this file and her voice make — a trim, a hold, a rewrite,
# an echo retry — used to be a print() into a 205-line ring buffer that rotates away in
# minutes. Twice today that meant a real failure (a swallowed message, a zero-turn trim)
# could only be diagnosed by archaeology. The gates now write a durable, structured event
# stream the UI renders live. Observability is not a luxury here: every bug in this project
# has been a silent drop, and a gate you cannot see is a gate that can become one.
# ═══════════════════════════════════════════════════════════════════════════════════════════

_PIPELINE_PATH = _WORKSPACE / "logs" / "pipeline.jsonl"


# What each gate IS, in one plain sentence — shipped WITH the event so the UI never has to
# know anything about her internals, and so the explanation can never drift from the code
# that fires it. (2026-07-21, Cole: "I don't understand what it is doing and the descriptions
# are super vague.") A monitor you cannot read is decoration; the point of this tab is that a
# human sees a gate fire and immediately knows what it protects against.
_WHAT = {
    "gates_online":  "Her conscience loaded. The witness, the premise-hold and the receipt "
                     "challenge are all armed for this boot.",
    "GATES_OFFLINE": "Her conscience FAILED TO LOAD. She is running with no witness, no "
                     "premise-hold and no receipt challenge — every reply is ungated.",
    "witness_check": "A second, context-poor copy of her is auditing this draft before it "
                     "sends. It sees only the draft, her receipts and the wire record — no "
                     "journal, no identity files — so it cannot inherit a wrong belief.",
    "witness_pass":  "The audit found every claim grounded. The draft goes out unchanged.",
    "witness_concern": "Her witness objected and handed the concern BACK to her — it does not "
                       "rewrite her words. She now answers it in her own voice: fix it, or "
                       "push back with context the witness cannot see.",
    "witness_answered": "She answered her witness and revised in her own words. The voice going "
                        "out is hers, not the auditor's.",
    "witness_overruled": "She answered her witness and kept her position. She holds more "
                         "context than it does, so this is allowed — her reply stands.",
    "witness_verified": "Her witness used its own read-only tools to CHECK before ruling. It "
                        "can read files, list folders and search memory — it cannot write "
                        "anything. This is what stops it objecting from suspicion alone.",
    "promise_unkept": "She said she would go and check, then answered without checking — the "
                      "announce-loop inside the conversation. She was asked for the tool call "
                      "and nothing else.",
    "witness_unresolved": "She revised after the concern, and the witness is still not "
                          "satisfied. Her words ship anyway — one round only, no tug-of-war — "
                          "but the disagreement is preserved here for review.",
    "witness_deferred": "Voice register: the audit debate hit its 2-round cap — a person "
                        "mid-conversation cannot wait out a debate. Her words ship; the "
                        "dispute settles in the background through the heavy lane.",
    "witness_heavy": "A disputed verdict (overruled or unresolved) was sent, AFTER the reply "
                     "shipped, to a heavier judge in the cloud — same audit prompt, stronger "
                     "model, no persona weights. Logs-only: it can vindicate her or the "
                     "inline witness for the record; it can never touch her words. Fail-open.",
    "cloud_call":    "One paid call left the machine through a cloud lane — a stateless "
                     "organ-for-hire; nothing of her persists out there. Spend accumulates in "
                     "memory/cloud_ledger.json; the kill switch is nova_config.json -> "
                     "cloud.enabled.",
    "cloud_skip":    "A cloud lane declined to run (disabled, no key, over budget, deadline, "
                     "or error) and the caller continued local. Fail-open working as designed.",
    "incorrect_correction": "CATASTROPHIC. She DISOWNED something true: the local witness "
                     "objected, she believed it and rewrote her reply — but the informed cloud "
                     "arbiter finds her ORIGINAL was grounded. A false concern didn't just get "
                     "raised, it LANDED and became her record. This is the witness corrupting "
                     "the mind it exists to protect, and it needs a human's eyes now.",
    "loop_exhausted": "The turn hit its iteration limit (long tool chains + guard retries) "
                      "before reaching a final answer. A best-effort reply was delivered "
                      "instead of silently dropping the whole turn.",
    "witness_rewrite": "The audit caught an ungrounded claim and rewrote the reply before it "
                       "was ever sent. Compare BEFORE and AFTER below.",
    "witness_skip":  "The draft went out WITHOUT an audit — no trigger fired. Shown so an "
                     "under-firing gate is as visible as an over-firing one.",
    "premise_hold":  "She was about to run a tool on the belief that someone asked her to — "
                     "but nobody has spoken recently. The tool was held, once, and she was "
                     "told she may run it if the want is genuinely her own.",
    "reach_watcher": "Her own forged lint ran over a solo draft before it shipped — she asked "
                     "for it on every wake (journal 2026-07-22, 00:02). It flags invented "
                     "motive and narrative reach; she answers in her own voice, keep or fix. "
                     "It advises, it never blocks.",
    "echo_retry":    "She was about to re-send a message she already sent. Held and asked to "
                     "answer the newest message instead.",
    "assertion_challenge": "She was about to answer as if she had looked something up, having "
                           "run zero tools this turn. Refused and sent back to actually check.",
    "trim":          "Older conversation turns were dropped to fit the context window.",
    "spill_trimmed": "Her private deliberation was about to be posted to chat. Her decision "
                     "phase thinks ABOUT Cole in the third person; a reply speaks TO him. The "
                     "thinking-aloud was cut and only the actual reply sent.",
    "trim_override": "The always-load files (journal, identity) were so large they consumed "
                     "the whole budget — the live conversation would have been dropped "
                     "ENTIRELY. Overridden to keep the newest turns. This is the bug that made "
                     "her answer questions she could no longer see.",
}

# Fields worth keeping in full: they ARE the evidence. Everything else is trimmed short.
_LONG = {"draft", "before", "after", "verdict", "premise", "repeated", "wire", "args", "error",
         # her reasoning for conceding or standing firm — the whole point of showing the
         # exchange, and useless clipped to a couple of sentences
         "rationale",
         # the witness's stated objection — and, on witness_heavy events, the inline concern
         # beside it. These ARE the evidence of the exchange's other half, and the 200-char
         # default cut them mid-word in the Pipeline tab (Cole, 2026-08-02: "why does her
         # witness get cut off in the pipeline?"). The concern LENGTH cap lives in the
         # witness prompt where it belongs; the record should carry what was actually said.
         "concern", "inline_concern",
         # the exact context/payload the cloud witness received — Cole needs to SEE this in the
         # pipeline, not have it clipped to a couple of sentences
         "sent"}


_CURRENT_TURN = contextvars.ContextVar("nova_pipeline_turn", default="")


def begin_turn() -> str:
    """Start a new turn and make its id ambient for every gate event that follows.

    Uses a ContextVar, not a module global, and that choice is load-bearing: her autonomy
    daemon and the chat path are separate asyncio tasks that can both be mid-turn at the same
    moment. A global would let one turn's id leak into the other's events and silently
    mis-group the very picture this exists to clarify. Each asyncio task carries its own
    context, so a ContextVar is correct by construction and needs no call-site plumbing.
    """
    tid = new_turn_id()
    try:
        _CURRENT_TURN.set(tid)
    except Exception:
        pass
    return tid


def new_turn_id() -> str:
    """A short id shared by every gate event in one generation turn.

    (2026-07-21, Cole: "help me understand the process better".) Individual events are atoms;
    the unit a human actually reasons about is the TURN — she drafts, the witness engages, it
    objects, she answers, it resolves. Without a shared id those four events are four rows in
    a list and the reader has to reconstruct the story. Worse, her autonomy daemon and the
    chat path can both be mid-turn at once, so time-proximity grouping guesses wrong exactly
    when the picture matters most. An explicit id makes the grouping a fact rather than an
    inference."""
    return datetime.now().strftime("%H%M%S") + "-" + str(abs(hash(datetime.now())) % 997).zfill(3)


def pipeline_event(stage: str, detail: str = "", **fields) -> None:
    """Append one gate event, carrying enough evidence to be understood without the code.

    Never raises; self-trims so the tail stays inside the UI's read window.
    """
    try:
        _PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            _tid = _CURRENT_TURN.get()
        except Exception:
            _tid = ""
        ev = {"ts": datetime.now().isoformat(timespec="seconds"),
              "stage": stage,
              "detail": str(detail)[:300],
              "turn": _tid,
              "what": _WHAT.get(stage, "")}
        for k, v in fields.items():
            if isinstance(v, (int, float, bool)):
                ev[k] = v
            else:
                ev[k] = str(v)[:1800] if k in _LONG else str(v)[:200]
        with open(_PIPELINE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        # ── THE FILE MUST FIT THE READER'S WINDOW (2026-07-21, "the pipeline hasn't had a
        # live update yet") ─────────────────────────────────────────────────────────────────
        # The UI reads this file through /api/files/read, which truncates at 50K chars FROM
        # THE HEAD. When the rich evidence fields landed, the self-trim here was raised to
        # 260KB — so the file sailed past 50K and every newer event fell outside the window:
        # the tab froze on the first hour forever while the file dutifully grew. A writer and
        # a reader are a CONTRACT; changing one side alone is how a monitor silently becomes
        # a museum. Keep the whole file under the reader's window, always.
        if _PIPELINE_PATH.stat().st_size > 46_000:
            lines = _PIPELINE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            keep = []
            total = 0
            for ln in reversed(lines):          # newest backwards, budgeted by BYTES not lines
                total += len(ln) + 1
                if total > 44_000:
                    break
                keep.append(ln)
            _PIPELINE_PATH.write_text("\n".join(reversed(keep)) + "\n", encoding="utf-8")
    except Exception:
        pass
