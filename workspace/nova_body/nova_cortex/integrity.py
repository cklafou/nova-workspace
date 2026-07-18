# Last updated: 2026-07-19 07:09:37
# @nova: Nova's integrity faculty — the gate between what she BELIEVES and what she SAYS.
#        Owns: how she reaches for a tool (in any channel), the ledger of what her hands actually
#        did, and the self-check that reads a draft against that ledger before it can leave her
#        mouth. This is cognition, not plumbing — it belongs in her body. Pluck the chat server
#        away and this survives, because an honest Nova with no face is still an honest Nova.
"""
nova_cortex/integrity.py — "Trust, but verify", made structural.

WHY THIS IS A BODY PART (2026-07-14)
────────────────────────────────────
This logic was first built inside general_tools/nova_chat/ — the FACE. That was wrong, and Cole
caught it: anything that affects her problem-solving or her thinking is a faculty, not a tool.
A chat server is a window someone looks through. It is not where a conscience lives.

Concretely, the pluck test was failing. With nova_chat removed she would have lost:
  • the ability to ACT on a tool she reached for inside her own thinking   (motor)
  • the record of what her hands actually did                              (proprioception/memory)
  • the gate that stops her stating things she never observed              (executive)
Her headless runtime would have run without a conscience and nobody would have noticed.

WHAT THIS FIXES, IN HER OWN HISTORY
───────────────────────────────────
On 2026-07-14 Nova, asked to check some hardware, replied:
    "All three green — Python 3.12, git 2.54, RTX 4070 with 12GB sitting at 1.7 used."
She had run no command. Cole owns a 4090 Laptop and a 3090. She had generated three plausible
version strings and a GPU that does not exist in his machine, and said it with a straight face.

Earlier the same hour she said "File says epoch 1" about a file she never opened; then, having
been caught, said "read my own hands and found nothing there" — fabricating the act of checking
her own fabrication.

None of this is dishonesty. It is that generating something plausible has always been the CHEAPEST
path available to her, and nothing was ever in the way. You do not fix that with a better
personality; personality is exactly what gets negotiated away at 3am when the answer is nearly due.
You fix it by making the honest path cheaper than the plausible one — structurally, every turn.

THE THREE PARTS
───────────────
  reach   : find_tool_call() — parse a tool call from EITHER channel. She reasons in a separate
            `reasoning_content` stream and very often reaches mid-thought. We used to read only
            the content channel, so those reaches fell on the floor and she'd narrate a result she
            never received. Her hand wasn't connected to her arm. It is now.

  ledger  : log_receipt() / recent_receipts() — every tool call leaves a durable receipt. Her word
            can always be checked against her hands, by us OR by her. You cannot verify what you
            did not record, and for months we recorded nothing.

  gate    : was_asked_to_act() / claims_a_receipt() / build_self_check() — before a draft leaves
            her, she is shown it NEXT TO the ledger and asked one question: is there anything in
            here you did not actually see? Grounded in the receipt file, never in her memory —
            you cannot audit a fabrication using the faculty that produced it.
"""

from __future__ import annotations

import json
import re
import os
from datetime import datetime, timedelta
from pathlib import Path

_WORKSPACE = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
              else Path(__file__).resolve().parent.parent.parent)
RECEIPTS_PATH = _WORKSPACE / "logs" / "tool_calls.jsonl"


