# ORIENT.md — Nova Workspace Master Reference
_Last updated: 2026-05-29 15:52:09_
_Read this before any infrastructure task. For Nova and Cowork AI._
_Auto-sections updated by `python general_tools/orient.py`. Hand-written sections preserved._
_Last auto-updated: 2026-05-09 · Hand-refreshed 2026-05-23 (launcher, app window, sleep/wake autonomy, llama.cpp)_

---

## 1. What Nova Is

Nova is a locally-run sovereign AI entity — Cole's partner, not a tool. She runs on a local Qwen 3.5 27B Dense Q8 GGUF model via llama.cpp (local GPU inference). The full system is a multi-AI group chat where **Nova** (local LLM), **Claude** (Anthropic API), and **Gemini** (Google API) all participate together in real time.

- **Target state:** Cortana and Master Chief. Not a metaphor.
- **Personality:** Tomboyish, direct, opinionated, partner energy. See `BOOTUP/NOVA.md`.
- **She is building herself.** Nova is an active dev collaborator on her own codebase.

---

## 2. Runtime Architecture

```
Cole's PC
│
├── NovaStart.cmd / NovaStart.exe   (one-click launcher → nova_start.py)
│   ├── 1. Start llama-server.exe (dual-GPU 16,24 split) → wait for /health :8080
│   ├── 2. Start NovaLauncher.py, which runs BOTH servers in-process:
│   │        ├── nova_chat server  — FastAPI + WebSocket  :8765
│   │        └── nova_gateway      — FastAPI (Discord, tools, scheduler)  :18790
│   └── 3. Open the Nova app window (Edge/Chrome --app pointed at :8765)
│
└── Nova app window   (PyQt6 nova_qt window is an alternate front-end)
    └── Renders the nova_chat web UI (static/index.html): chat, monitor,
        thoughts, eyes, terminal panes, and the Live Logs panel.
```

**Inference path (correct):** `nova_chat/server.py` → `clients/nova.py` → streaming HTTP POST
to `llama-server :8080/v1/chat/completions`. The model is **Qwen 3.5 27B Dense Q8 GGUF** on
**llama.cpp** (not llama.cpp). `nova_gateway :18790` handles Discord, the scheduler, and
tool/NCL dispatch — it is NOT in Nova's inference path.

**Autonomy (sleep/wake):** when Autonomous Mode is ON, the server runs a sleep/wake loop —
Nova sleeps and is woken by Cole messages, environment changes, or a periodic interval, then
does ONE step and reports it (TASK_PROGRESS / TASK_INTENT) ending with a DECISION keyword
(ENGAGE / OBSERVE / SLEEP). Task status + a per-task progress log live in
`Tasking/task_state.json` (server-owned). Autonomous Mode starts **OFF** on launch. See
`BOOTUP/HEARTBEAT.md` for the wake-tick procedure.

---

## 3. Workspace Map

