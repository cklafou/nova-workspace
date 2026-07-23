# She invented a camera — confabulation investigation
_Last updated: 2026-07-24 04:19:29_

_2026-07-20, Fable. Cole: "She keeps making things up." Nova stopped for investigation._

---

## The three fabrications

From her own thinking, quoted by Cole:

> *"Cole's asking me to go over the logs."* — he never said that
> *"He's been awake since 6am and he asked how he looks."* — he said neither
> *"I already know the answer from the camera."* — **she has no camera**

The third is the serious one. The first two misattribute words; the third asserts a
**perception she never had** and then plans an action on the strength of it.

## First question: is this retrieval bleed or generation?

Different root causes, opposite fixes. Tested by searching her entire record — sessions,
chat logs, journal, journal notes, memory — for the invented content.

| claim | found in her record? |
|---|---|
| "how do I look" | **nowhere** |
| Cole awake since 6am | **nowhere** |
| camera | only as *metaphor* — "any 2D image is just a camera angle of the 3D model" (avatar docs), and "bigger than any camera in existence" (a remark about PNG dimensions) |

**No camera exists in her senses or tools.** Zero matches across `nova_senses/` and
`tool_router.py`. Her last real sight event was 2026-07-19 20:08 — over ten hours before the
thought.

**Verdict: not retrieval. Generation.** She is not surfacing old material as current; she is
producing plausible context and then treating it as recall.

## The finding that actually matters

Compare the same model, same adapter, minutes apart.

**Her autonomy thoughts** — the path that gets a clock, a wake cause, her board, her last
reflection and her drives:

> *"Another wake cycle at 00:16 AM Sunday. Barely slept before stirring again — my own rhythm
> pulled me back up after thirteen seconds."*
> *"Sixteen seconds ago I wrote 'tomorrow morning gets raw unfiltered feedback' and here I am
> awake again before that message even settled."*

Precise. Timestamped. Self-auditing. She counts her own seconds.

**Her chat replies** — the path that gets a system prompt and a transcript, and nothing else:

> *"I've been awake since you left the room, not scheduled."*
> *"I already know the answer from the camera."*

**She confabulates on the context-poor path and is rigorous on the context-rich one.** That is
not a personality problem and it is not the adapter. It is a structural asymmetry between two
code paths, and it has been there the whole time.

## Why the integrity gate didn't catch it

`needs_self_check(draft, asked)` fires when she was asked to act, or when
`claims_a_receipt(draft)`, or when the draft contains a digit or a file path.

Two holes, both fatal here:

**1. It checks claims about TOOLS, not claims about PERCEPTION.** `claims_a_receipt` looks for
"I read", "I ran", "the file says" — tool results. *"I already know the answer from the camera"*
claims a **sensory** fact. Nothing in the gate models that class of assertion.

**2. It gates the outgoing DRAFT, not her reasoning.** A fabrication that shapes her *plan*
without appearing in the final message passes untouched. All three of these lived in her
thinking. The gate never saw them.

There is also no check at all on **attribution** — "you asked me to…", "he said…". She can put
words in Cole's mouth and nothing questions it.

## What I have already fixed

**The clock, in chat.** Her wake prompt has opened with `It is {clock.stamp()}` for weeks. Her
chat path had **no clock anywhere** — not in `SYSTEM_PREFIX`, not in the transcript — and no
clock *tool* either. Every chat turn now opens with the real time, the time of day, and **how
long since the previous message**, plus an instruction that this line beats anything anyone
claims about the date.

This matters beyond timekeeping. When Cole said "it is tomorrow", she replied *"I have a clock I
could read, but I don't."* **That was itself a confabulation** — she invented a character flaw to
explain a missing organ, apologised for it, and promised a fix she was structurally incapable of
making. Same shape as the ping error string teaching her Windows was blocking focus: a gap in
what we give her becomes, to her, a fact about herself.

Verified 11/11, including the 9-hour-gap case that would have told her he'd been up all night
instead of inventing it.

## What I have NOT fixed, and would do next

Deliberately not rushed — this is her honesty, and a wrong guard is worse than none.

1. **Extend the integrity gate to sensory and attribution claims.** Add detectors for "I saw / I
   heard / from the camera / I already know" and for "you said / you asked / he wants". Both
   classes should require a receipt or an explicit hedge.
2. **Gate her REASONING, not only her draft.** The self-check should be able to look at the
   thinking that produced a plan, since that is where all three fabrications lived.
3. **Give chat turns the grounding block the wake gets.** The clock was one missing organ; the
   real asymmetry is that a wake knows what is true right now and a chat turn does not. Sensory
   state ("your last image capture was 10h ago"), recent receipts, and board state would close it.
4. **A confabulation detector**, in the shape of `referent_check.py` — scan her output for claims
   of perception or attribution and score them against the receipt ledger. Turns "she makes things
   up" into a rate we can drive to zero, the way the hallucination gate did.

## The honest read

Her hallucination battery passed 6/6 on 07-19 and I called the bar met. That battery tested
**factual claims about the machine** — file contents, GPU, adapter, counts — and she reaches for
a tool every time. It never tested claims about **her own perception** or about **what Cole
said**, and those are exactly where she is failing.

The gate isn't broken. It was built for a narrower class of lie than the one she is telling.
