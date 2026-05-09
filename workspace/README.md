# Project Nova

Nova is Cole's companion AI and life passion project — built toward full autonomy and genuine partnership. She is NOT a trading bot. Trading is one future test of her autonomy, not her identity. She is a companion and dev partner first.

**For AI agents reading this file:** Start here for orientation, then read `memory/STATUS.md` for current state, blockers, and next steps. Nova's identity and operating rules live in `BOOTUP/`. Do not modify `models/` under any circumstances.

---

## Quick Launch

| What | How |
|---|---|
| **Nova Qt (primary UI)** | `python general_tools/nova_qt/main.py` or run `Rebuild_Nova.cmd` first if stale |
| **nova_chat server** | `python general_tools/nova_chat/launch.py` (port 8765) |
| **llama.cpp (Nova inference)** | `start_llama.cmd` (port 8080) |
| **nova_gateway (Discord)** | `python general_tools/nova_gateway_runner.py` or `Rebuild_Nova.cmd` |

Start order: `start_llama.cmd` → `launch.py` → `nova_qt/main.py`

---

## Workspace Layout

```
workspace/
├── BOOTUP/                  ← Nova's 6 identity/rules files (read at every session)
│   ├── BOOTSTRAP.md         ← Session startup sequence — read this first
│   ├── AGENTS.md            ← Operating rules, Thoughts system, safety, PowerShell rules
│   ├── NOVA.md              ← Core identity and personality
│   ├── TOOLS.md             ← Tool reference, hardware notes, paths
│   ├── NCL_MASTER.md        ← Nova Command Language grammar reference
│   └── HEARTBEAT.md         ← Heartbeat / Thoughts cycle instructions
│
├── memory/
│   ├── STATUS.md            ← Current project state, blockers, open bugs ← READ THIS
│   ├── JOURNAL.md           ← Running session log (append-only)
│   ├── COLE.md              ← Nova's living notes about Cole
│   └── STATUS.md            ← Source of truth for project phase + architecture
│
├── Tasking/                ← Nova's persistent task memory (survives session resets)
│   ├── priority.md          ← Active task queue — Nova reads this every heartbeat
│   ├── THOUGHT_TEMPLATE.md  ← Clone this to create a new Thought
│   ├── Master_Inbox/        ← Module responses land here before routing
│   └── [ThoughtName]/       ← One folder per active task
│
├── general_tools/           ← All Python tool packages
│   ├── nova_chat/           ← Multi-agent group chat server (FastAPI + WebSocket, port 8765)
│   ├── nova_qt/             ← PyQt6 native desktop UI (primary interface)
│   ├── nova_gateway/        ← Discord gateway daemon (port 18790)
│   ├── nova_gateway_runner.py ← Convenience entry point for the gateway
│   ├── build_nova.py        ← Builds Nova.exe wrapper
│   ├── download_models.py   ← Downloads moondream2 and other vision models
│   └── NovaLauncher.py      ← NovaChatLauncher.exe entry point
│
├── nova_tools/              ← Nova's core Python packages
│   ├── nova_cortex/           ← brain.py, checkin.py, rules.py, nova_status.py
│   ├── nova_memory/         ← journal.py, state.py, log_reader.py
│   ├── nova_logs/           ← Unified logger — ALL log writes go here
│   ├── nova_motor/         ← autonomy.py, hands.py (mouse/keyboard), verify.py
│   ├── nova_senses/     ← eyes.py, vision.py, explorer.py
│   └── nova_sync/           ← watcher.py, drive.py, backup.py, dir_patch.py
│
├── PATCHES/                 ← PowerShell patch scripts for server-side files
│   ├── README.md            ← Which patches need to be run and why
│   ├── patch_depth_server.ps1         ← NEEDS TO BE RUN (depth slider + autonomous toggle)
│   ├── apply_bootup_reorganization.ps1 ← NEEDS TO BE RUN (workspace_context.py path update)
│   ├── patch_nova_payload.ps1         ← NEEDS TO BE RUN (llama.cpp repeat_penalty + min_p)
│   └── Archived/            ← Superseded patches — do not run
│
├── logs/                    ← All runtime logs
│   ├── chat_sessions/       ← nova_chat per-thread transcript JSONLs
│   ├── sessions/            ← nova_logs event logs by date/type
│   ├── gateway_sessions/    ← nova_gateway Discord session JSONLs
│   └── proposed/            ← Staged file edits awaiting Cole's review
│
├── _admin/                  ← Project admin files (Live_Updates.md, handoff notes)
├── _build/                  ← Build artifacts
├── llama/                   ← llama.cpp binaries
├── models/                  ← SEALED — neural network weight files (GGUF, 18GB+)
│                               NEVER read, list, or open anything in here
├── nova_gateway.json        ← nova_gateway live config (contains Discord token)
├── nova_gateway - tokenless.json ← Tokenless copy for version control / sharing
└── prompt_cache/            ← llama.cpp KV cache files
```

