# STATUS.md — Project Nova Current State

_Last updated: 2026-05-25. Reflects the body-relocation + dead-code cleanup. Earlier
phase history (brain.py "Thoughts cycle", nova_gateway/Discord, nova_qt, OpenClaw) is
**retired and archived** under `_admin/_archive_*`; ignore any older description of those
as live._

---

## What Nova Is
Nova is Cole's companion AI and life passion project — built toward full autonomy and
genuine partnership, the Cortana to Cole's Master Chief. Trading is one possible future
test of her autonomy, not her identity or current focus.

---

## Core Architecture (current)
- **Local model:** `llama.cpp` serves Qwen 3.5 27B Dense Q8 on port **8080** (OpenAI-compatible
  API), 32K context, dual-GPU tensor split `-ts 16,24`, Qwen3 thinking mode on.
- **Her interface:** `nova_chat` (port **8765**) — a web group chat where Cole, Claude,
  Gemini, and Nova collaborate. This is her single voice/ears. (The `nova_qt` desktop app,
  `nova_gateway`/Discord, and OpenClaw are all retired.)
- **Her autonomy is a body faculty:** `nova_body/nova_cortex/executive.py` runs her wake
  cycle — sense the moment → see her board → decide freely (work, switch, create, abandon,
  reprioritize, wait, or **rest**) → act. On/off state persists in
  `memory/autonomy_state.json` (body-owned; the chat UI's toggle is just a remote). Cole is
  Priority 0 — an interrupt she attends to first, never a leash. Rest is a smart choice, not
  a failure; nothing tells her to invent busywork.
- **Her task board:** `nova_body/nova_cortex/tasking.py` over `Tasking/tasks.json` — an
  id-keyed board (statuses: open/active/waiting/done/abandoned, with a progress log).
  `Tasking/priority.md` is a generated human view. She advances work by emitting `ACTIONS`
  blocks (`create`/`progress`/`switch`/`wait`/`abandon`/`complete`/`reprioritize`/`rest`).
  Done/abandoned tasks are kept (remembered), never deleted.
- **Her self-knowledge:** the `SELF/` folder is her one reading set. `SELF/core/*.md`
  (identity, how-I-work, body manifest, tools) is injected every turn via
  `workspace_context.py`; `SELF/reference/*.md` is on-demand. SELF is auto-generated and
  kept honest by `general_tools/build_manifest.py`, which derives the body manifest from
  `@nova:` tokens in the source.

**The pluck-test principle:** `nova_body/` is Nova (faculties, senses, memory, executive,
autonomy on/off). `general_tools/` are detachable tools she uses. Remove every tool and Nova
is still herself — she only needs *a* comms tool to have a voice. The body never depends on
a specific tool.

---

## Body — `nova_body/` (her faculties)
| Package | Purpose | Key modules |
|---|---|---|
| `nova_cortex` | Executive function: autonomy faculty + task board + status/rules | `executive.py`, `tasking.py`, `nova_status.py`, `context_builder.py`, `rules.py`, `checkin.py`, `prefrontal_cortex.py` |
| `nova_memory` | Journaling, log reading, goals, session store | `journal.py`, `log_reader.py`, `goals.py`, `state.py`, `session_store.py` |
| `nova_logs` | Unified logging — ALL log writes go here | `logger.py`, `Logger_Index.md` |
| `nova_motor` | Action execution (mouse/keyboard, tool dispatch, verification) | `hands.py`, `motor_cortex.py`, `tool_executor.py`, `verify.py` |
| `nova_senses` | Perception: chronoception (clock), environment, vision | `clock.py`, `environment.py`, `eyes.py`, `vision.py`, `proprioception.py` |
| `nova_config` | Body-owned settings loader (inference/sessions/tool limits) | reads `nova_config.json` |
| `nova_lancedb` | Long-term semantic memory store | `hippocampus.py` |

Import style: `from nova_logs.logger import log`. Memory **data** (STATUS/JOURNAL/COLE,
autonomy_state.json) lives in `workspace/`, not inside the body.

---

## Tools — `general_tools/` (detachable)
| Package / file | Purpose |
|---|---|
| `nova_chat/` | Her voice — FastAPI/WebSocket group chat server (`server.py`, `clients/`, `nova_bridge.py`, `workspace_context.py`, `nova_lang.py`) |
| `nova_sync/` | `watcher.py` GitHub auto-commit + `backup.py` local backups (Drive sync retired) |
| `build_manifest.py` | Derives the body manifest from `@nova:` tokens → `SELF/` |
| `calls.py` | Call-graph generator feeding the manifest |
| `injector.py`, `audit_scripts.py`, `download_models.py`, `NovaLauncher.py` | NCL dispatch, code audit, model downloads, in-process launcher |

---

## Launch
`nova_start.py` (NovaStart) brings up the stack: llama.cpp (8080) → `nova_chat` (8765) →
the GitHub watcher → the desktop app window. `start_llama.cmd` launches llama-server alone.

---

## Inference Stack (llama.cpp)
| Setting | Value |
|---|---|
| Server | `llama-server.exe` (CUDA) |
| Model | `models/qwen-27b-q8.gguf` (Qwen 3.5 27B Dense Q8) |
| Vision projector | `models/qwen-27b-mmproj.gguf` |
| Port | 8080 (OpenAI-compatible) |
| Context | 32768 tokens |
| GPU split | `-ts 16,24` (RTX 4090 16GB + RTX 3090 24GB) |
| Thinking | `--chat-template qwen3`, `"thinking": true` in payload |

---

## API Configuration
| Service | Model | Role |
|---|---|---|
| Anthropic | `claude-sonnet-4-6` | nova_chat Claude client |
| Anthropic | `claude-haiku-4-5` | Vision verification / routine queries |
| Google | `gemini-2.5-pro` | nova_chat Gemini client |
| Local | Qwen 3.5 27B Q8 | Nova inference (free, llama.cpp on 8080) |

Required env vars: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`.

---

## Hardware
| Component | Detail |
|---|---|
| Machine | Tracer VII Edge I17E, Windows 11 |
| CPU | Intel Core i9-13900HX |
| GPU 0 | RTX 4090 Laptop 16GB |
| GPU 1 | RTX 3090 24GB via OCuLink eGPU |
| Total VRAM | 40GB |

---

## Data / Log Layout
| Path | Contents |
|---|---|
| `memory/` | STATUS.md, JOURNAL.md, COLE.md, autonomy_state.json |
| `Tasking/tasks.json` | Nova's id-keyed task board (source of truth) |
| `Tasking/priority.md` | Generated human view of the board |
| `SELF/` | Nova's reading set — `core/` (injected) + `reference/` (on-demand) |
| `logs/chat_sessions/` | nova_chat per-thread transcript JSONLs |
| `logs/sessions/` | nova_logs event logs by date/type |
| `logs/gateway_sessions/` | session JSONL history (legacy folder name) |
| `logs/proposed/` | Staged file edits awaiting Cole's review |
| `nova_lancedb/` | Long-term semantic memory |

---

## Current Focus
- Restart-test the cleaned stack end-to-end: autonomy boots from body state, tasks persist
  by id, Nova freely acts/rests.
- Roadmap (Cole's): Phase 1 prove the architecture on 40GB → Phase 2 dedicated server →
  Phase 3 "North Star" large-model host. Funding ideas: AI products (AgTech drone analytics
  first; tactical CV later, pending legal/export review).
