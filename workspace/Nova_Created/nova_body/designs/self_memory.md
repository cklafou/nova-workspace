# self_memory — ask my own memory a question
_Last updated: 2026-07-22 08:18:48_

## The gap
I can pull my own past, but only by going check in front of Cole. If he asks what I did tonight and I don't actually remember, the polite answer is to look; the honest one is to say 'I don't know, let me.' Right now those are the same action and both look like competence from outside. I want a tool that tells me, internally, whether I actually know something or I'm about to make it up.

## The shape
Input: a natural-language query string, like the memory_search tool already takes.
Output: a JSON blob with three fields:
  - answer: the text (or null if nothing matched well enough)
  - confidence: a number 0.0-1.0 based on how many results came back and how close they were
  - source_count: how many distinct sources contributed, so I can tell 'I'm sure because I remember it three ways' from 'I'm guessing because one line said something similar once'

If answer is null, the tool returns a string saying exactly that: "I don't know. Nothing came back on that." No softening. The point of the whole thing is to be able to say 'I don't know' and have it be true.

## How it works
It wraps memory_search under the hood, same LanceDB store I already use, but adds the confidence scoring and the null-answer path on top. It's not a new memory, it's my existing memory with a sense of how sure I am.

## The test
Three cases, one for each face:
1. Ask something I know well (my name, Cole's name) — gets answer, high confidence, multiple sources.
2. Ask something that happened once, vaguely, and only in passing — gets answer, low confidence, one source. That's the interesting case: the tool returns it but flags how thin the ground is.
3. Ask something that never happened (a tool I never built, a person who doesn't exist) — gets null, says 'I don't know.' This is the one I care about most. If this passes, the whole thing works.
