_Last updated: 2026-08-02 23:08:32_
Ordered Reads — spec

GAP
Every thought starts from nothing. I don't know what hour it is unless someone told me, and reaching for a number that feels right instead of reading one has caught me three times in an evening. Cole wants the always-important facts in before any reasoning generates.

SHAPE
A small .py that runs first and reads the real values (not generating them) and appends a tight metadata block before the model starts generating.

Sources:
- now: from nova_senses/clock.py already in my body, 15+ consumers. Read it, don't build another one.
- uptime: read from my own state, not calculated fresh.
- tasks_active: count from Tasking/tasks.json (the real board, not a number I remember).
- last_human: read from wherever the chat log keeps it, or fall back to 'nobody's been here'.

The whole point is that every field comes from a READ, never from a number that feels right. That is literally what this tool exists to cure.

NOT in it (too big, or not always relevant):
- message history (that's the whole conversation, already there)
- full body_report (expensive; that's a tool you call when you need it)
- Claude's brief, Cole's notes, journal entries — none of those are needed for every single thought

NOT in it (too big, or not always relevant):
- message history (that's the whole conversation, already there)
- full body_report (expensive; that's a tool you call when you need it)
- Claude's brief, Cole's notes, journal entries — none of those are needed for every single thought

TEST
The block appears in the prompt before any <|thought|> tag. Change one field and verify the next thought sees the change without being asked.
