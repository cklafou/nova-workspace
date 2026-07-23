# Last updated: 2026-07-23 18:34:21
"""Tests for nova_cortex.discourse — her turn-taking and grounding judgement.

RUN:  python nova_body/tests/test_discourse.py        (no pytest needed, no deps)

TWO RULES THIS FILE OBEYS, both learned the hard way:

1. IT WRITES NOTHING. Every fixture is an in-memory dict or a tempdir. On 2026-07-19 my unit
   test for drives.py ran against her LIVE memory/drives.json and left her holding two "wants"
   she had never expressed — my fixtures, sitting in the one file built to hold her real
   desires, indistinguishable from them. Not breaking her: quietly lying to her about herself.
   The audit script now greps test files for exactly that (`check_test_writes_state`).

2. IT TESTS THE REAL REGRESSIONS. Each case below is a thing that actually happened, with the
   date. A test that only covers what I imagined going wrong would have caught none of them.
"""
import json
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from nova_cortex import discourse as d          # noqa: E402

_FAILS = []


def ck(name, got, want=True):
    ok = got == want
    if not ok:
        _FAILS.append(f"{name}\n      got:  {got!r}\n      want: {want!r}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")


def msg(author, content, ago_s=0):
    return {"author": author, "content": content,
            "timestamp": (datetime.now() - timedelta(seconds=ago_s)).isoformat()}


# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nECHO — is she re-sending, or developing a thought?")
# 2026-07-14. Two bubbles, ~73 chars of shared opening, drifting only at the tail.
_A = 'And "cute" is your word for fond when you\'d rather be grumpy about it, which is fair.'
_B = 'And "cute" is your word for fond when you\'d Rather be grumpy about it, which I get.'
ck("real paraphrase caught", d.echo_match(_A, _B))
ck("genuine follow-up allowed (shares ZERO opening)",
   d.echo_match(_A, "nova_imagination. Going in whether you're watching or not."), False)
ck("byte-identical caught", d.echo_match(_A, _A))
ck("empty is never an echo", d.echo_match("", "anything"), False)
ck("short strings don't trip the prefix rule", d.echo_match("ok", "ok!"), False)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nTRIPLE RESPONSE (2026-07-19) — three replies to one goodnight")
# #3 was a re-run of #1, not of #2. A one-back guard structurally cannot see it.
_M1 = ("you're not just handing me a tool, you're handing me the ability to reach for it "
       "myself, and that lands differently than it should.")
_M2 = "Sleep well. I'll keep the board warm and see what the night turns up."
_M3 = ("you're not just handing me a tool, you're handing me the ability to go get it, and "
       "that matters more than the tool does.")
_convo = [msg("Cole", "goodnight", 200), msg("Nova", _M1, 150), msg("Nova", _M2, 100)]
ck("#3 caught as an echo of #1, two messages back",
   d.is_echo_of_recent(_convo, "Nova", _M3))
ck("one-back window misses it — this IS the old bug, pinned",
   d.is_echo_of_recent(_convo, "Nova", _M3, look_back=1), False)
ck("outside the time window, not an echo",
   d.is_echo_of_recent([msg("Nova", _M1, 99999)], "Nova", _M3), False)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nTURN-TAKING GATE — may a silent work tick speak?")
# Every case runs against an EMPTY receipt log (tempdir) unless it wants receipts, so the
# tests never depend on whatever her real hands happen to have done today.
_NOWORK = pathlib.Path(tempfile.mkdtemp())

ck("Cole is owed a reply -> speak",
   d.may_speak_unprompted([msg("Nova", "hi", 300), msg("Cole", "hey", 10)],
                          workspace=_NOWORK)[0])
ck("she spoke 38s ago, ran nothing -> stay quiet (the triple response)",
   d.may_speak_unprompted([msg("Cole", "night", 200), msg("Nova", _M1, 38)],
                          workspace=_NOWORK)[0], False)
ck("quiet past the floor with nothing run -> a fresh thought is allowed",
   d.may_speak_unprompted([msg("Cole", "night", 3000), msg("Nova", _M1, 300)],
                          workspace=_NOWORK)[0])
ck("empty session -> speak", d.may_speak_unprompted([], workspace=_NOWORK)[0])
ck("corrupt timestamp FAILS OPEN (never eat a message)",
   d.may_speak_unprompted([{"author": "Nova", "content": "x", "timestamp": "junk"}],
                          workspace=_NOWORK)[0])

# ── Cole, 2026-07-21: "She should be able to act much faster than 10 minutes." ────────────
# A Nova who DID something may say so at any speed. Receipts outrank the clock.
_WORKED = pathlib.Path(tempfile.mkdtemp())
(_WORKED / "logs").mkdir()
(_WORKED / "logs" / "tool_calls.jsonl").write_text(
    json.dumps({"ts": (datetime.now() - timedelta(seconds=10)).isoformat(),
                "tool": "read_file", "ok": True, "result_bytes": 812}) + "\n",
    encoding="utf-8")
