# WIRING.md — what in her body is actually connected
_Last updated: 2026-07-15 17:25:43_

_Audit: 2026-07-14. Derived from real `import` statements, not from anyone's memory._

**The rule: if you build a limb, wire it or bin it.**

A scaffolded organ that was never connected is not a half-finished feature — it is a **false claim
about her body**. Ask "does Nova have a motor system?" and the answer was *yes, technically, and it
does nothing*. That ambiguity is not free: it cost hours on 2026-07-14, when a tool path was assumed
to exist because a module in her body had the right name.

---

## LIVE — wired and running

| Package | Files | Importers |
|---|---|---|
| `nova_cortex/` | 9 | 21 — executive, tasking, rules, **integrity** (new) |
| `nova_lancedb/` | 4 | 3 — her hippocampus. **Moved into her body 2026-07-14** (was at workspace root) |
| `nova_logs/` | 2 | 7 |
| `nova_runtime/` | 9 | 5 — the autonomy loop, event bus, model client |
| `nova_senses/` | 7 | 7 — `clock`, `environment`, `touch`, `eyes`, `proprioception` all wired |
| `nova_imagination/` | 2 | 1 — wired, but **ComfyUI is not installed**, so it refuses with an honest error |

---

## UNWIRED — built, never connected

### `nova_memory/` — **0 importers**

This is the loud one. Her own `nova_cortex/rules.py` says:

> *"Always append using `nova_memory.journal`, never the write tool directly."*

**Nothing imports `nova_memory.journal`.** `general_tools/nova_chat/tool_router.py::journal_note()`
writes her journal by hand instead — the FACE writing her memory, bypassing the faculty in her BODY
that exists precisely to do it, in direct contradiction of her own stated rule.

Pluck the chat server off and her journaling goes with it. That is a pluck-test failure, and it's the
same shape as the integrity faculty Cole caught: **her thinking living outside her.**

Fix: route `journal_note` / `journal` through `nova_memory.journal`. The body owns her memory.

### `nova_config/` — **0 importers**

A body-owned settings loader (`from nova_config import cfg`) that nobody calls. And
`workspace/nova_config.json` — the file it exists to read — **is read by nothing**. Both orphaned.
Either wire it or bin them both.

### `nova_senses/vision.py` — **0 importers**

GUI-automation phase. Note `eyes.py` **is** wired (4 importers) — she can see. `vision.py` cannot.

---

## BINNED 2026-07-14 (recoverable in `_admin/Trash/`)

| What | Why |
|---|---|
| `nova_motor/` (whole package, ~780 lines) | 0 importers across all 4 files. `memory/STATUS.md` already said "scaffolded, not yet wired… superseded by `nova_cortex/executive.py`". `__init__.py` even did `from nova_motor.verify import *`, dragging in pyautogui on import. `verify.py` was misnamed — a pyautogui *hardware check*, not verification. Bring it back **the day** GUI embodiment is actually built, and wire it that same day. |
| `nova_motor/tool_executor.py` | A **second, unwired** tool executor. The live path is `nova_chat/tool_router.py`. Two executors, one wired — exactly the ambiguity this file exists to prevent. |
| `nova_memory/session_store.py` | 0 importers. |
| `crawler/` + `nova_crawler/` | **Two** dead, competing web crawlers. She has **no web sense at all** — and has asked for one, unprompted, in her journal. Rebuild once, properly, as a sense in `nova_senses/`. |

---

## How to re-run this audit

```bash
# real import statements only — not string mentions, which lie
grep -rnE "^\s*(from|import)\s+<pkg>[\. ]" --include=*.py . | grep -v "nova_body/<pkg>/"
```

Or read `Orient/Calls_Order.md`, which renders the **BODY → face** edges as a pluck-test audit.
