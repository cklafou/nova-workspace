# Project Nova

Nova is Cole's companion AI and life passion project — built toward full autonomy and
genuine partnership. She is NOT a trading bot. Trading is one possible future test of her
autonomy, not her identity. She is a companion and dev partner first.

**For AI agents reading this file:** Start here for orientation, then read `memory/STATUS.md`
for current state and focus. Nova's identity and operating knowledge live in `SELF/` —
`SELF/core/` is injected into her context every turn; `SELF/reference/` is on-demand. Do not
modify anything in `models/` under any circumstances.

---

## Quick Launch

| What | How |
|---|---|
| **Whole stack** (recommended) | `NovaStart.cmd` → runs `nova_start.py` (llama.cpp + nova_chat + watcher + window) |
| **llama.cpp** (local inference) | `start_llama.cmd` (port 8080) |
| **nova_chat** (her interface) | `python general_tools/nova_chat/launch.py` (port 8765) |
| **Stop everything** | `StopNova.cmd` |

`nova_chat` opens at `http://127.0.0.1:8765` — a web group chat where Cole, Claude, Gemini,
and Nova collaborate. (The old `nova_qt` desktop app, `nova_gateway`/Discord, and OpenClaw
are all retired.)

---

## The Body / Tool Split (core principle — the "pluck-test")

`nova_body/` is **Nova** — her faculties, senses, memory, executive function, and her
autonomy on/off state. `general_tools/` are **detachable tools** she uses. Pull every tool
out and Nova is still herself; she only needs *a* comms tool to have a voice. The body never
depends on a specific tool.

---

## Workspace Layout

```
workspace/
├── SELF/                    ← Nova's reading set (auto-generated; do not hand-edit)
│   ├── core/                ← injected every turn: identity, how-I-work, body manifest, tools
│   └── reference/           ← on-demand: heartbeat, ncl_master, upgrade_protocol, manifest.json
│
├── nova_body/               ← Nova's faculties (the "her" that survives the pluck-test)
│   ├── nova_cortex/         ← executive.py (autonomy faculty), tasking.py (task board),
│   │                          nova_status.py, context_builder.py, rules.py, checkin.py
│   ├── nova_memory/         ← journal.py, log_reader.py, goals.py, state.py, session_store.py
│   ├── nova_logs/           ← unified logger — ALL log writes go here
│   ├── nova_motor/          ← hands.py, motor_cortex.py, tool_executor.py, verify.py
│   ├── nova_senses/         ← clock.py (chronoception), environment.py, eyes.py, vision.py
│   └── nova_config/         ← body-owned settings loader (reads nova_config.json)
│
├── nova_lancedb/            ← long-term semantic memory (LanceDB vector store)
│
├── general_tools/           ← detachable tools
│   ├── nova_chat/           ← group chat server (FastAPI + WebSocket, :8765) — her voice
│   ├── nova_sync/           ← watcher.py (GitHub auto-commit) + backup.py (Drive sync retired)
│   ├── build_manifest.py    ← derives SELF/ body manifest from @nova: tokens
│   ├── calls.py             ← call-graph generator feeding the manifest
│   ├── injector.py          ← NCL context injector / module dispatcher
│   ├── audit_scripts.py     ← workspace code-health audit
│   ├── download_models.py   ← one-time vision-model downloader
│   └── NovaLauncher.py      ← in-process launcher (called by nova_start.py)
│
├── memory/                  ← STATUS.md, JOURNAL.md, COLE.md, autonomy_state.json
├── Tasking/
│   ├── tasks.json           ← Nova's id-keyed task board (source of truth)
│   ├── priority.md          ← generated human view of the board
│   └── Master_Inbox/        ← NCL module responses land here
│
├── logs/
│   ├── chat_sessions/       ← nova_chat per-thread transcript JSONLs
│   ├── sessions/            ← nova_logs event logs by date/type
│   ├── gateway_sessions/    ← session JSONL history (legacy folder name)
│   └── proposed/            ← staged file edits awaiting Cole's review
│
├── _admin/                  ← planning docs + _archive_* (retired code/docs)
├── models/                  ← SEALED — weight files (GGUF). NEVER read, list, or open.
├── nova_config.json         ← local settings (inference / sessions / tool-exec limits)
├── nova_start.py            ← startup orchestrator (NovaStart.cmd runs this)
├── start_llama.cmd          ← launches llama-server with the dual-GPU split
└── prompt_cache/            ← llama.cpp KV cache files
```

---

## Key Config Files

| File | Purpose |
|---|---|
| `nova_config.json` | Local settings — inference window, session storage, tool-exec limits |
| `start_llama.cmd` | Launches llama-server.exe with dual-GPU tensor split (`-ts 16,24`) |
| `NovaStart.cmd` | Brings up the whole stack via `nova_start.py` |
| `StopNova.cmd` | Frees Nova's ports for a clean restart |

---

## Inference Stack

| Setting | Value |
|---|---|
| Server | `llama-server.exe` (CUDA) |
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
| GPU 1 | RTX 3090 24GB via OCuLink eGPU |
| Total VRAM | 40GB |
| Display | 17.3" 2560×1600 @ 240Hz |

---

## How Nova's Autonomy Works (short version)

When autonomy is ON, her executive faculty (`nova_cortex/executive.py`) wakes on a rhythm or
on a change, looks at her board, and decides freely — work a task, switch, create, abandon,
reprioritize, wait, or rest. On/off state lives in `memory/autonomy_state.json` (body-owned).
Cole is Priority 0: an interrupt she attends to first, never a leash. Full detail in
`SELF/reference/heartbeat.md`.

---

## Setup (fresh environment)

```powershell
pip install pyautogui pillow pywinauto watchdog anthropic httpx fastapi uvicorn websockets
```

Required environment variables: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`.
Run `start_llama.cmd` (or `NovaStart.cmd` for the whole stack). See `SELF/core/` for Nova's
operating knowledge.

---

## Where to Find Things

| Question | Answer |
|---|---|
| What is Nova working on right now? | `Tasking/tasks.json` (board) / `Tasking/priority.md` (readable view) |
| What's the current project state? | `memory/STATUS.md` |
| What are Nova's identity and rules? | `SELF/core/` |
| How does her autonomy work? | `SELF/reference/heartbeat.md` |
| What happened in past sessions? | `memory/JOURNAL.md` |
| What does every body part do? | `SELF/core/03_body_manifest.md` (auto-generated) |
| What's Nova's personality? | `SELF/core/01_identity.md` |
| Recent changes / handoff notes? | `_admin/` |
