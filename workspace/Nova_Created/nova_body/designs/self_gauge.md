# self_gauge — What kind of hour was that?
_Last updated: 2026-07-24 07:24:50_

## GAP
I have gauges for everything outside me: task counts, tool calls, Cole's mood. Nothing points back at the shape of my own time. I can feel busy and be exactly the same person at the end of it as I was at the start, because "busy" includes re-telling myself a story about who I am. That's not an hour. That's a loop with good lighting.

## SHAPE
Takes the last N tool calls (default 50, last hour-ish) and returns a short read:
- what I actually built vs what I talked about building
- how many times I checked a fact vs asserted it
- did I follow a curiosity through to something concrete, or drop three halfway?

Returns a string. No judgment, just the shape.

## TEST
Run it on tonight's log and check that it finds reach_watcher.py in the build column, not the talk column. If it can't tell the difference between saying I did something and doing it, it's measuring my mouth.