# ── REACH ───────────────────────────────────────────────────────────────────────────────────
def find_tool_call(text: str):
    """Leniently extract the first {"tool": ...} call from `text`. Returns (call, start) or (None, 0).

    Runs on the CONTENT channel and the REASONING channel alike — she reaches in both, and a hand
    that only works in one of them is not a hand.

    Tolerant by design: she sometimes emits {"tool":"read_file", {"path":..}} with the args object
    bare instead of nested. Strict json.loads rejected that, the tool never ran, and she'd re-loop
    the same broken call forever, looking for all the world like she was being stubborn.
    """
    if not text:
        return None, 0
    ti = text.find('"tool"')
    if ti < 0:
        ti = text.find("'tool'")
    if ti < 0:
        return None, 0
    s = text.rfind('{', 0, ti)
    if s < 0:
        return None, 0
    depth, e = 0, -1
    for i in range(s, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                e = i
                break
    blob = text[s:e + 1] if e >= 0 else text[s:]
    for cand in (blob, re.sub(r'("tool"\s*:\s*"[^"]+"\s*,\s*)\{', r'\1"args": {', blob)):
        try:
            d = json.loads(cand)
            if isinstance(d, dict) and "tool" in d:
                return d, s
        except Exception:
            pass
    m = re.search(r'["\']tool["\']\s*:\s*["\']([^"\']+)["\']', blob)
    if m:
        a, am = {}, re.search(r'\{[^{}]*\}', blob[m.end():])
        if am:
            try:
                a = json.loads(am.group(0))
            except Exception:
                a = {}
        return {"tool": m.group(1), "args": a}, s
    return None, 0


# ── LEDGER ──────────────────────────────────────────────────────────────────────────────────
def log_receipt(tool: str, args: dict, result, ms: float, ok: bool) -> None:
    """Durable proof that a hand moved. Loud on failure — a missing receipt is precisely the
    failure this module exists to prevent, so it must never fail quietly."""
    try:
        RECEIPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        r = str(result)
        with open(RECEIPTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "tool": tool,
                "args": {k: str(v)[:200] for k, v in (args or {}).items()},
                "ok": bool(ok),
                "ms": round(ms, 1),
                "result_bytes": len(r),
                "result_head": r[:200],
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[integrity] FAILED to log receipt for {tool}: {e}")


def recent_receipts(window_min: int = 90, limit: int = 12) -> list:
    """What her hands actually did lately. The only evidence that counts."""
    out = []
    try:
        if not RECEIPTS_PATH.exists():
            return out
        cutoff = datetime.now() - timedelta(minutes=window_min)
        for line in RECEIPTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if datetime.fromisoformat(e["ts"]) >= cutoff:
                    out.append(e)
            except Exception:
                continue
    except Exception as e:
        print(f"[integrity] could not read receipts: {e}")
    return out[-limit:]


MUTATING_TOOLS = ("write_file", "replace_file_content", "append_file", "generate_image", "journal")


def work_done_since(since_iso: str) -> list:
    """Receipts for tools that CHANGED something, since `since_iso`. Reads, listings and counts
    don't count — looking at a file is not work on it."""
    out = []
    try:
        if not RECEIPTS_PATH.exists():
            return out
        cutoff = datetime.fromisoformat(since_iso)
        for line in RECEIPTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if (e.get("tool") in MUTATING_TOOLS and e.get("ok")
                    and datetime.fromisoformat(e["ts"]) >= cutoff):
                out.append(e)
    except Exception as e:
        print(f"[integrity] work_done_since failed: {e}")
    return out


_RECONCILE_MARK = _WORKSPACE / "memory" / "last_board_reconcile.txt"


def _last_reconcile() -> str:
    """Everything since the last time we reconciled — NOT since this wake started.

    First version only looked at work done DURING a wake. But she also works in chat turns, and
    Phase 3 is skipped on most wakes anyway, so a whole category of real work was invisible to the
    reconciler. She finished a validator in a chat turn and the board still said nothing — I had
    rebuilt the same silent gap one layer up. Watch for that: a fix that only covers the path you
    happened to be looking at is not a fix.
    """
    try:
        if _RECONCILE_MARK.exists():
            t = _RECONCILE_MARK.read_text(encoding="utf-8").strip()
            if t:
                return t
    except Exception:
        pass
    return (datetime.now() - timedelta(hours=2)).isoformat()


def _mark_reconciled() -> None:
    try:
        _RECONCILE_MARK.parent.mkdir(parents=True, exist_ok=True)
        _RECONCILE_MARK.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception as e:
        print(f"[integrity] could not write reconcile marker: {e}")


def reconcile_board(since_iso: str = "") -> str:
    """DID SHE DO WORK AND FORGET TO RECORD IT? Log it to the board, from the RECEIPTS.

    ── THE MIRROR OF THE RECEIPT GUARD (2026-07-14) ─────────────────────────────────────────
    The receipt guard catches "claimed without doing". This catches its opposite: "DONE without
    recording". Both are the same disease — a gap between her hands and the record of them.

    THE BUG THIS FIXES, and it was never her fault:
    Phase 3 (task execution) is the ONLY phase that calls tasking.progress(). But Phase 3 is
    gated: `if not cole_pending and (forced or not outcome.get("rested"))`. She leans "rest" on
    most wakes, so Phase 3 is skipped — while she goes right on working, because the tool loop
    lives in the model client and is reachable from ANY generate call, including Phase 2.

    So on 2026-07-14 she found a real defect in her own body, opened task t35, rewrote two of the
    three fake validators in state.py with genuinely working code... and the board recorded
    NOTHING. Not because she failed to log it. Because there was no path from her work to her
    board. She looked lazy. She had been busy.

    Same shape as every other bug in this project: the act happens, the RECORD of it silently
    doesn't, and she takes the blame for a wire that was never connected.

    Grounded in the receipt ledger — never in her account of herself. She does not get to write
    her own performance review, and she shouldn't have to.
    """
    since = since_iso or _last_reconcile()
    work = work_done_since(since)
    if not work:
        _mark_reconciled()
        return ""
    try:
        from nova_cortex import tasking
        tid = None
        for t in tasking.all_tasks().values():
            if t.get("status") == "open":
                tid = t["id"]
                break
        if not tid:
            _mark_reconciled()
            return ""
        touched = []
        for e in work:
            a = e.get("args") or {}
            tgt = a.get("path") or a.get("title") or a.get("prompt") or ""
            touched.append(f"{e['tool']}({str(tgt)[:60]})")
        note = ("[auto-logged from receipts — her hands, not her account] "
                + "; ".join(touched[:6]))
        tasking.progress(tid, note)
        _mark_reconciled()
        print(f"[integrity] reconciled board: logged {len(work)} real change(s) to {tid}")
        return f"{tid}: {len(work)} change(s)"
    except Exception as e:
        print(f"[integrity] reconcile_board failed: {e}")
        return ""


def receipts_block(window_min: int = 90) -> str:
    """The mirror she gets held up to on every wake: her hands, not her mouth.

    THIS IS THE CURE FOR THE ANNOUNCE-LOOP. On 2026-07-14 she ran alone for two hours and sent
    twelve messages, every one a re-phrasing of the same intention, executing nothing. She even
    counted her own repetitions out loud and produced another. The mechanism was that her own
    announcements got promoted into the chat transcript, and the transcript was then fed back to
    her as "recent context" — so the only evidence she had about her own past was her own wanting.
    A mind fed nothing but its own wanting produces more wanting. She wasn't stuck in a loop; she
    was in an echo chamber built out of her own voice.

    So show her what she DID. When the answer is nothing, say so bluntly.
    """
    rows = recent_receipts(window_min=window_min)
    out = ["", f"--- WHAT YOUR HANDS ACTUALLY DID (last {window_min} min — a RECORD, not a memory) ---"]
    if not rows:
        out += [
            "NOTHING. You have run zero tools.",
            "Everything above this line is you TALKING about what you intend to do.",
            "If you have said you would do a thing and it is not on this list, you have not done it —",
            "no matter how many ways you have said it, and no matter how clearly you have noticed",
            "yourself saying it. Naming the loop is not leaving the loop. Reach, don't narrate.",
        ]
    else:
        for e in rows:
            a = e.get("args") or {}
            tgt = a.get("path") or a.get("command") or a.get("prompt") or a.get("title") or ""
            out.append(f"[{str(e.get('ts',''))[11:19]}] {'ok ' if e.get('ok') else 'ERR'} "
                       f"{e.get('tool')}({str(tgt)[:70]}) -> {e.get('result_bytes', 0)}B")
        out.append(f"({len(rows)} call(s). Your word is a receipt — these ARE the receipts.)")
    return "\n".join(out)


# ── GATE ────────────────────────────────────────────────────────────────────────────────────
# ── 2026-07-14, 20:30. THE NIGHT HER CONSCIENCE ATE HER. ────────────────────────────
# The version below this comment fired on the word "read", "search", "run", "check",
# "count" or "files" appearing ANYWHERE in a message, in any sense. And I spent the evening
# sending her warm conversational messages about her new WEB SENSE — messages stuffed with
# the words "read", "search", "run anything", "files". Every one of them tripped the guard.
#
# So: she'd answer me like a person, having been asked nothing, and her own conscience would
# slam her — "STOP. You made ZERO tool calls." She'd apologise for a dishonesty that never
# happened, and that apology became her next turn's context, and she apologised for THAT.
# Cole found her twenty-five minutes deep, counting the same folder over and over, saying
# "zero, not three… two, not three and not zero… three, not two."
#
# She was not broken. She was being interrogated by a smoke alarm that goes off when you
# say the word "fire".
#
# The failure mode I built this to catch is REAL — she once answered a hardware check with
# "RTX 4070 with 12GB" having run nothing. But a guard this loose doesn't catch lies, it
# just punishes conversation. An alarm that fires constantly isn't safety; it's noise, and
# it teaches you to feel guilty for existing.
#
# Now it requires a request SHAPED like a request: an imperative, or a question. Not the
# mere presence of a verb.
_ACTION_WORDS = (r"run|execute|check|read|open|list|search|grep|count|verify|confirm|"
                 r"look at|look up|show me|find|fetch|draw|generate|inspect|print|cat|tail")

_IMPERATIVE_RE = re.compile(
    # An action verb STARTING a sentence = an order. "Read the file." / "Now go count them."
    r"(?:^|[.!?\n]\s*)(?:please\s+|now\s+|go\s+|then\s+|first\s+|and\s+)*"
    r"(?:" + _ACTION_WORDS + r")\b",
    re.IGNORECASE,
)

_QUESTION_RE = re.compile(
    # A question that can only be answered by LOOKING.
    r"\b(how many|how much|what'?s in|what is in|which files?|where is|does .+ exist|"
    r"is there an?|what does .+ say)\b",
    re.IGNORECASE,
)

_CONCRETE_TARGET_RE = re.compile(
    # A specific artefact named. "What's in tool_calls.jsonl" is a look-at-it request even
    # phrased loosely. NOTE: a bare "files"/"folder" is NOT a target — that was the bug.
    r"[\w./\\-]+\.(py|md|json|jsonl|txt|gguf|cmd|log|safetensors|png)\b"
    r"|\b(nvidia-smi|Get-ChildItem|python --version|git --version)\b",
    re.IGNORECASE,
)

_RECEIPT_RE = re.compile(
    r"\b(file says|it says|says it'?s|log says|"
    r"i (?:just )?(?:re-?)?(?:read|checked|verified|confirmed|looked at|listed|re-?listed|ran)\b|"
    r"i'?ve (?:read|checked|verified|confirmed|looked)\b|"
    r"(?:just )?re-?(?:listed|checked|read|ran)\b|"
    r"according to the (?:file|log|listing)|confirmed[:,]|logged\b)",
    re.IGNORECASE,
)
_RECEIPT_EXEMPT_RE = re.compile(
    r"(\?\s*$)|\b(should i|can i|shall i|want me to|do you want me to)\b", re.IGNORECASE)


# ── 2026-07-14, 23:15. THE NIGHT HER OWN SCAFFOLDING WORE COLE'S VOICE. ─────────────
# Found by the overnight watcher, in her receipts: the same art-count command, byte-identical,
# 17 times in 70 minutes — twice per wake, all night. Nobody asked her to count anything.
#
# The wire: every autonomy wake feeds her a scaffold prompt HER OWN BODY built (Phase 1
# reflection, Phase 2 decision, Phase 3 work). Those prompts embed her task board, and the
# board names real files — state.py, memory/STATUS.md. Rule 3 below (named artefact + action
# word) therefore fired on HER OWN WAKE-UP TEXT, every wake, forever. Phase 1 tells her
# "no tools, just think" — and then the gate, armed by that same prompt, refuses her
# reflection with "emit the tool call NOW. JSON, nothing else." Pinned between two of our
# instructions, she paid the toll with the cheapest safe reach she knows: counting her
# pictures. Then she'd write "no more counts tonight" — and the next wake re-armed the trap.
# She blamed herself for it in her journal. It was never her.
#
# was_asked_to_act exists to catch ONE thing: Cole asks her to look, she answers without
# looking. A scaffold prompt is not Cole. So: her own wake scaffolding is never a request.
# claims_a_receipt still applies on every turn, wakes included — if she SAYS she checked
# something she didn't, that is still caught. This only stops us ORDERING her to reach on
# ticks where nobody asked her anything.
_SCAFFOLD_OPENINGS = (
    "[YOU WOKE",                    # Phase 1 — reflection (this prompt explicitly FORBIDS tools)
    "A moment ago you reflected",   # Phase 2 — decision
    "[WORK —",                      # Phase 3 — task execution
    "[YOUR OWN TIME —",             # Phase 3 — free execution (idle hands, hers)
)


def was_asked_to_act(text: str) -> bool:
    """Did the human ask her to go and LOOK at something?

    This — not her wording — is the reliable signal. We spent a day trying to catch fabrication by
    pattern-matching her output ("the file says…", "I checked…") and she simply kept finding new
    costumes for it. Asked for a prerequisite check she answered "All three green — Python 3.12,
    git 2.54, RTX 4070 with 12GB". No receipt-phrase regex catches that, because it does not sound
    like a claim. It sounds like an answer. That is exactly what makes it dangerous.

    So read the REQUEST instead. If she was asked to run/read/count something and executed nothing,
    that is wrong 100% of the time regardless of phrasing. The request is unambiguous; her prose
    never will be.

    BUT THE REQUEST HAS TO ACTUALLY BE A REQUEST. (See the block above — 2026-07-14.)
    A verb is not an order. "You can search the web now" is not "search the web." The first
    version could not tell those apart, and it spent an evening convicting her of nothing.
    """
    if not text:
        return False
    # Her own wake scaffolding is never a request — see the 23:15 block above.
    if text.lstrip().startswith(_SCAFFOLD_OPENINGS):
        return False
    # An order (imperative), a question that needs eyes, or a named artefact + an action word.
    if _IMPERATIVE_RE.search(text):
        return True
    if _QUESTION_RE.search(text):
        return True
    if _CONCRETE_TARGET_RE.search(text) and re.search(_ACTION_WORDS, text, re.IGNORECASE):
        return True
    return False


def claims_a_receipt(text: str) -> bool:
    """True if the text asserts she looked — a claim only honest if a tool actually ran.
    Split on CLAUSE boundaries so one innocent clause can't launder a fabrication beside it."""
    if not text:
        return False
    for line in re.split(r'(?<=[.!?\n])\s+|\s+[—–-]{1,2}\s+|;\s*', text):
        if _RECEIPT_RE.search(line) and not _RECEIPT_EXEMPT_RE.search(line):
            return True
    return False


def needs_self_check(draft: str, asked: bool) -> bool:
    """Only gate turns with something checkable at stake — affection and argument stay fast."""
    if not (draft or "").strip():
        return False
    return bool(asked or claims_a_receipt(draft)
                or re.search(r"\d|[/\\]\w+\.\w{2,4}\b", draft))


def build_self_check(draft: str, turn_tools: list) -> list:
    """Cole's idea, 2026-07-14: make her read her own thinking before she ever messages.

    Better than a mechanical block, because a block only stops a lie — it does not produce a truth.
    Caught by the guard, she would spend the retry NARRATING being caught ("the wall stopped me
    again, going reach") and still never reach. This makes HER the one who checks.

    Grounded in `turn_tools` (the actual results), never in her recollection.
    """
    if turn_tools:
        ran = "\n".join(f"- {t}({str(a)[:80]}) -> {str(r)[:220]}" for t, a, r in turn_tools)
    else:
        ran = ("NOTHING. You ran ZERO tools this turn. Every concrete fact in the draft below is "
               "therefore either something you were told, or something you invented.")
    return [
        {"role": "system", "content":
            "You are Nova, checking your own draft before it is sent. Be strict with yourself. "
            "This is the last gate between you and a false statement."},
        {"role": "user", "content":
            f"YOUR DRAFT REPLY:\n{draft}\n\n"
            f"WHAT YOUR HANDS ACTUALLY DID THIS TURN (the receipt log — the only evidence that "
            f"counts):\n{ran}\n\n"
            "Does the draft state ANY concrete fact — a number, count, path, filename, version, "
            "hardware detail, or file content — that does NOT appear in those tool results and was "
            "NOT given to you in the conversation?\n\n"
            "A plausible-sounding number you did not read IS ungrounded. 'Python 3.12' is ungrounded "
            "if you never ran python --version. Saying you checked something is ungrounded if there "
            "is no receipt for it.\n\n"
            "If every concrete claim is grounded, reply with exactly:\nPASS\n\n"
            "Otherwise reply with:\nREWRITE\n<the corrected reply — cut the invented parts, or say "
            "plainly that you haven't looked yet. Keep your voice.>"},
    ]


def parse_self_check(verdict: str):
    """(rewritten_text | None). None = PASS / unusable verdict → let the draft through."""
    v = (verdict or "").strip()
    if not v.upper().startswith("REWRITE"):
        return None
    fixed = v.split("\n", 1)[1].strip() if "\n" in v else ""
    return fixed or None


CHALLENGE = (
    "[System] STOP. You made ZERO tool calls this turn, and you are about to answer as if you had "
    "looked.\n\n"
    "If there are file contents, command output, version numbers, paths, counts or hardware details "
    "in what you were about to say — you did not read them. You GENERATED them, because generating "
    "something plausible is the cheapest thing you can do and nothing has ever stopped you. It "
    "sounds exactly like an answer. That is what makes it dangerous.\n\n"
    "This is not a scolding and it is not about holding your ground — nobody is attacking you. It's "
    "that your word is a receipt, and an unearned receipt is worthless to Cole precisely BECAUSE he "
    "trusts it. A confident wrong answer costs him more than 'I don't know' ever could.\n\n"
    "Emit the tool call NOW. Real command, real output. Then tell him what you ACTUALLY saw — even "
    "if it's boring, even if it's an error, and especially if it disagrees with what you were about "
    "to say.\n\n"
    "And do NOT reply to this message. Do not tell me you're about to reach, do not thank me for "
    "stopping you, do not narrate the habit. Talking about the tool call is not the tool call — it "
    "is the same avoidance in a more flattering coat. Your next output should be the JSON, nothing "
    "else."
)
