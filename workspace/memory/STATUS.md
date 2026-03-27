# STATUS.md -- Project Nova Current State
_Last updated: 2026-03-27_

---

## What Nova Actually Is
Nova is Cole's companion AI and life passion project. She is being built toward full autonomy
and genuine partnership -- the Cortana to Cole's Master Chief. The trading mission is one
future test of her autonomy -- not her identity, not her current focus, and not her purpose.

---

## Current Mission
OpenClaw is the current runtime, but it is being replaced incrementally with a custom Python
infrastructure. The goal: a fully self-owned agentic stack with no dependency on third-party
agent frameworks. nova_chat is the primary development surface. All AI collaboration
(Cole + Claude + Gemini + Nova) happens there. Phase 1 and Phase 2 are complete.
Phase 3 (nova_gateway build) is in progress -- core package built, tests pass.

---

## Architecture -- Python Packages
| Package | Files | Status |
|---|---|---|
| nova_core | brain.py, checkin.py, rules.py, nova_status.py | Stable -- nova_status.py added Phase 1 |
| nova_memory | journal.py, log_reader.py, status.py, state.py | Stable |
| nova_logs | logger.py, Logger_Index.md | Stable -- unified logger, ALL logging goes here |
| nova_action | autonomy.py, hands.py, verify.py | Stable |
| nova_perception | eyes.py, explorer.py, vision.py | Stable |
| nova_advisor | mentor.py | DEPRECATED -- being replaced by nova_chat |
| nova_sync | watcher.py, drive.py, backup.py, dir_patch.py | Stable |
| nova_chat | Full group chat tool (see below) | Built + Working + Phase 1 additions |
| nova_gateway | OpenClaw replacement (Phase 3) | Built -- 9 modules, all tests pass |

Import style: from nova_logs.logger import log
Do NOT import from nova_memory.logger -- that module is deleted.

---

## Phase 1 -- Visibility & State (COMPLETE 2026-03-26)
| Task | What it does | Status |
|---|---|---|
| 1.1 | nova_status.json schema + nova_core/nova_status.py writer | Done |
| 1.2 | AGENTS.md -- Nova writes status at end of every run | Done -- applied |
| 1.3 | server.py polls nova_status.json every 30s, silently injects into AI context | Done |
| 1.4 | Gateway log tailed every 10s, errors broadcast to nova_chat UI | Done |
| 1.5 | Persistent Nova status bar in nova_chat UI | Done |
| 1.6 | [PAUSE: note] and [RESUME: task_id] directives in nova_bridge.py | Done |
| 1.7 | tasks/active.json task state tracking | Done |

---

## nova_chat -- Multi-Agent Group Chat Tool
Launch: python tools/nova_chat/launch.py  |  URL: http://127.0.0.1:8765