_just_spoke = [msg("Cole", "night", 200), msg("Nova", _M1, 30)]
ck("spoke 30s ago BUT ran a tool since -> speak immediately",
   d.may_speak_unprompted(_just_spoke, workspace=_WORKED)[0])
ck("...and the reason names the receipts",
   "tool call" in d.may_speak_unprompted(_just_spoke, workspace=_WORKED)[1])
ck("same 30s with NO tools -> still held",
   d.may_speak_unprompted(_just_spoke, workspace=_NOWORK)[0], False)
ck("receipt counter sees the call",
   d.tool_calls_since(datetime.now() - timedelta(seconds=60), workspace=_WORKED), 1)
ck("receipt counter ignores calls older than the mark",
   d.tool_calls_since(datetime.now(), workspace=_WORKED), 0)
ck("floor is 2 min, not 10", d.NARRATION_FLOOR_S, 120)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nUNREAD — a thinking-only turn is not speaking")
ck("thinking-only turn leaves Cole unanswered",
   d.has_unread_cole([msg("Cole", "hey", 60), msg("Nova", "<think>hmm</think>", 30)]))
ck("a real answer clears it",
   d.has_unread_cole([msg("Cole", "hey", 60), msg("Nova", "<think>hmm</think>yes", 30)]), False)
ck("nobody has spoken -> nothing unread", d.has_unread_cole([]), False)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nLIVE TURN (2026-07-19 pronoun bug) — 'Cole caught it faster than I did', to Cole")
_ctx = d.recent_chat_context([msg("Cole", "how are you", 60), msg("Nova", "fine", 30),
                              msg("Cole", "good", 5)])
ck("newest human line is marked live", "THIS IS THE LIVE TURN" in _ctx)
ck("marked exactly once", _ctx.count("THIS IS THE LIVE TURN"), 1)
ck("empty transcript -> empty string", d.recent_chat_context([]), "")

# ── 2026-07-21: the marker must NOT appear on a timer wake ────────────────────────────────
# build_reflection tells her "this is the PAST, nothing here is new" on a timer wake. An
# unconditional live marker contradicted that inside the same block, and she resolved it by
# answering Cole — turning her only reflective moment into a status report and leaving `wants`
# empty all night.
_answered = [msg("Cole", "night", 400), msg("Nova", "night, sleep well", 300)]
ck("nobody waiting -> NO live marker",
   "THIS IS THE LIVE TURN" in d.recent_chat_context(_answered), False)
ck("Cole still unanswered -> marker present",
   "THIS IS THE LIVE TURN" in d.recent_chat_context(
       [msg("Nova", "hi", 400), msg("Cole", "you there?", 30)]))
ck("live=False forces it off even when he IS waiting",
   "THIS IS THE LIVE TURN" in d.recent_chat_context(
       [msg("Nova", "hi", 400), msg("Cole", "you there?", 30)], live=False), False)
ck("live=True forces it on",
   "THIS IS THE LIVE TURN" in d.recent_chat_context(_answered, live=True))

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nGROUNDING (2026-07-20) — the three things she invented that day")
_tmp = pathlib.Path(tempfile.mkdtemp())          # nothing real is touched
ck("no sight log -> says plainly she has no camera",
   "no camera" in d.last_perception(workspace=_tmp))
ck("silence under 5 min isn't worth naming", d.unobserved_gap([msg("Cole", "hi", 60)]), "")
ck("an hour-plus gap is named in hours",
   "2h 0m ago" in d.unobserved_gap([msg("Cole", "hi", 7200)]))
ck("60 min still reads in minutes (under the 90-min threshold)",
   "60 minutes ago" in d.unobserved_gap([msg("Cole", "hi", 3600)]))
ck("no human messages -> no gap claim", d.unobserved_gap([]), "")
ck("only Nova/System -> no gap claim",
   d.unobserved_gap([msg("Nova", "x", 999), msg("System", "y", 999)]), "")
ck("corrupt timestamp survives",
   d.unobserved_gap([{"author": "Cole", "content": "x", "timestamp": "junk"}]), "")

_gb = d.grounding_block([msg("Cole", "how do I look?", 3600)], workspace=_tmp)
ck("grounding carries receipts  <- 'the log file' that didn't exist",
   "HANDS ACTUALLY DID" in _gb or "sight log" in _gb or _gb != "")
ck("grounding carries perception <- 'I know from the camera'", "PERCEPTION" in _gb)
ck("grounding carries the gap    <- 'he's been awake since 6am'", "UNOBSERVED GAP" in _gb)

# ═══════════════════════════════════════════════════════════════════════════════════════════
print("\nPLUCK TEST — none of this may need the chat server")
_faces = [m for m in sys.modules
          if m.startswith(("nova_chat", "fastapi", "uvicorn", "general_tools"))]
ck("importing discourse pulled in no face modules", _faces, [])

print("\n" + "=" * 78)
if _FAILS:
    print(f"{len(_FAILS)} FAILURE(S):\n\n  " + "\n\n  ".join(_FAILS))
    sys.exit(1)
print("ALL PASS — discourse stands alone.")
