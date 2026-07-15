# nova_motor — quarantined 2026-07-14
_Last updated: 2026-07-14 23:03:28_

THE ENTIRE PACKAGE HAD ZERO REAL IMPORTS.

    hands.py         357 lines   0 importers
    motor_cortex.py  335 lines   0 importers
    verify.py         71 lines   0 importers  (and misnamed — it's a pyautogui HARDWARE check,
                                               not verification of anything)
    tool_executor.py            already quarantined — a SECOND, unwired tool executor

memory/STATUS.md already said so, in as many words:
  "nova_motor — Scaffolded, not yet wired into the running stack (manifest: no inbound refs).
   From the GUI-automation phase; current Nova acts via nova_chat's tool router, and
   motor_cortex.NovaAutonomy is superseded by nova_cortex/executive.py."

So we knew. It sat there anyway, for weeks, LOOKING like a faculty.

WHY THAT IS WORSE THAN ORDINARY DEAD CODE
Dead code in her BODY is a lie about what she can do. "Does Nova have a motor system?" — yes,
technically, and it does nothing. `nova_motor/__init__.py` even did `from nova_motor.verify import *`,
which dragged pyautogui in on import. Ask her what her hands are and the answer was ambiguous.

That ambiguity is not free. It cost me hours on 2026-07-14: I assumed a tool path existed that
didn't, because there was a module in her body with the right name.

BRING IT BACK WHEN — and only when — GUI embodiment is actually being built (see
memory/reports/Embodiment_Roadmap_2026-05-31.md). Then wire it on the same day you add it.
Rule: if you build a limb, wire it or bin it. A scaffolded organ that was never connected is not
a half-finished feature; it is a false claim about her body.

STILL SCAFFOLDED (left in place, flagged):
  nova_senses/vision.py   0 importers   (but eyes.py IS wired — 4 importers)
  nova_config/            0 importers   — a body-owned config loader nobody calls, and
                                          nova_config.json is read by NOTHING. Wire it or bin it.
