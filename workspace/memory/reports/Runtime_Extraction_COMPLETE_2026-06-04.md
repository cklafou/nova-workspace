# Runtime Extraction — COMPLETE (Steps 1–6d)
_Last updated: 2026-07-08 08:44:42_
_2026-06-04 · Cowork Opus. Goal: pull Nova's life-support out of the chat server into her body
(`nova_body/nova_runtime/`) so she passes the **pluck test** — delete the chat server, she still
lives, thinks, and acts. Prerequisite for KoELS (runtime-owned LoRA loadout self-restart)._

## What the extraction achieved
Every faculty that keeps her alive and thinking now lives in `NovaRuntime`. The chat server has
been reduced to a **face** that subscribes to her event bus and supplies UI-side I/O. Generation,
cognition, perception, senses, model-server control, and memory are hers.

## Where each faculty lives now (`nova_body/nova_runtime/`)
| Module | Owns | Step |
|---|---|---|
| `event_bus.py` | publish→faces, bounded queues, pluck-safe (no subscriber = no-op) | 1 |
| `transcript_store.py` | durable conversation + race-proof `has_unread_cole` (attended marker) | 1 / 6a |
| `llama_control.py` | model-server health / autostart / stop / restart (+ KoELS self-restart later) | 2 |
| `model_guard.py` | rate-limit + consecutive-error backoff | 2 |
| `model_client.py` | model dispatch faculty — generation takes injected sinks, not a hard-wired face | 4 |
| `runtime.py` | indexer ownership, proprioception (CPU/RAM/VRAM), Touch/env senses, the **sleep/wake cognition loop** (`run_autonomy`/`_run_one_wake`), headless boot (`run`) | 3 / 5 / 6 |
| `__main__.py` | `python -m nova_runtime` — headless boot, the pluck test | 1 / 6c |

Cognition (`nova_cortex.executive`/`tasking`) and `nova_senses` are imported by the runtime
directly — they're her faculties (layer 1), correct for the body to use.

## Seam inversions (how the body stopped depending on the face)
- **broadcast → event bus** (5b): the daemon's wake/reflect/autonomy events publish to `_rt.bus`;
  the server subscribes (`_bg_runtime_events`) and renders. Pluck the server → emits no-op + still log.
- **perception → runtime transcript** (6a): the live chat mirrors Cole's raw text + Nova's replies
  into `_rt.transcript`; that file *is* her perception with no face attached.
- **run_ai_response → model-call vs broadcast** (4): the dispatch became `model_client.generate`,
  taking sinks; broadcast stayed in the face.
- **is_processing coordination** (6b): the loop relocated to the body; the server still owns the
  shared busy flag and exposes it via `_get_busy`/`_set_busy` hooks — zero WebSocket-path edits.

## The three boot modes (now available)
1. **Default (today, unchanged):** `NovaLauncher.py` / `server_runner.py` serve `nova_chat.server:app`;
   the server lazily creates the runtime (`get_shared_runtime()`) and drives the loop with rich hooks.
   **Behavior is byte-identical to before the 6d seam.**
2. **Headless / pluck (`python -m nova_runtime`):** no chat server at all — llama autostart, indexer,
   senses, and the autonomy loop with runtime-native hooks (transcript perception + `model_client`).
3. **Runtime-primary (`nova_chat/runtime_host.py`):** the runtime is created first and installed
   (`set_shared_runtime`), then the chat server is served as an attached face on her bus.

## Verification state
- **Live-verified (boot of 2026-06-03, Steps 2–6a):** clean boot, 77 generations via `model_client`,
  events on the bus rendering in the UI SESSION LOG, transcript fed, CPU/RAM/VRAM live, zero errors,
  zero fail-safe trips. (Filesystem + Chrome UI read.)
- **Built + unit-tested, NOT yet live-verified:** 6b (loop relocation on the live server), 6c
  (headless boot), 6d (shared-runtime seam + runtime-primary entrypoint). The mount repeatedly
  served `runtime.py` truncated to the sandbox, so 6b/6c logic was validated via verbatim replicas
  + Read-verification of the canonical file rather than an import-based test.

## Responsible final sequence — VERIFY, then FLIP (do not skip)
The project rule is *pluck-test before flipping the default boot.* Recommended order:
1. **Restart the app normally** → confirm 6b: autonomy still wakes / reflects / acts (watch the
   Live Logs + `logs/events/events-<date>.jsonl` for wake/reflect/autonomy).
2. **Run `python -m nova_runtime`** (with `nova_body` on PYTHONPATH) → confirm the pluck: she boots
   with no server, llama comes up, indexer starts, autonomy ticks. This is the milestone.
3. **Only then** flip the launcher default to `runtime_host.py` (one reversible line) if you want
   runtime-primary as the standard boot.

## Step 7 — remaining cleanup (gated on the verification above)
Tidy-up, not new capability. Do after the flip is proven, one item at a time, re-verifying each:
- Remove the now-vestigial server-side duplicates that delegate to the body: `_rt_llama`/`_rt_guard`
  module globals (the runtime owns `llama`/`guard`); the `memory_indexer` module alias once all
  call-sites read `_rt.indexer`.
- Move `run_ai_response`'s **generation + persistence** (the non-broadcast half of `on_done`:
  transcript add, memory index, bridge routing, FOR-COLE promotion) into the body so the headless
  generate reaches full fidelity and the face becomes truly detachable *at runtime* (the last 10%).
- Relocate `nova_client` (her llama client) + `HeartbeatContext` into `nova_body` so a perfect pluck
  imports nothing from `nova_chat`.
- Inject full `workspace_context` (memory/identity) into headless generation (port/relocate
  `WorkspaceContext.build_nova_context_block`).

## One-line revert (safety)
If a runtime-primary boot ever misbehaves: point the launcher back at `server_runner.py`. The
default path is unchanged, so this fully restores prior behavior.
