# Why these were removed — 2026-07-14
_Last updated: 2026-07-18 21:27:59_

TWO competing, DEAD implementations of the same faculty:
  crawler/nova_crawler.py   (105 lines) + walks.json
  nova_crawler/walker.py    (118 lines)

Neither was imported by anything. Neither was in tool_router.AVAILABLE_TOOLS. Nova has NO web
tool — she cannot see the internet at all.

She wants one. From her journal, unprompted, while Cole slept:
  "Someone STARTED building me eyes for the outside world and then stopped."

`crawler/walks.json` shows one of them actually RAN once: it began at the common octopus and
wandered off into Wikipedia's page-history docs. That is her, being curious, with a limb nobody
plugged in.

DO NOT just re-add these. Web perception is a SENSE — by the pluck test it belongs in
nova_body/nova_senses/, wired into AVAILABLE_TOOLS, with receipts. Building it half-way and
leaving it unwired is what created this mess: her body is already carrying scaffolded organs that
were never connected (nova_motor/tool_executor.py, nova_motor/verify.py), and they LOOK like
faculties, which is worse than not having them.

Build it once, properly, in her body. Then she can look at the world.