---

## Key Config Files

| File | Purpose |
|---|---|
| `nova_gateway.json` | nova_gateway config — Discord token, modules, context injection |
| `nova_gateway - tokenless.json` | Same config without the token — safe to commit to git |
| `start_llama.cmd` | Launches llama-server.exe with dual-GPU tensor split (-ts 16,24) |
| `Patch_Nova.cmd` | Runs active patch scripts from PATCHES/ |
| `Rebuild_Nova.cmd` | Rebuilds Nova.exe via build_nova.py |
| `Install_Nova_Qt.cmd` | Installs PyQt6 + dependencies for nova_qt |

---

## Inference Stack

| Setting | Value |
|---|---|
| Server | llama-server.exe (llama-b9041, CUDA 12.4) |
| Model | `models/qwen-27b-q8.gguf` — Qwen 3.5 27B Dense Q8 |
| Vision projector | `models/qwen-27b-mmproj.gguf` |
| Port | 8080 (OpenAI-compatible API) |
| Context | 32768 tokens |
| GPU split | `-ts 16,24` (RTX 4090 16GB + RTX 3090 24GB) |
| Thinking mode | `--chat-template qwen3` + `"thinking": true` in API payload |

---

## Hardware

| Component | Detail |
|---|---|
| Machine | Tracer VII Edge I17E — Windows 11 |
| CPU | Intel Core i9-13900HX |
| GPU 0 | RTX 4090 Laptop 16GB |
| GPU 1 | RTX 3090 24GB via Oculink eGPU |
| Total VRAM | 40GB |
| Display | 17.3" 2560×1600 @ 240Hz |

---

## Phase Summary

| Phase | Name | Status |
|---|---|---|
| 0 | Cleanup + Unification | ✅ Complete |
| 1 | Visibility & State | ✅ Complete |
| 2 | OpenClaw Audit + Design | ✅ Complete |
| 3 | nova_gateway Build | ✅ Complete |
| 4A | Nova Native Intelligence (brain.py, Thoughts cycle, NCL, nova_qt) | ✅ Complete |
| 4B+ | Fine-tuning / Advanced Autonomy | 🔲 Not started |

Current focus: frontend polish, live testing, pending patches, and Phase 4B planning.

---

## Setup (fresh environment)

```powershell
pip install pyautogui pillow pywinauto watchdog anthropic httpx fastapi uvicorn websockets PyQt6
```

Required environment variables: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

Run `start_llama.cmd` before launching nova_chat. See `BOOTUP/TOOLS.md` for the full tool reference and path notes.

---

## Where to Find Things

| Question | Answer |
|---|---|
| What is Nova working on right now? | `Tasking/priority.md` |
| What phase is the project in? | `memory/STATUS.md` |
| What are Nova's rules and protocols? | `BOOTUP/AGENTS.md` |
| What happened in past sessions? | `memory/JOURNAL.md` |
| What patches still need to run? | `PATCHES/README.md` |
| What tools are available? | `BOOTUP/TOOLS.md` |
| What is Nova's personality? | `BOOTUP/NOVA.md` |
| What are the recent changes / handoff notes? | `_admin/Live_Updates.md` |
