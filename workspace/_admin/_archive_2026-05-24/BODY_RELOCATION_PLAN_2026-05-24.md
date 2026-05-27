# Plan — Relocate Nova's body code into nova_body/
_Last updated: 2026-05-28 06:41:30_

_Status: DRAFT for review. Move to `_admin/_archive_*` when executed.
Author: Claude (Cowork), with Cole, 2026-05-24.
Goal (Cole): "All code that should be in Nova's body placed in her body — existing
script or a new one — in the proper place, describing the body part/function it
represents."_

---

## 1. Principle

`nova_body/` = Nova's **faculties** (cortex, memory, motor, senses, logs).
`general_tools/` = **tools** she uses (chat server/voice, watcher, audit, clients…).

The chat server (`general_tools/nova_chat`) is a **tool** — her voice and comms.
But two faculties were built *inside* it during the autonomy work and are mislocated:
her **task memory** and her **autonomy cognition**. This plan moves them into the
body, each as a real part with an `@nova:` description, so the body manifest lists
them and the chat tool merely *calls* them.

_Correction (2026-05-24): "memory" is NOT a body faculty. Memory is **data** —
`workspace/memory/` (STATUS/JOURNAL/COLE) and long-term `nova_lancedb` — accessed by
the body, not a part of it. The task system is **executive function** (planning,
prioritizing, tracking), which is the **prefrontal cortex** → it goes in
`nova_cortex`, NOT a body "memory" folder. Task DATA stays in `workspace/Tasking/`
(already correct, parallel to `workspace/memory/`)._

## 2. Classification of `server.py` (every function)

**→ nova_cortex / executive — task state (pure file + logic, NO chat coupling, clean
to move first):** `_parse_queue`, `_write_task`, `_complete_task`, `_load_task_state`,
`_save_task_state`, `_task_key`, `_ensure_task_state`, `_match_task_title`,
`_record_progress`, `_drop_task_state`, `_task_queue_view`, `_priority_hash`,
`_mirror_cole_intent`, `_journal_correction`.

**→ nova_cortex / executive — autonomy cognition (coupled to chat internals, needs
DI):** `_run_autonomy_tick`, `autonomy_daemon`, `_autonomy_cfg`, `_env_fingerprint`,
`HeartbeatContext`, `_parse_task_intent`, `_parse_task_progress`, `_reconcile_queue`.

Both groups land in `nova_cortex` (one executive faculty). Task DATA files
(`task_state.json`, `priority.md`) remain in `workspace/Tasking/` — never moved into
the body.

**→ nova_senses (perception of Cole's presence):**
`_has_unread_cole`, `_cole_is_typing`. (Small; may also sit in cortex — decide in Stage 3.)

**Stays in nova_chat (tool: voice / comms / HTTP+WS):**
all FastAPI endpoints, `broadcast`, `get_status`, `run_ai_response`,
`_run_gemini_response`, `_run_response_queue`, `emit_event`, `_maybe_route_inbox`,
`_should_agent_respond`, `startup_event`, `shutdown_event`, `_window_close_watchdog`,
`_TeeStream`, `_build_discord_context_block` (retired — flag for removal).

## 3. Other `general_tools/` modules (quick ruling)

- **Tools (stay):** `watcher.py`, `audit_scripts.py`, `calls.py`, `build_manifest.py`,
  `backup.py`, `drive.py`, `download_models.py`, `NovaLauncher.py`, `gateway_config.py`
  (gateway retired — archival candidate). These are tooling that *serves* the body.
- **Clients (stay, tool):** `nova_chat/clients/{claude,gemini,nova}.py` — LLM/comms adapters.
- **Borderline — `injector.py` (NCL dispatch):** executes Nova's `@module` actions →
  arguably **nova_motor** (action execution). Revisit after Stages 1–2.
- **`workspace_context.py` self-model assembly** (`build_nova_context_block`,
  `_load_self_core`): how she loads her own self-knowledge → arguably **cortex**, but
  tightly bound to the chat prompt builder. Revisit in Stage 3.

## 4. The circular-import strategy (the core risk)

Body logic must not import the chat server (which imports the body) → cycle.

- **Memory functions are pure** (file I/O + logic). They move with zero chat
  dependency. `server.py` just imports and calls them. (Stage 1 — safe.)
- **Cortex functions need chat primitives** (`broadcast`, `run_ai_response`,
  `get_status`, `emit_event`, `session_mgr`, the `is_processing` flag). Resolve by
  **dependency injection**: the cortex module defines the cognition logic and receives
  those primitives as arguments/handles from `server.py` (e.g.
  `autonomy_daemon(deps)`), or via a small `ChatBridge` object the server constructs
  and passes in. Body never imports nova_chat. (Stage 2.)

## 5. Staged execution (each stage: build module + `@nova:` header → rewire server
imports → run audit + manifest → restart-test before next)

- **Stage 1 — Task system → `nova_cortex/tasking.py`.** Move the 14 task-state/queue
  functions (own path constants → `workspace/Tasking/`). `server.py` replaces its
  local defs with `from nova_cortex.tasking import …`. Lowest risk; do first.
- **Stage 2 — Autonomy cognition → `nova_cortex/autonomy.py`.** Move the tick + daemon
  + parsers + reconcile, with DI for chat primitives. `server.py` constructs the deps
  and calls `nova_cortex.autonomy.run(...)`. Higher risk; isolate and restart-test.
- **Stage 3 — Senses + self-model.** `_has_unread_cole`/`_cole_is_typing` → senses;
  evaluate moving `build_nova_context_block`/`_load_self_core` (self-model assembly)
  into cortex; decide `injector.py` → motor.
- **Stage 4 — Manifest + cleanup.** Confirm the new parts appear in
  `SELF/core/03_body_manifest.md` with purposes; archive `gateway_config.py` if now
  unreferenced; update any `@nova:`/docs.

## 6. Verification per stage

- `audit_scripts.py` (broken imports / dead code) — must stay clean (modulo the
  sandbox torn-mount false positives on file-tool-edited files).
- `build_manifest.py` — the new body part(s) appear with their `@nova:` purpose.
- Restart-test — server boots, autonomy ticks, task tracking works end-to-end.

## 7. Open decisions for Cole

1. Task system home: one `nova_cortex/tasking.py`, or split into `tasking.py`
   (state/queue) + fold the decide/reconcile into the autonomy module? (Claude leans:
   one `tasking.py` for the data/queue ops, autonomy module calls it — clean seam.)
2. Cortex DI shape: pass individual callables, or one small `ChatBridge` handle?
   (Claude leans: a `ChatBridge` — cleaner, one seam.)
3. Stage 3 scope: move self-model assembly + injector now, or defer until 1–2 prove out?
4. **The existing `nova_body/nova_memory` package** (logger/journal/state/goals/
   log_reader) is named "memory" too — by the same logic ("memory isn't a body
   faculty") it may want renaming to the *faculty* it is (the recall/journaling
   machinery, e.g. a hippocampus/recall name) while the memory DATA stays in
   `workspace/memory/` + `nova_lancedb`. Rename it as part of this restructure, or
   leave for a separate pass? (Not touched yet — Cole's call.)