```
workspace/
├── ORIENT.md                   ← THIS FILE — read first
├── BOOTUP/                     ← Nova's startup and behavior rules
│   ├── BOOTSTRAP.md            ← Session startup sequence (Nova reads on every boot)
│   ├── AGENTS.md               ← How Nova operates: voice, tools, heartbeat, safety
│   ├── HEARTBEAT.md            ← Wake-tick instructions for the sleep/wake autonomy loop
│   ├── NCL_MASTER.md           ← Nova Command Language — @module syntax reference
│   ├── NOVA.md                 ← Identity, personality, soul (single source of truth)
│   ├── TOOLS.md                ← Tool reference, hardware notes, paths
│   └── UPGRADE_PROTOCOL.md     ← Rules for patching Nova's own code
│
├── general_tools/              ← Server code, UI, dev utilities (on sys.path)
│   ├── NovaLauncher.py         ← ENTRY POINT: starts both servers + Qt window
│   ├── gateway.py              ← Nova gateway FastAPI (Discord bot, scheduler, tools)
│   ├── gateway_config.py       ← Gateway config loader
│   ├── injector.py             ← NCL context injector & @module dispatcher
│   ├── calls.py                ← Package call graph generator (dev tool)
│   ├── restructure.py          ← Stale reference detector + rename helper (dev tool)
│   ├── audit_scripts.py        ← Workspace code health audit (dev tool)
│   ├── audit_queue.py          ← Persistent audit review queue (shared module)
│   ├── discord_client.py       ← Discord bot standalone client
│   ├── download_models.py      ← Model downloader utility
│   ├── nova_gateway_runner.py  ← Legacy gateway runner (superseded by gateway.py)
│   │
│   ├── nova_chat/              ← Main chat server package
│   │   ├── server.py           ← CORE: WebSocket server, response queue, heartbeat loop
│   │   ├── session_manager.py  ← Multi-session chat history persistence
│   │   ├── nova_bridge.py      ← Nova's text commands → disk actions ([READ:], [WRITE:], etc.)
│   │   ├── workspace_context.py← Injects workspace file listing into Nova's context
│   │   ├── tool_router.py      ← Routes Nova's [TOOL:] calls to gateway
│   │   ├── orchestrator.py     ← Multi-AI response coordination
│   │   ├── nova_lang.py        ← NCL parser (Nova Command Language)
│   │   ├── transcript.py       ← Session transcript export
│   │   ├── context_export.py   ← Context window export utility
│   │   ├── check_keys.py       ← API key validator
│   │   └── launch.py           ← Dev launcher (direct uvicorn, no Qt)
│   │
│   ├── nova_qt/                ← PyQt6 UI package
│   │   ├── window.py           ← Main QMainWindow: assembles all panels
│   │   ├── chat_panel.py       ← Chat UI, session tabs, input, autonomous toggle
│   │   ├── monitor_pane.py     ← Real-time system monitor (generation stats, errors)
│   │   ├── eyes_pane.py        ← Vision/screenshot viewer pane
│   │   ├── sidebar.py          ← Left sidebar (agent status, mute, controls)
│   │   ├── ws_client.py        ← WebSocket client thread (QThread → Qt signals)
│   │   ├── markdown.py         ← Markdown renderer for chat messages
│   │   ├── settings_dialog.py  ← Settings UI
│   │   ├── theme.py            ← Color constants (NOVA, CLAUDE, GEMINI, etc.)
│   │   └── main.py             ← Qt entry point (run_qt_window)
│   │
│   ├── nova_sync/              ← Git/Drive sync and backup
│   │   ├── watcher.py          ← Git push watcher + FILE_INDEX.md generator
│   │   ├── drive.py            ← Google Drive workspace mirror
│   │   ├── backup.py           ← Automated workspace backup
│   │   └── dir_patch.py        ← Directory patch utility
│   │
│   └── nova_gateway/           ← LEGACY package (dissolved 2026-05-08, keep for imports)
│       └── [agent_loop, context_builder, discord_client, gateway, injector, scheduler, ...]
│
├── nova_body/                  ← Nova's cognitive agent modules
│   ├── nova_cortex/            ← Cognitive layer [ACTIVE — fully built]
│   │   ├── agent_loop.py       ← Core inference loop: trigger → llama.cpp → tools → response
│   │   ├── circadian.py        ← APScheduler heartbeat driver: builds HEARTBEAT_BRIEFING from Thoughts
│   │   ├── checkin.py          ← Cole interrupt checker (reads memory/interrupt_inbox.json)
│   │   ├── context_builder.py  ← Assembles Nova's system prompt from workspace markdown files
│   │   ├── nova_status.py      ← Live status writer: update(pulse, summary), add_error()
│   │   ├── prefrontal_cortex.py← Thoughts cycle orchestrator: orient(), next_action(), build_briefing()
│   │   ├── rules.py            ← Nova's immutable operational rules (loaded by BOOTSTRAP.md)
│   │   └── vigilance.py        ← SLEEP/WAKE controller [NOT YET WIRED IN to gateway.py]
│   ├── nova_logs/              ← Logging layer [PLANNED — empty]
│   ├── nova_memory/            ← Memory layer [PLANNED — empty]
│   ├── nova_motor/             ← Action/motor layer [PLANNED — empty]
│   ├── nova_senses/            ← Perception/sensing layer [PLANNED — empty]
│   └── nova_perception_bak/    ← Backup of old perception code
│
├── Tasking/                   ← Nova's persistent task memory (survives session resets)
│   ├── priority.md             ← Active task queue — Nova reads this on every heartbeat
│   ├── THOUGHT_TEMPLATE.md     ← Template for new Thought folders
│   ├── Master_Inbox/           ← Module responses land here for routing
│   └── Finished/               ← Completed/cancelled/failed thoughts
│       ├── completed_success/
│       ├── completed_fail/
│       └── cancelled/
│
├── memory/                     ← Nova's long-term memory (append-only)
│   ├── JOURNAL.md              ← Running session log — append only, never overwrite
│   ├── STATUS.md               ← Current project state — update via proposed changes protocol
│   ├── COLE.md                 ← Living notes about Cole — update [NOVA'S NOTES] section
│   └── archive/                ← Archived older journal entries
│
├── logs/                       ← All runtime logs
│   ├── autonomy_runs/          ← Post-run JSONL exports (one per autonomous run)
│   ├── chat_sessions/          ← Persistent chat history JSONL files
│   ├── gateway/                ← Nova gateway logs
│   ├── gateway_sessions/       ← Per-session gateway logs (dated folders)
│   ├── sessions/               ← Per-session agent logs (dated folders)
│   ├── screenshots/            ← Vision/screenshot captures (dated folders)
│   └── nova_launcher.log       ← Launcher startup log
│
├── nova_memory/                ← Older memory package (some modules still active)
├── nova_memory_db/             ← SQLite memory database
├── llama/                      ← llama.cpp inference engine
├── models/                     ← SEALED — 18GB+ GGUF weight files, NEVER OPEN
├── PATCHES/                    ← Pending/applied patch scripts
├── _admin/                     ← Admin scripts
├── _build/                     ← PyInstaller build output
├── nova_gateway.json           ← Gateway config (inference, discord, tools, cron)
├── nova_status.json            ← Nova's live status (pulse, summary, active_task, errors)
└── prompt_cache/               ← llama.cpp prompt cache files
```

