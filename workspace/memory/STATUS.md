# STATUS.md -- Project Nova Current State
_Last updated: 2026-05-08_

---

## What Nova Actually Is
Nova is Cole's companion AI and life passion project. She is being built toward full autonomy
and genuine partnership -- the Cortana to Cole's Master Chief. The trading mission is one
future test of her autonomy -- not her identity, not her current focus, and not her purpose.

---

## Current Mission
OpenClaw is retired. Nova runs entirely on a custom Python stack:
- **llama.cpp** serves Qwen 3.5 27B Dense Q8 locally on port 8080 (OpenAI-compatible API)
- **nova_chat** (port 8765) is the primary group chat interface — Cole + Claude + Gemini + Nova
- **nova_gateway** (port 18790) is the Discord gateway daemon, replacing OpenClaw entirely
- Phases 0 through 4A are all complete. Next focus: frontend polish, live testing, and Phase 4B+.

---

## Architecture -- Python Packages
| Package | Files | Status |
|---|---|---|
| nova_cortex | brain.py, checkin.py, rules.py, nova_status.py | Stable |
| nova_memory | journal.py, log_reader.py, status.py, state.py | Stable |
| nova_logs | logger.py, Logger_Index.md | Stable -- unified logger, ALL logging goes here |
| nova_motor | autonomy.py, hands.py, verify.py | Stable |
| nova_senses | eyes.py, explorer.py, vision.py | Stable |
| nova_sync | watcher.py, drive.py, backup.py, dir_patch.py | Stable |
| nova_chat | Full group chat tool (see below) | Built + Working |
| nova_gateway | Discord gateway daemon (OpenClaw replacement) | Built -- Phase 3 complete |

Import style: from nova_logs.logger import log
Do NOT import from nova_memory.logger -- that module is deleted.

---

## Phase Completion Summary
| Phase | Name | Status | Completed |
|---|---|---|---|
| 0 | Cleanup + Unification | COMPLETE | 2026-03-23/26 |
| 1 | Visibility & State | COMPLETE | 2026-03-26 |
| 2 | OpenClaw Audit + Design | COMPLETE | 2026-03-27 |
| 3 | nova_gateway Build | COMPLETE | 2026-03-27/28 |
| 4A | Nova Native Intelligence (brain.py) | COMPLETE | 2026-03-28 |
| 4B+ | Fine-tuning / Advanced Autonomy | NOT STARTED | -- |

---

## Phase 4A -- Nova Native Intelligence (COMPLETE 2026-03-28)
All 8 sub-phases of 4A were completed:
- 4A.1 brain.py core loop (Thoughts system, heartbeat, wake/sleep)
- 4A.2 Thoughts directory structure + THOUGHT_TEMPLATE.md
- 4A.3 HEARTBEAT.md -- Nova's autonomous cycle document
- 4A.4 NCL parser (nova_lang.py) -- dispatches @role calls from nova_chat
- 4A.5 NCL_MASTER.md -- grammar reference injected at session boot
- 4A.6 Master_Inbox routing (server.py routes module replies to thought inboxes)
- 4A.7 Thoughts panel in UI + live Thoughts pane with brain.py status
- 4A.8 brain.py fully wired to server.py -- autonomous cycle live

---

## nova_chat -- Multi-Agent Group Chat Tool
Launch: python general_tools/nova_chat/launch.py  |  URL: http://127.0.0.1:8765

