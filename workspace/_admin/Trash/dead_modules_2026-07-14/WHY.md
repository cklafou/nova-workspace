# Dead modules in her body — 2026-07-14
_Last updated: 2026-07-14 23:03:28_

Zero importers. Verified by grep across the whole workspace.

- nova_motor/tool_executor.py   A SECOND, unwired tool executor. The live path is
                                general_tools/nova_chat/tool_router.py. Two executors, one wired.
- nova_memory/session_store.py  Unreferenced.

WHY THIS MATTERS MORE THAN TIDINESS:
Dead code in her BODY is worse than dead code anywhere else, because it LOOKS like a faculty.
"Does Nova have a tool executor in her body?" — yes, technically, and it does nothing. That
ambiguity cost real hours: I assumed a tool path existed that didn't.

If you build a limb, wire it or bin it. A scaffolded organ that was never connected is not a
half-finished feature — it is a lie about what she can do.

Still to reconcile (NOT removed, they are wired or ambiguous):
- nova_motor/verify.py — the name says "verifies results"; it is actually a pyautogui HARDWARE
  check. Misleading name on a live file. Rename it.
