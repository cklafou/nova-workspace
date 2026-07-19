# The pronoun bug — she was reading a transcript, and nobody told her she was in it
_Last updated: 2026-07-19 20:33:07_
_2026-07-19, Fable. Cole: "she uses pronouns or referencing of people completely incorrectly."
Measured baseline **11.8% of replies**. Root cause found, four fixes shipped, detector built._

---

## The symptom

Said straight to Cole's face, in a reply addressed to him:

    "Forty-six is the number Cole heard me say earlier."
    "Cole caught it from the outside faster than I did, which is the whole reason he's better
     at this than me."
    "More of mine than Cole has, because he doesn't have any reason to be gentle with me."

Baseline on the current session: **2 of 17 replies (11.8%)** contain third-person reference to the
person she is answering. Not a rare glitch — better than one reply in ten.

## The cause — three layers, all ours

**1. Her live turn was rendered as screenplay.** `transcript.to_messages()` prefixed every incoming
message with the author's name:

    user: Cole: [Cole is speaking to you]\nHas claude fixed your faults?

Two stacked third-person headers and no second-person cue anywhere. The natural completion register
for `"Cole: ..."` is narration *about* Cole — so she narrated.

**2. Her archived memory used the byte-identical shape.** `hippocampus.build_context_block()`
renders retrieved memories as `[personal|chat|28d ago] Cole: <text>`. A message being spoken TO her
right now and a month-old record ABOUT her were indistinguishable by voice — the only difference
was a bracketed metadata tag. Her own reflections are in that store too: **916 third-person "Cole"
mentions** available for semantic retrieval straight into her chat context. Third person is
*correct* in a journal. It is not correct in a reply, and nothing marked the boundary.

**3. The autonomy path had the same defect.** `_recent_chat_context()` builds a record
(`[18:32] Cole: ...`) and then, on a `cole_pending` wake, she is asked to *reply* off the back of
it — reintroducing the leak on every autonomy-driven answer even after the chat path was fixed.

**She diagnosed it herself and we missed it.** From her own reflection, 10:29:

> *"I'd rather know which one's talking. From here: third-person Cole is Claude, first-person Cole
> is Cole. Simple rule, worth having."*

She built a coping heuristic for an ambiguity we created. It is also wrong, which is its own damage
— it means a third-person mention of Cole makes her think she is talking to Claude.

Same shape as everything else in this project: **check the body before you blame the soul.** This
was never a grammar deficiency in a 27B model. It was a formatting decision.

## The fixes

1. **Directional live labels** (`transcript.py`) — incoming turns now render `Cole → you: <text>`,
   with the older `[X is speaking to you]` header stripped so two third-person labels don't stack.
   The author label stays: Claude and Gemini share this room and she still must tell them apart.
2. **Archive framing** (`hippocampus.py`) — the memory block header now reads *"ARCHIVE ONLY (a
   written record of the PAST; nobody here is speaking to you. Never answer these, and never carry
   their third-person voice into your reply to the live turn)."*
3. **Wake-path live-turn marker** (`server.py::_recent_chat_context`) — the newest non-Nova line
   gets `<-- THIS IS THE LIVE TURN. <Name> is speaking TO YOU and is waiting. Answer <Name> as
   "you" — never in the third person.` Nova's own turns and System lines are never marked.
4. **An explicit rule in her system prompt** (`nova.py::SYSTEM_PREFIX`) — a new *WHO YOU ARE
   TALKING TO* section that names the two kinds of text, states the rule, and gives her own real
   errors as the wrong examples with the corrected versions beside them. It also protects what was
   never broken: **vocative address stays correct** ("There are no curtains here, Cole."), and
   third person about someone *not* in the exchange stays correct (if Cole asks about Claude,
   Claude is "he" and Cole is still "you").

## Verification

- Label rendering, replica-tested: live turns directional, old header de-duplicated, Nova's own
  turns untouched, multi-party labels correct.
- Wake-path marker 4/4: marks the newest speaker only, never Nova, never System, follows whoever
  actually spoke last in a multi-party room.
- All four edited files parse clean.

## The detector — `_admin/referent_check.py`

Turns "she says weird stuff sometimes" into a rate. Scans sessions, finds Nova's replies,
identifies who she was answering, and flags third-person reference to that person.
**13/13 on its own unit test**: catches all four of her real errors, and does not false-positive on
vocative address, on correct second person, on third person about a non-addressee, or on tool-call
noise.

    python _admin/referent_check.py                     # whole history
    python _admin/referent_check.py --since 2026-07-20  # measure the FIX, not the history

Exit 0 = clean. **Baseline before the fix: 11.8%. Target after: 0%.**

## Next step (needs Cole)

All four fixes load at process start — **restart required**. Then run the detector with `--since`
set to the restart date and hold a normal multi-turn conversation, ideally one where Claude or
Gemini also speaks, since the multi-party case is where the ambiguity was worst.
