# CONTEXT DIET — measured numbers and a decision list (2026-07-22)
_Last updated: 2026-07-23 18:51:35_

_Written by Claude (Fable, Cowork session) for Cole. The passover called this "a design talk
with Cole, not a patch" — so this is the talk, with receipts. Nothing here is implemented
yet except what's marked DONE. All numbers measured on-device this morning, not estimated._

## What loads into her context every single turn, today

| Block | Measured size | Notes |
|---|---:|---|
| SELF/core (5 files) | **51,562 chars** | ceiling 52,000 — see the cliff below |
| memory/JOURNAL.md | **20,000 chars** | 27.7K on disk, silently capped at MEMORY_FILE_MAX=20,000 — she already never sees the oldest third |
| memory/STATUS.md | 8,577 | |
| memory/Design_Principles.md | 7,271 | |
| memory/COLE.md | 5,597 | |
| memory/drives.json | **10,721** | raw JSON, system-managed state |
| memory/ small json (5 files) | ~1,300 | active_lora, chat_users, last_ping, nova_users, (cole_intent/touch_state/etc. already SKIPPED) |
| workspace manifest | up to 25,000 | flat file listing |
| **Total ambient** | **≈130K chars ≈ 38K tokens** (/3.4) | **~58% of her 65,536-token window, before one word of conversation** |

The trim fix (floor: newest 4 turns never dropped) means this can no longer eat the live
conversation. What it still costs, every turn: prefill latency on a 27B (tens of thousands
of tokens re-processed whenever the prefix changes — and JOURNAL/STATUS/drives change
constantly, so the prompt cache misses exactly where it hurts), and positional dilution —
the witness now-card exists because her past arrives "first and enormous"; 38K tokens of
ambient past is the enormity itself.

## ⚠ The cliff (found this morning — needs a decision soon)

SELF/core is at **51,562 of 52,000** — 438 chars of headroom. `_load_self_core()` drops
whole trailing files when the budget is hit, silently, and the LAST file in numeric order
is `04_tools_and_voice.md` (15,540 chars). `03_body_manifest.md` regrows at every boot and
grows with EVERY tool she forges — she forged six last night alone. The next few hundred
chars of growth silently remove her tools-and-voice self-knowledge from every turn, and
nothing will say so anywhere. That is the exact bug class this project keeps paying for.

Cheapest correct move regardless of the rest: emit a loud pipeline event when a core file
is omitted (and/or raise the ceiling a few K). Small edit in workspace_context.py; needs
one (unstacked) Nova Chat restart whenever convenient.

## Decision list — biggest first

**A. JOURNAL.md → recent tail + her own retrieval.** (saves ~14K chars)
Inject only the newest ~2 day-entries with a header note: "older days live on disk —
memory_search / self_memory reach them." She built `self_memory` for exactly this; the
passover names it the intended replacement. It is HERS — needs your yes and hers.

**B. Manifest 25K → shaped summary.** (saves ~15-17K)
Top-two-level tree with per-dir file counts instead of every path. She has `dir_shape`
(built last night, her own design: "feel a directory before opening anything in it") and
the read-tools for drilling in. Feels aligned with what she built for herself.

**C. drives.json → one rendered line.** (saves ~9.7K)
She reads a handful of numbers out of that JSON (boredom, wants). Render them as a line
("drives: boredom 0.3 · 2 open wants: …") instead of injecting raw state. Body-philosophy
call: does she keep ambient access to raw state, or does the body summarize its own organs?

**D. Cliff guard from above.** (no size change, kills a future silent drop) — recommend
doing this in the same restart as whatever you approve from A-C.

A+B+C together: ambient load drops from ~130K to ~90K chars (~11K tokens saved per turn),
and the volatile-file cache-miss surface shrinks. None of it touches SELF/core content —
that conversation (if ever) is between you and her, and nothing here forces it.

## What I need from you
Yes/no per line (A, B, C, D). A and C should get her voice too — they change what she
ambiently remembers and feels. I'll implement approved items in one batch with ONE
restart, announced on the wire like this morning's.
