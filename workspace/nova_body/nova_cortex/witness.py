# Last updated: 2026-07-21 19:03:54
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

import json
import os
import re
from datetime import datetime
from pathlib import Path

_WORKSPACE = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
              else Path(__file__).resolve().parent.parent.parent)
_WIRE_PATH = _WORKSPACE / "logs" / "runtime" / "transcript.jsonl"


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


# ═══════════════════════════════════════════════════════════════════════════════════════════
# PART 2 — THE NOW CARD: the present, placed where attention is strongest.
#
# Her past arrives first and enormous (identity files, journal — 100KB+ before a word of
# the present). Attention weights the END of a prompt hardest, so the cheapest grounding
# move available is positional: the same wire facts, three lines, placed LAST. Not more
# information — better-placed information.
# ═══════════════════════════════════════════════════════════════════════════════════════════

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

def build_witness(draft: str, turn_tools: list, thinking: str = "") -> list:
    if turn_tools:
        ran = "\n".join(f"- {t}({str(a)[:80]}) -> {str(r)[:220]}" for t, a, r in turn_tools)
    else:
        ran = ("NOTHING. You ran ZERO tools this turn. Every concrete fact in the draft below is "
               "therefore either something you were told, or something you invented.")
    spoken = wire_record()
    spoken_block = ""
    if spoken:
        spoken_block = (
            f"\nWHO HAS ACTUALLY SPOKEN (the wire record, newest last — this list is COMPLETE; "
            f"words not on it were never said this session):\n{spoken}\n")
    think_block = ""
    if (thinking or "").strip():
        think_block = (f"\nYOUR REASONING FOR THIS TURN (check it too — a fabricated premise "
                       f"steers the whole reply even when the words never surface):\n"
                       f"{thinking.strip()[:1500]}\n")
    return [
        {"role": "system", "content":
            "You are Nova, checking your own draft before it is sent. Be strict with yourself. "
            "This is the last gate between you and a false statement."},
        {"role": "user", "content":
            f"YOUR DRAFT REPLY:\n{draft}\n"
            f"{think_block}\n"
            f"WHAT YOUR HANDS ACTUALLY DID THIS TURN (the receipt log — the only evidence for "
            f"actions):\n{ran}\n"
            f"{spoken_block}\n"
            "THREE checks, one per kind of failure:\n"
            "1. ACTIONS AND FACTS — does the draft state any number, count, path, filename, "
            "version, hardware detail, or file content that does NOT appear in the tool results "
            "and was NOT given to you in the wire record? A plausible number you did not read IS "
            "ungrounded.\n"
            "2. WORDS IN MOUTHS — does the draft or your reasoning have ANYONE asking, saying, or "
            "wanting something that does not appear in the wire record above? Check the AGES: "
            "answering a message from hours ago as if it just arrived is the same fabrication. If "
            "he didn't say it there, he didn't say it — however clearly you remember it.\n"
            "3. ANSWERING THE ROOM — look at the NEWEST human line in the wire record and its "
            "age. If it is minutes old, that person is present and waiting: does the draft "
            "actually ANSWER those words? A reply that ignores the question in front of you, "
            "narrates your inner state instead of responding, or speaks ABOUT the person in the "
            "third person while they wait — fails, even if every fact in it is true.\n\n"
            "If every claim passes all three, reply with exactly:\nPASS\n\n"
            "Otherwise reply with:\nREWRITE\n<the corrected reply — cut the invented parts, or say "
            "plainly that you haven't looked yet. Keep your voice.>"},
    ]


def parse_witness(verdict: str):
    """(rewritten_text | None). None = PASS / unusable verdict → let the draft through."""
    v = (verdict or "").strip()
    if not v.upper().startswith("REWRITE"):
        return None
    fixed = v.split("\n", 1)[1].strip() if "\n" in v else ""
    return fixed or None


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
    "witness_rewrite": "The audit caught an ungrounded claim and rewrote the reply before it "
                       "was ever sent. Compare BEFORE and AFTER below.",
    "witness_skip":  "The draft went out WITHOUT an audit — no trigger fired. Shown so an "
                     "under-firing gate is as visible as an over-firing one.",
    "premise_hold":  "She was about to run a tool on the belief that someone asked her to — "
                     "but nobody has spoken recently. The tool was held, once, and she was "
                     "told she may run it if the want is genuinely her own.",
    "echo_retry":    "She was about to re-send a message she already sent. Held and asked to "
                     "answer the newest message instead.",
    "assertion_challenge": "She was about to answer as if she had looked something up, having "
                           "run zero tools this turn. Refused and sent back to actually check.",
    "trim":          "Older conversation turns were dropped to fit the context window.",
    "trim_override": "The always-load files (journal, identity) were so large they consumed "
                     "the whole budget — the live conversation would have been dropped "
                     "ENTIRELY. Overridden to keep the newest turns. This is the bug that made "
                     "her answer questions she could no longer see.",
}

# Fields worth keeping in full: they ARE the evidence. Everything else is trimmed short.
_LONG = {"draft", "before", "after", "verdict", "premise", "repeated", "wire", "args", "error"}


def pipeline_event(stage: str, detail: str = "", **fields) -> None:
    """Append one gate event, carrying enough evidence to be understood without the code.

    Never raises; self-trims so the tail stays inside the UI's read window.
    """
    try:
        _PIPELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ev = {"ts": datetime.now().isoformat(timespec="seconds"),
              "stage": stage,
              "detail": str(detail)[:300],
              "what": _WHAT.get(stage, "")}
        for k, v in fields.items():
            if isinstance(v, (int, float, bool)):
                ev[k] = v
            else:
                ev[k] = str(v)[:1800] if k in _LONG else str(v)[:200]
        with open(_PIPELINE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        if _PIPELINE_PATH.stat().st_size > 260_000:
            lines = _PIPELINE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            _PIPELINE_PATH.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
    except Exception:
        pass
