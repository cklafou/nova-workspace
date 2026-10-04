# STATUS.md — Project Nova Current State
_Last updated: 2026-10-04 14:23:30_
_Technical runtime sections updated: 2026-10-02; older background notes retain their dates._

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
- **Her interface:** `nova_chat` (port **8765**) — Cole and Nova's chat; her single voice/ears.
  Resident Claude/Gemini chat clients were removed (2026): Nova reaches Cowork Claude on Cole's
  desktop via her **Ping** function (`general_tools/ping_claude.ps1`) when she wants him.
  (The `nova_qt` desktop app, `nova_gateway`/Discord, and OpenClaw are all retired.)
- **Her autonomy is a body faculty:** `nova_body/nova_runtime/runtime.py` coordinates the
  wake; `nova_cortex/executive.py` selects tasks. Accepted concrete work goes directly to
  execution. When no concrete task is ready, reflection, decision, exploration and rest
  remain available. Fresh asks, durable environment events and timers can wake her.
  Two-minute focus leases rotate equal-priority tasks at checkpoints; a wake defaults to
  a 300-second budget. State lives in `nova_body/memory/autonomy_state.json`.
- **Her task board:** `nova_body/Tasking/tasks.json` retains attribution, progress,
  scheduling reasons and acceptance evidence. `DONE` runs the task's checks; missing or
  failing checks leave it waiting for review. Human confirmation is recorded separately.
  `prepare_task_workspace` and `promote_task_workspace` offer scoped test copies with
  checkpoints and checks against concurrent edits. These are not security sandboxes.
- **Her computer:** normal registered tools provide guest status, execution, screenshots
  as visual observations, and input actions. Cole can take control through the Control
  widget. A hidden session keeps WSL alive between calls; the VNC service has its own
  writable X11 socket mount so WSLg's read-only mount does not break desktop startup.
- **Runtime control:** Stop supervises model generation, worker threads and child processes.
  Structured receipts distinguish success, failure, refusal, timeout, cancellation and
  unknown; historical receipts retain their original limitations. Events and memory
  writes use durable queues under `nova_body/memory/`, including visible retry failures.
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
autonomy_state.json) lives in `nova_body/memory/`; Tasking, SELF, logs and the vector database are body-owned too.

---

## Tools — `general_tools/` (detachable)
| Package / file | Purpose |
|---|---|
| `nova_chat/` | Her voice — FastAPI/WebSocket group chat server (`server.py`, `clients/`, `nova_bridge.py`, `workspace_context.py`, `nova_lang.py`) |
| `nova_sync/` | `watcher.py` GitHub auto-commit + `drive.py` Google Drive workspace mirror (rides with each push) + `backup.py` local backups |
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
| Local | Qwen 3.6 27B Q6_K_XL + `mmproj-F16` projector | Nova's thinking AND her sight — one model, one server (llama.cpp on 8080) |

_Her vision is the mmproj projector on her own Qwen 3.6 base — NOT an API. (Haiku-vision was
migrated to local eyes 2026-07-19; the last stale claims of it were scrubbed from docs and code
2026-08-02.) Resident Claude (`claude-sonnet-4-6`) and Gemini (`gemini-2.5-pro`) nova_chat
clients were removed (2026); Nova reaches Cowork Claude on Cole's desktop via Ping
(`general_tools/ping_claude.ps1`). No external API sits in her live loop today; `ANTHROPIC_API_KEY`
stays set for the planned cloud witness lane (see `memory/reports/CLOUD_LANES_2026-08-02.md`)._

The local inference path does not require Anthropic or Google API keys. Optional external integrations have their own configuration.

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