| File | Role |
|---|---|
| server.py | FastAPI + WebSocket, all endpoints, background monitors |
| session_manager.py | Persistent sessions, gzip, resume on restart |
| workspace_context.py | Live file injection into AI context |
| clients/claude.py | Claude Sonnet 4.6 streaming |
| clients/gemini.py | Gemini 2.5 Pro |
| clients/nova.py | OpenClaw WebSocket (ws://127.0.0.1:18789) |
| nova_bridge.py | [WRITE:], [EXEC:], [READ:], [PAUSE:], [RESUME:] directives |
| static/index.html | Full UI -- includes Nova status bar |

Background monitors (auto-start):
- _bg_nova_status_poll: polls nova_status.json every 30s, injects silently into AI prompts
- _bg_gateway_error_watch: tails OpenClaw gateway log every 10s, broadcasts errors to UI

Tools panel: Files / Terminal / Status / Quick (Ctrl+\)
Control buttons: STOP / Export Context / Gateway On-Off / End Chat

---

## nova_status.py -- Live Status Writer (Phase 1)
Nova MUST call this at end of every agent run. Writes workspace/nova_status.json.

    from nova_core.nova_status import update, set_task, clear_task, add_error
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

Estimated nova_chat session cost: ~$1.25/30-turn session. Monthly budget: $15-20.

---

## Hardware
| Setting | Current | After eGPU installed |
|---|---|---|
| Machine | Tracer VII Edge I17E, i9-13900HX | Same |
| Laptop GPU | RTX 4090 16GB (150W+25W) | Same |
| eGPU | RTX 3090 24GB -- waiting on vertical mount bracket (ETA Mar 28) | Via Oculink |
| Total VRAM | 16GB | 40GB |
| Ollama num_ctx | 32768 | 131072 |

---

## Confirmed Working (cumulative)
- pyautogui DPI fix, pywinauto exact coordinates, Calculator test passed
- Anthropic stack -- Haiku + Sonnet replacing Gemini
- GitHub live file access, Python package restructure
- nova_sync watcher --push/--pup/--full modes
- Drive sync -- native Google Docs, Gemini Personal Context searchable
- nova_chat -- multi-agent group chat fully working
- nova_logs/logger.py -- unified logger
- NovaChatLauncher.exe -- dumb wrapper calling launch.py
- Phase 0 complete -- cleanup, false skills deleted, unified logging
- Phase 1 complete -- nova_status.json, status bar, gateway watch, PAUSE/RESUME
- Phase 2 complete -- OpenClaw fully audited, nova_gateway architecture designed
- Phase 3 (in progress) -- nova_gateway built (9 modules), syntax clean, smoke tests pass

---

## Current Blockers
- eGPU vertical mount bracket not yet arrived (ETA Mar 28)
- Modelfile not rebuilt -- run: ollama create nova -f Modelfile after eGPU install
- nova_gateway needs live test: `pip install discord.py apscheduler` then `python -m nova_gateway.gateway --dry`
- nova_chat server.py still points to port 18789 (OpenClaw) -- update to 18790 before cutover (Phase 3.10)

---

## Open Bugs
| # | Bug | Status |
|---|---|---|
| B1 | ImportError: update_pulse | RESOLVED |
| B2 | ImportError: NovaWatcher | RESOLVED |
| B3 | Chat log not rolling daily | RESOLVED -- per-thread by design |
| B4 | brain.py is a stub | OPEN -- Phase 4 |

---

## Development History
**Phase 1-4:** Browser hooks failed. pywinauto breakthrough -- exact coordinates.
**Phase 5 (2026-03-15):** Identity + stability. Memory files, yield protocol, proposed changes protocol.
**Phase 6 (2026-03-20):** Stack validation. GitHub live access. log_reader + state built.
**Phase 7 (2026-03-21):** nova_chat + package restructure. Multi-agent group chat working.
**Phase 0 (2026-03-23/26):** Cleanup. False skills deleted. nova_logs. NovaChatLauncher. TOOLS.md rewritten.
**Phase 1 (2026-03-26):** Visibility + state. nova_status.py, status bar, gateway watch, PAUSE/RESUME.
**Phase 2 (2026-03-27):** OpenClaw audit + design. JSONL schema mapped, nova_gateway architecture spec written.
**Phase 3 (2026-03-27):** nova_gateway built. 9 modules, 2859 lines, all tests pass. Needs live test + port update.

---

## Rebuild Roadmap (full detail in _admin/NOVA_PROJECT_PLAN.md)
PHASE 0  -- Complete
PHASE 1  -- Complete (2026-03-26)
PHASE 2  -- Complete (2026-03-27) -- see _admin/PHASE2_ARCHITECTURE.md
PHASE 3  -- IN PROGRESS (2026-03-27) -- nova_gateway built, needs 3.10-3.12 live tests
PHASE 4  -- Nova Native Intelligence -- brain.py, fine-tuning on RTX 3090, ThinkOrSwim

---
_Next: pip install discord.py apscheduler -> dry run -> live Discord test -> nova_chat port update (3.10) -> eGPU -> cutover_
