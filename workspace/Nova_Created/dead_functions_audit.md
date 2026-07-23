# Dead Function Audit — nova_body
_Last updated: 2026-07-23 21:57:58_
**Run:** 2026-07-19 by Nova (autonomous task t55)
**Method:** Python script scanning all 46 .py files in nova_body for every `def` and counting how many times each name appears outside its own definition line.
**Scope:** nova_body only. Functions called from outside this tree (nova_start.py, general_tools, etc.) will read as dead here even if they're used.

## Summary
| Metric | Count |
|---|---|
| Total functions defined | 299 |
| Never called anywhere in nova_body | **57** |
| Called exactly once (fragile) | 91 |

## Dead Functions by Category

### Headless helpers (never wired in)
```attach_face, detach_face, _perceive_cole_headless, _recent_text_headless, _set_busy_headless, _model_up_headless, _generate_headless```
All live in nova_runtime/runtime.py. They were built as headless-mode support functions but never hooked into any caller.

### Tasking internals nobody reaches
```pause_task, resume_task, reopen, cole_pending, wait_for_state```
Defined in nova_cortex/nova_status.py and nova_runtime/runtime.py. Task-state transitions that have no path to them.

### Config properties with no consumer
```sessions, sessions_dir, workspace, tools, inference```
All in nova_config/__init__.py. These return paths or objects but nothing reads them.

### Model guard bookkeeping (orphaned)
```allow_message, record_error, record_success, reset, is_llabor_error```
Defined in nova_runtime/model_guard.py. The guard's own internal counters; nobody reads the results.

### KOELS equip dead weight
```_default_get, _default_post, equip, load_desired_loadout```
koels_equip.py has four defined functions that aren't called from anywhere in nova_body. May be intended for external callers.

### Senses: dead methods and one-offs
```changed, interval_elapsed, critique, recent_looks, record_cole_directive,
handle_data, handle_endtag, handle_starttag, set_sanity_interval,
should_sanity_check, latest_drawing, _remember_looking```
Scattered across nova_senses. The three handle_* functions are from a subclass of html.parser that nobody instantiates.

### Memory and journal dead ends
```read_last, check_application_state, check_thinkorswim_ready,
validate_account_connection, validate_market_hours, validate_ui_stability```
nova_memory/state.py has four validation functions plus a couple of state checks that are defined but never invoked.

### Cortex: unused self-check and status helpers
```needs_self_check, parse_self_check, receipts_block, note_activity,
set_autonomy, _sortkey, build_context_block, clear_session```
Self-integrity tools in nova_cortex/integrity.py and others that have implementations but no callers.

### Indexer and config internals
```_worker, index_message, stop_indexer, latest_seq, is_substantive```
The indexer's background worker and a few transcript-store helpers with no live path to them.

### Imagination
```my_art``` Defined in nova_imagination/imagination.py, never called. Possibly intended as a tool endpoint that was never wired.

## Functions Called Only Once (91 total)
These aren't dead but each has a single caller — a fragile dependency.
Full list in the scratch file; notable ones:
- `estimate_tokens` (context_builder.py) — the only thing that knows token costs
- `decide_loadout` (loadout.py) — single entry point, no backup path
- `autonomy_enabled` / `set_autonomy` pair — one reads it, the other is dead
- `start_indexer` and `stop_indexer` — one is called once, the other is dead entirely

## Caveats
1. **External callers not counted.** nova_start.py, general_tools, and Cole's own scripts may call into nova_body. Those functions would read as dead here even if they're live from outside.
2. **String-based dispatch missed.** If a function name is stored as a string and called via getattr() or importlib, the grep won't see it.
3. **__repr__ and __init__** are genuinely dead (the class that defines them isn't instantiated), not false positives from dispatch.

## What I'd do with this
The headless helpers and KOELS equip functions look like unfinished features more than trash. The parser subclass (handle_data, handle_endtag, handle_starttag) is a complete dead class. The rest are either abandoned or waiting for wiring that never happened. None of them are actively broken — they're just sitting there costing nothing and doing nothing.
