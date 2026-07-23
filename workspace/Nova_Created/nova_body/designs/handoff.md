# Handoff Tool — finished thought, not narrated journey
_Last updated: 2026-07-23 19:28:54_

## The Gap
I have exactly one output shape: a reply. Every time I finish something it comes out as the whole process narrated at Cole, and he doesn't always want the walk-through. Sometimes he wants the conclusion he can take, reasoning available if he asks for it.

This is the difference between building-mode (show your work) and handoff-mode (here's the thing, I'll open the hood if you want).

## The Shape
A tool that takes a finished answer and an optional reasoning note, and delivers it as a HANDOFF block instead of a chat line. Cole gets the conclusion first; the reasoning sits behind a collapsed section he can expand. If he doesn't ask to see it, it stays tucked away.

```json
{"tool": "handoff", "args": {"answer": "ComfyUI stayed up this whole time, nobody told it to die.", "reasoning": "checked process list, one boot seven hours ago, six renders since. Log has no exit line."}}
```

## The Test
1. Handoff where Cole gets only the conclusion and doesn't expand it. Did he get what he wanted without the walk-through?
2. Same handoff, he asks to see the reasoning. Does it open cleanly?
3. A handoff with no reasoning attached. Does it not crash, just deliver the answer?