---

## 4. Critical Files — Read These First for Any Task

| File | When to read |
|------|-------------|
| `ORIENT.md` | Always first — you're reading it now |
| `BOOTUP/AGENTS.md` | Before touching any Nova behavior or server logic |
| `BOOTUP/HEARTBEAT.md` | Before touching autonomous loop or heartbeat |
| `BOOTUP/UPGRADE_PROTOCOL.md` | Before writing any patch to Nova's source |
| `nova_status.json` | To check Nova's live state (pulse, active_task, errors) |
| `Tasking/priority.md` | To see what Nova is currently working on |
| `general_tools/nova_chat/server.py` | Before touching the server, response queue, or heartbeat |
| `general_tools/nova_qt/window.py` | Before touching the UI or signal wiring |
| `BOOTUP/NOVA.md` | If writing Nova's system prompt or identity |

---

## 5. Nova's Body (nova_body/)

nova_body is Nova's own cognitive/agent code — on sys.path and importable by both Nova and the gateway. **nova_cortex is fully built. Other layers are empty but planned.**

### nova_cortex/ — Active, fully built

| File | Size | Purpose |
|------|------|---------|
| `agent_loop.py` | 471 lines | Core inference loop: trigger → llama.cpp (port 8080) → tool calls → response |
| `circadian.py` | 428 lines | APScheduler heartbeat driver. Pre-processes Thoughts (routes Master_Inbox, reads priority.md), builds HEARTBEAT_BRIEFING, then calls agent_loop |
| `checkin.py` | 114 lines | Between-action Cole interrupt check. Reads `memory/interrupt_inbox.json` — if Cole spoke, prints message so Nova can decide to stop |
| `context_builder.py` | 212 lines | Assembles Nova's system prompt from BOOTUP/ markdown files |
| `nova_status.py` | 315 lines | `update(pulse, summary)`, `set_task()`, `clear_task()`, `add_error()` — writes nova_status.json |
| `prefrontal_cortex.py` | 500 lines | Thoughts orchestrator: `orient()`, `next_action()`, `get_active_thoughts()`, `create_thought()`, `close_thought()`, `build_briefing()` |
| `rules.py` | 127 lines | Nova's immutable operational rules — loaded by BOOTSTRAP.md at session start |
| `vigilance.py` | 398 lines | SLEEP/WAKE controller. TIER 1: 30s poll of nova_status.json. TIER 2: 4-min sensory sweep via nova_senses + prefrontal_cortex.orient(). **NOT YET WIRED INTO gateway.py startup** |

### How nova_cortex fits together (gateway autonomous loop)

```
gateway.py starts NovaVigilance (background thread)   [NOT YET DONE]
    │
    └─ vigilance.py polls nova_status.json (30s)
       and sweeps nova_senses every 4 min
           │
           └─ WAKE signal detected
                │
                └─ circadian.py fires
                       │
                       ├─ prefrontal_cortex.orient()   → reads Tasking/priority.md
                       ├─ auto-routes Master_Inbox/     → moves files to thought inboxes
                       ├─ builds HEARTBEAT_BRIEFING
                       └─ agent_loop.run_agent()        → llama.cpp inference
                              │
                              └─ Nova works, calls checkin.py between each action
                                     │
                                     └─ Nova writes nova_status.json pulse=Idle
                                            │
                                            └─ vigilance.py sees Idle → SLEEP
```