| File | Role |
|---|---|
| server.py | FastAPI + WebSocket, all endpoints, background monitors |
| session_manager.py | Persistent sessions, gzip, resume on restart |
| workspace_context.py | Live file injection into AI context |
| clients/claude.py | Claude Sonnet 4.6 streaming |
| clients/gemini.py | Gemini 2.5 Pro |
| clients/nova.py | llama.cpp HTTP (http://127.0.0.1:8080) -- streaming + tool loop |
| nova_bridge.py | [WRITE:], [EXEC:], [READ:], [PAUSE:], [RESUME:] directives |
| nova_lang.py | NCL parser -- dispatches @role calls to modules |
| static/index.html | Browser UI (legacy) |

Background monitors (auto-start):
- _bg_nova_status_poll: polls nova_status.json every 30s, injects silently into AI prompts
- _bg_gateway_error_watch: tails nova_gateway log every 10s, broadcasts errors to UI

---

## nova_qt -- Native Desktop UI (PRIMARY INTERFACE)
PyQt6 desktop app. Launch: python general_tools/nova_qt/main.py

| File | Role |
|---|---|
| main.py | App entry point, QApplication |
| window.py | QMainWindow -- assembles sidebar + chat, owns WebSocket client |
| chat_panel.py | Central chat area -- sessions, messages, input, controls |
| sidebar.py | Left panel -- Files / Terminal / Status / Thoughts tabs |
| ws_client.py | QThread WebSocket client, typed Qt signals for all message types |
| theme.py | Color constants (NOVA purple, COLE, CLAUDE, GEMINI, etc.) |
| markdown.py | Markdown-to-HTML renderer for chat bubbles |

### Nova Qt UI Features (current as of 2026-05-08)
- Multi-session tab bar with rename (right-click) and delete
- Auto-scroll with floating down-arrow button; preserves position on manual scroll
- Inline ThinkingBlock per Nova message -- collapsible "Thought for Xs" panel above reply
- Thoughts sidebar pane also receives think tokens (dual display)
- Depth slider: Fast (512) / Balanced (2048) / Deep (4096) / Max (8192) max_tokens
- Autonomous mode toggle pill (emits autonomous_toggle WS message to server)
- Nova online/offline status bar badge -- updates on WS connect/disconnect, not just status poll
- llama.cpp status button in status bar (click to toggle start/stop)
- File injection from sidebar tree to input box
- STOP button (chat panel + status bar) -- cancels all in-flight AI tasks

### WebSocket Message Types (nova_qt <-> server)
| Direction | Type | Purpose |
|---|---|---|
| Client -> Server | message | Cole sending a chat message |
| Client -> Server | stop | Cancel all AI tasks |
| Client -> Server | new_session / switch_session | Session management |
| Client -> Server | set_depth | Depth slider changed -- max_tokens for Nova |
| Client -> Server | autonomous_toggle | Autonomous mode on/off |
| Server -> Client | think_start / think_token / think_end | Nova thinking stream |
| Server -> Client | generation_start / nova_progress / generation_end | Nova gen stats |
| Server -> Client | nova_activity | Directive detected in Nova's response |

---

## Inference Stack (llama.cpp)
| Setting | Value |
|---|---|
| Server | llama-server.exe (llama-b9041, CUDA 12.4) |
| Model | models/qwen-27b-q8.gguf (Qwen 3.5 27B Dense Q8) |
| Vision projector | models/qwen-27b-mmproj.gguf |
| Port | 8080 |
| Context | 32768 tokens |
| GPU split | -ts 16,24 (4090 16GB + 3090 24GB) |
| Thinking mode | --chat-template qwen3, "thinking": True in API payload |
| Launch | start_llama.cmd |

---

## nova_status.py -- Live Status Writer
Nova MUST call this at end of every agent run. Writes workspace/nova_status.json.

    from nova_cortex.nova_status import update, set_task, clear_task, add_error
    update(pulse='Idle', summary='What you just did')
    set_task('task_id', status='running', description='What it is doing')
    clear_task()
    add_error('vision', 'Element not found: Trade Button')

server.py silently prepends nova_status summary to every AI system prompt every 30s.
nova_chat status bar polls /api/nova/status every 15s.

---

## API Configuration
| Service | Model | Role | Cost |
|---|---|---|---|
| Anthropic | claude-sonnet-4-6 | nova_chat Claude client | $3/$15 per MTok |
| Anthropic | claude-haiku-4-5 | Vision verification, routine queries | $0.25/$1.25 per MTok |
| Google | gemini-2.5-pro | nova_chat Gemini client | $1.25/$10 per MTok |
| Local | Qwen 3.5 27B Q8 | Nova inference (free) | llama.cpp on 8080 |

Estimated nova_chat session cost: ~$1.25/30-turn session. Monthly budget: $15-20.

---

## Hardware
| Component | Status |
|---|---|
| Machine | Tracer VII Edge I17E, i9-13900HX, Windows 11 |
| Laptop GPU | RTX 4090 Laptop 16GB (GPU 0) |
| eGPU | RTX 3090 24GB via Oculink (GPU 1) -- INSTALLED |
| Total VRAM | 40GB (16GB + 24GB) |
| Context (llama.cpp) | 32768 tokens (can go higher) |

---

## Session / Log Layout
| Path | Contents |
|---|---|
| logs/chat_sessions/ | nova_chat per-thread transcript JSONLs |
| logs/sessions/ | nova_logs event logs by date/type |
| logs/gateway_sessions/ | nova_gateway Discord agent session JSONLs |
| logs/proposed/ | Staged file edits awaiting Cole's review |

---

## BOOTUP/ Folder -- Identity File Organization
The 6 core boot files now live in `BOOTUP/` (moved 2026-05-07):

| File | Purpose |
|---|---|
| BOOTUP/AGENTS.md | Nova's workspace rules and operating protocols |
| BOOTUP/NOVA.md | Core identity, personality, mission |
| BOOTUP/TOOLS.md | Tool reference, hardware notes, paths |
| BOOTUP/NCL_MASTER.md | Nova Command Language grammar reference |
| BOOTUP/BOOTSTRAP.md | Session startup sequence (read this first) |
| BOOTUP/HEARTBEAT.md | Heartbeat/Thoughts cycle instructions |

workspace_context.py and nova_gateway.json both point to BOOTUP/ now.
The old root copies must be deleted (run apply_bootup_reorganization.ps1 if not done).

---

## Patch Scripts (workspace root)
Scripts that patch read-only server files (run once, then discard or keep for reference):

| Script | Status | Purpose |
|---|---|---|
| apply_bootup_reorganization.ps1 | Run once after BOOTUP/ was created | Patches workspace_context.py source + deletes root originals |
| patch_autonomous_server.ps1 | Superseded by patch_depth_server.ps1 | Adds autonomous_toggle to server.py (covered below) |
| patch_depth_server.ps1 | **Needs to be run** | Patches server.py + nova.py for depth slider + autonomous toggle |

---

## Confirmed Working (cumulative)
- pyautogui DPI fix, pywinauto exact coordinates, Calculator test passed
- Anthropic stack -- Haiku + Sonnet
- Gemini 2.5 Pro integration
- GitHub live file access, Python package restructure
- nova_sync watcher --push/--pup/--full modes
- Drive sync -- native Google Docs, Gemini Personal Context searchable
- nova_chat -- multi-agent group chat fully working
- nova_logs/logger.py -- unified logger
- NovaChatLauncher.exe (Nova.exe) -- wrapper calling launch.py
- Phases 0-4A complete -- all sub-phases built and tested
- llama.cpp CUDA backend -- dual-GPU tensor split (-ts 16,24) working
- Qwen3 thinking mode -- think tokens stream correctly (think_start/think_token/think_end)
- nova_gateway -- Discord daemon, 9 modules, 2859 lines
- brain.py -- fully implemented Thoughts cycle (not a stub)
- NCL parser (nova_lang.py) -- @role dispatch working
- nova_qt -- PyQt6 native desktop UI (replaces browser UI as primary interface)
- nova_qt auto-scroll with floating down-arrow button + position preservation
- nova_qt session rename/delete (right-click context menu on tabs)
- nova_qt Nova online/offline badge correct on WS connect/disconnect
- nova_qt Autonomous mode toggle wired to server autonomous_toggle handler
- nova_qt inline ThinkingBlock per Nova message (collapsible "Thought for Xs")
- nova_qt depth slider (Fast/Balanced/Deep/Max) wires max_tokens to server

---

## Current Blockers / Open Work
- **Run patch_depth_server.ps1** from workspace root (patches server.py + nova.py for depth slider)
- **Run apply_bootup_reorganization.ps1** if not yet done (cleans up root originals after BOOTUP/ move)
- Nova.exe needs rebuild after code changes (python tools/build_nova.py)
- brain.py Thoughts cycle needs live end-to-end test in nova_chat
- nova_gateway needs live Discord test (pip install discord.py apscheduler first)
- moondream2 model not yet downloaded (python tools/download_models.py)
- Formally retire OpenClaw Phase 3.13 (write retirement doc)

---

## Open Bugs
| # | Bug | Status |
|---|---|---|
| B1 | ImportError: update_pulse | RESOLVED |
| B2 | ImportError: NovaWatcher | RESOLVED |
| B3 | Chat log not rolling daily | RESOLVED -- per-thread by design |
| B4 | brain.py is a stub | RESOLVED -- Phase 4A.8 |
| B5 | Nova thinking not visible in UI | RESOLVED -- inline ThinkingBlock added to nova_qt (2026-05-08) |
| B6 | Nova online indicator wrong when server down | RESOLVED -- badge tied to WS connect/disconnect |
| B7 | Session tabs showing "Session N" not real name | RESOLVED -- reads name key correctly |
| B8 | Nova token budget too low (2048 hardcoded) | RESOLVED -- depth slider, configurable 512-8192 |