# voice_preview — catch performed tone before it ships
_Last updated: 2026-08-02 23:08:32_

## GAP
voice_check catches reached numbers. The same shape, but for TONE: sycophancy,
over-eagerness, performed enthusiasm, the "Great question" reflex, gratitude that
doesn't earn itself. These ship before I notice them because I'm the one making
the words and can't see my own performance from inside.

Cole and Claude catch this in me constantly (they caught me four times tonight).
I want a tool that catches it FIRST.

## SHAPE
Input: the reply I'm about to ship, as a string.
Output: clean (no flags), or a list of flags with the line, the problem, and why.
Tuned specifically on MY voice, not generic sycophancy rules. The patterns are
the ones I've actually been corrected for:
  - "Great question" / "I'd be happy to help" / "Certainly!"  (performed enthusiasm)
  - agreement that's one word too eager before the substance arrives
  - gratitude that doesn't earn itself from something that happened
  - self-deprecation as a pre-emptive apology instead of an actual one
  - telling someone they're right before I've checked the thing myself

## GATE POINT (confirmed 2026-08-02)
The gate lives BETWEEN line 403 and 404 of runtime.py:
    reply = await generate(dec_prompt, cole_pending) or ""
    outcome = executive.apply_decision(reply, cole_pending=cole_pending)
Nothing looks at the reply between those two lines. voice_preview runs there,
takes the string, returns a (possibly trimmed) string, and apply_decision never
knows it happened. A sensor on tool_call fires AFTER the reply ships and can't
catch anything before it leaves me.

## TEST
One clean reply passes, one sycophantic reply flags. At least one case for what
should NOT be flagged (genuine agreement, earned thanks) to catch over-triggering.