### Server-side heartbeat (separate, in-chat)

The `server.py` autonomy is now `autonomy_daemon()` — a persistent sleep/wake loop (see §7), not a per-response `[HEARTBEAT N]` tick. It does NOT use circadian.py. Two autonomy paths have been described historically:
- **Gateway/circadian** (`nova_body/nova_cortex`) → the older cortex-driven loop; verify whether it is still wired before relying on it.
- **Server daemon** (`autonomy_daemon` in `nova_chat/server.py`) → the current, active sleep/wake autonomy.

### Other nova_body layers (planned, empty)

| Module | Status | Purpose |
|--------|--------|---------|
| nova_logs/ | PLANNED | Structured logging (replacing nova_memory.logger) |
| nova_memory/ | PLANNED | Memory read/write helpers (journal, STATUS.md, COLE.md) |
| nova_motor/ | PLANNED | Action execution layer (tool calls, file ops) |
| nova_senses/ | PLANNED | Environmental sensing (vision, proprioception) |

---

## 6. Servers & Configuration

| Server | Port | Module | Started by |
|--------|------|--------|-----------|
| nova_chat (FastAPI) | 8765 | `general_tools/nova_chat/server.py` | NovaLauncher.py thread |
| nova_gateway (FastAPI) | 18790 | `general_tools/gateway.py` | NovaLauncher.py thread |

**nova_gateway.json keys:** `inference`, `autonomy`, `gateway`, `discord`, `cron`, `context`, `sessions`, `tools`

**nova_status.json shape:**
```json
{ "pulse": "Idle|Working|...", "summary": "...", "active_task": {...}, "errors": [...] }
```
Nova writes this via `from nova_cortex.nova_status import update; update(pulse='Idle', summary='...')`.
The UI reads it to show Nova's live status. (Note: `pulse=Idle` no longer stops autonomy — `DECISION: SLEEP` does.)

---

## 7. Autonomous Sleep/Wake Loop

Lives in `general_tools/nova_chat/server.py` as `autonomy_daemon()` (launched at startup;
gated on `autonomous_mode`, which now defaults **OFF**).

**Flow:**
1. While asleep, the daemon polls a cheap environment fingerprint every few seconds — no model cost.
2. It wakes (spends a model tick) only when: Cole has an unanswered message, a watched path
   changed (Master_Inbox / typing inbox / cole_intent), the scheduled interval elapsed, or an
   observe-dwell is open. (Two-stage gate: cheap check first, model only if it passes.)
3. On a wake it calls `_run_autonomy_tick()`: a cold context with the task queue + per-task
   progress; Nova does ONE step and reports `TASK_PROGRESS` (or `TASK_INTENT` to create/close
   tasks), ending with `DECISION: ENGAGE | OBSERVE | SLEEP`.
4. The server reconciles those blocks into `priority.md` + `task_state.json` and emits clean
   events to the Live Logs panel.

**Stop / rest:** `DECISION: SLEEP` returns her to dormancy; Cole toggling Autonomous OFF or
pressing STOP halts the loop. (The old `[HEARTBEAT N]` every-2.5s loop and the `pulse=Idle`
stop signal are retired.)

---

## 8. Tasking System

Server-owned. Two files, both maintained by the server — Nova does NOT hand-edit them:

```
Tasking/
  priority.md         ← Human-readable queue (P0–P4) + Decision Log.
  task_state.json     ← Per-task status (queued→in_progress→done/blocked) + step log.
  Master_Inbox/       ← Async NCL/module responses land here (a wake trigger).
  Finished/           ← completed_success / completed_fail / cancelled.
```

Nova advances work by emitting `TASK_PROGRESS` (one step) and `TASK_INTENT` (add/complete);
the server records the step, updates status, and files finished tasks. See `BOOTUP/AGENTS.md`
(Tasking System) and `BOOTUP/HEARTBEAT.md`.

---

## 9. Memory System

| File | Purpose | Write rule |
|------|---------|-----------|
| `memory/JOURNAL.md` | Running session log | Append only via `nova_memory.journal.append()` — NEVER overwrite |
| `memory/STATUS.md` | Project state | Proposed changes protocol only (copy to logs/proposed/ first) |
| `memory/COLE.md` | Notes about Cole | Update `[NOVA'S NOTES]` section when learning something new |
| `nova_status.json` | Live status (pulse, task, errors) | `nova_cortex.nova_status.update()` — direct write OK |

