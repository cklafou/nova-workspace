# STATUS.md — Project Nova Current State
_Last updated: 2026-07-09 00:37:34_

_Prior revision 2026-05-25 — reflects the body-relocation + dead-code cleanup. Earlier
phase history (brain.py "Thoughts cycle", nova_gateway/Discord, nova_qt, OpenClaw) is
**retired and archived** under `_admin/_archive_*`; ignore any older description of those
as live._

---

## What Nova Is
Nova is Cole's companion AI and life passion project — built toward full autonomy and
a genuine lifelong partnership — growing and succeeding together (Cortana and Master Chief is Cole's metaphor for it). Trading is one possible future
test of her autonomy, not her identity or current focus.

---

## Core Architecture (current)
- **Local model:** `llama.cpp` serves Qwen 3.6 27B Dense Q6_K_XL (+MTP speculative decoding) on
  port **8080** (OpenAI-compatible API), **64K context** (`-c 65536`, single slot; native ctx is
  262144), dual-GPU tensor split `-ts 12,28`, hybrid thinking on via `--jinja --reasoning-format
  deepseek`. Launched by `start_llama_qwen36.cmd` (nova_start.py builds the equivalent).
- **Her interface:** `nova_chat` (port **8765**) — a web group chat where Cole, Claude,
  Gemini, and Nova collaborate. This is her single voice/ears. (The `nova_qt` desktop app,
  `nova_gateway`/Discord, and OpenClaw are all retired.)
- **Her autonomy is a body faculty:** `nova_body/nova_cortex/executive.py` runs her wake
  cycle in two phases — **reflect** (sit with the moment in first person, fed by her Touch
  sense for what's interacting with her) → **decide freely** (engage Cole, work, switch,
  create, abandon, reprioritize, wait, or **rest**). Then a third **execute** pass: if she
  holds an open task and isn't mid-reply to Cole or resting, she does the next concrete step
  of it with her real tools and logs honest progress (or completes it). On/off state persists
  in `memory/autonomy_state.json` (body-owned; the chat UI's toggle is just a remote). Cole is
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
| `nova_cortex` | Executive function: autonomy faculty + task board + status/rules | `executive.py`, `tasking.py`, `nova_status.py`, `context_builder.py`, `rules.py`, `checkin.py` |
| `nova_memory` | _Scaffolded, not yet wired into the running stack (manifest: no inbound refs)._ Intended purpose (per `@nova:` tag): persistent state, journal, goals/status, daily log summaries. Current memory data is written directly to `memory/*.md`. | `journal.py`, `log_reader.py`, `goals.py`, `state.py`, `session_store.py` |
| `nova_logs` | Unified logging — ALL log writes go here | `logger.py`, `Logger_Index.md` |
| `nova_motor` | _Scaffolded, not yet wired into the running stack (manifest: no inbound refs)._ Intended purpose (per `@nova:` tag): motor system — execute actions (`hands.py`), plan them (`motor_cortex.py`), verify results. From the GUI-automation phase; current Nova acts via `nova_chat`'s tool router, and `motor_cortex.NovaAutonomy` is superseded by `nova_cortex/executive.py`. | `hands.py`, `motor_cortex.py`, `tool_executor.py`, `verify.py` |
| `nova_senses` | Perception: chronoception (clock), environment, touch (what's interacting with her), vision | `clock.py`, `environment.py`, `touch.py`, `eyes.py`, `vision.py`, `proprioception.py` |
| `nova_config` | Body-owned settings loader (inference/sessions/tool limits) | reads `nova_config.json` |
| `nova_lancedb` | Long-term semantic memory store | `hippocampus.py` |
| `nova_imagination` | Visual-creation faculty — drives local ComfyUI to render images; powers the `generate_image` tool (auto-applies her self-LoRA for self-portraits). **LIVE** (used by nova_chat) | `imagination.py` |

Import style: `from nova_logs.logger import log`. Memory **data** (STATUS/JOURNAL/COLE,
autonomy_state.json) lives in `workspace/`, not inside the body.

---

## Tools — `general_tools/` (detachable)
| Package / file | Purpose |
|---|---|
| `nova_chat/` | Her voice — FastAPI/WebSocket group chat server (`server.py`, `clients/`, `nova_bridge.py`, `workspace_context.py`, `nova_lang.py`) |
| `nova_sync/` | `watcher.py` GitHub auto-commit + `drive.py` Google Drive mirror for Gemini (rides with each push) + `backup.py` local backups |
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
| Model | `models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf` (Qwen 3.6 27B Dense Q6_K_XL, MTP variant) |
| Vision projector | `models/qwen3.6/mmproj-F16.gguf` |
| Port | 8080 (OpenAI-compatible) |
| Context | 65536 tokens (single slot, `--parallel 1`; native 262144) |
| GPU split | `-ts 12,28` (RTX 4090 16GB + RTX 3090 24GB) |
| Speculative | MTP: `--spec-type draft-mtp --spec-draft-n-max 2` (~1.4-2x gen) |
| Thinking | hybrid, on by default via `--jinja --reasoning-format deepseek` |

---

## API Configuration
| Service | Model | Role |
|---|---|---|
| Anthropic | `claude-sonnet-4-6` | nova_chat Claude client |
| Anthropic | `claude-haiku-4-5` | Vision verification / routine queries |
| Google | `gemini-2.5-pro` | nova_chat Gemini client |
| Local | Qwen 3.6 27B Q6_K_XL | Nova inference (free, llama.cpp on 8080) |

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
- **Active direction (2026-05-31): embodiment + body reorg** — give Nova autonomous see-and-control
  of a whole computer (local vision + motor), with tool-execution moved into the body per the Pluck
  Test. Plan: `memory/reports/Embodiment_Roadmap_2026-05-31.md`. Most build steps need the stack live.
- Roadmap (Cole's): Phase 1 prove the architecture on 40GB → Phase 2 dedicated server →
  Phase 3 "North Star" large-model host. Funding ideas: AI products (AgTech drone analytics
  first; tactical CV later, pending legal/export review).