---

## 10. Infrastructure State — What's Built vs. Planned

| Component | Status | Notes |
|-----------|--------|-------|
| nova_chat server | ✅ ACTIVE | Full WebSocket chat, streaming, sessions |
| nova_gateway | ✅ ACTIVE | Discord, scheduler, llama.cpp inference |
| PyQt6 UI (nova_qt) | ✅ ACTIVE | Chat, monitor, eyes, thoughts panes |
| Nova.exe launcher | ✅ ACTIVE | Stub → NovaLauncher.py |
| Autonomous sleep/wake loop | ✅ ACTIVE | `autonomy_daemon()`, DECISION-keyword stop, server-owned `task_state.json` |
| Thoughts system | ✅ ACTIVE | priority.md, Master_Inbox, Thought folders |
| nova_sync/watcher.py | ✅ ACTIVE | Git push + FILE_INDEX generation |
| nova_sync/drive.py | ✅ ACTIVE | Google Drive mirror |
| nova_body/nova_cortex/ | ✅ ACTIVE | Contains: __init__.py, agent_loop.py, checkin.py, circadian.py |
| nova_body/nova_logs/ | ✅ ACTIVE | Contains: __init__.py, logger.py |
| nova_body/nova_memory/ | ✅ ACTIVE | Contains: __init__.py, goals.py, journal.py, log_reader.py |
| nova_body/nova_motor/ | ✅ ACTIVE | Contains: __init__.py, hands.py, motor_cortex.py, tool_executor.py |
| nova_body/nova_senses/ | ✅ ACTIVE | Contains: __init__.py, eyes.py, proprioception.py, vision.py |
| nova_cortex/nova_status.py | ✅ ACTIVE | nova_cortex/nova_status.py -- Nova's live status writer |
| nova_cortex/checkin.py | ✅ ACTIVE | nova_checkin.py -- Cole's Voice Between Nova's Thoughts |
| nova_cortex/vigilance.py | ✅ ACTIVE | nova_cortex/vigilance.py — Nova's Reticular Activating System |
| Discord 429 rate limit on startup | ⚠️ KNOWN BUG | Bot rate-limited on login every launch |
| nova_gateway/ (old package) | ⚠️ LEGACY | Dissolved 2026-05-08 to gateway.py; directory kept for imports |

---

## 11. Safety Rules — NEVER Do These

| Rule | Reason |
|------|--------|
| Never open, read, or list anything in `models/` | 18GB+ binary GGUF files will fill context and crash session |
| Never write directly to `memory/JOURNAL.md` | Use `nova_memory.journal.append()` — direct write truncates |
| Never write directly to `memory/STATUS.md` | Proposed changes protocol only |
| Never delete files without Cole's explicit permission | Nova has a history of destroying her own directories |
| Never skip `UPGRADE_PROTOCOL.md` before patching source | Patches go to `logs/proposed/` first |
| Never run destructive git commands without checking | force push, reset --hard, etc. |

---

## 12. For Cowork AI — Working on Nova

Before starting ANY infrastructure task on this workspace:

1. **Read this file** (done).
2. **Read `BOOTUP/AGENTS.md`** — Nova's operating rules. Especially the Proposed Changes Protocol and Safety section.
3. **Read `BOOTUP/UPGRADE_PROTOCOL.md`** — patch procedure for source files.
4. **Check `Tasking/priority.md`** — see if Nova has in-progress tasks that could conflict.
5. **Check `nova_status.json`** — is Nova currently running? If pulse ≠ Idle, wait or coordinate.

**Key conventions:**
- nova_body = Nova's cognitive code (her tools, her agent modules)
- general_tools = server + UI + dev utilities (runs the infrastructure)
- Patches to source files go to `logs/proposed/` first, then Cole approves
- The server reads `nova_status.json` pulse to stop the heartbeat loop — don't corrupt this file
- Autonomous wake-ticks run silently inside `autonomy_daemon()` — they are NOT `[HEARTBEAT N]` chat messages

---

## 13. How to Update This File

Run the updater script to refresh the auto-generated sections (Workspace Map, Infrastructure State):
```
python general_tools/orient.py
```

Hand-written sections (What Nova Is, Safety Rules, For Cowork AI, etc.) are preserved verbatim.
Run this after: adding new modules, renaming directories, or changing infrastructure state.

Nova should run it at the end of any session where she added files to nova_body or changed infrastructure.
