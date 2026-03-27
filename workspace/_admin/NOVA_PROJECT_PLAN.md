# NOVA PROJECT PLAN
_Master planning document. Not for Nova to read. Lives in `_admin/`._
_Updated: 2026-03-27 | Maintained by: Cole + Cowork Claude_

---

## HOW TO USE THIS DOCUMENT

This is the single source of truth for Project Nova's infrastructure rebuild.
Three sections:
1. **Workspace Audit** — what exists, what it does, what's broken, what's redundant
2. **OpenClaw Map** — every part of OpenClaw we depend on and what replaces it
3. **Rebuild Roadmap** — ordered checklist, check off as we go

When context resets, paste this document into the chat. It is the briefing.

---

## SECTION 1 — WORKSPACE AUDIT (current as of 2026-03-25)

### ROOT FILES

| File | Origin | What it does | Status |
|------|--------|--------------|--------|
| `AGENTS.md` | OpenClaw native, heavily customized | Behavioral rules, yield protocol, memory protocol, heartbeat rules, safety, Discord behavior | KEEP |
| `SOUL.md` | OpenClaw native, customized | Identity, personality, values, interests | KEEP |
| `TOOLS.md` | Custom built | Tool reference manual — packages, syntax, protocols, bootstrap URLs | KEEP — rewritten 2026-03-25 |
| `HEARTBEAT.md` | OpenClaw native | What to do on scheduled heartbeat pings | KEEP |
| `IDENTITY.md` | OpenClaw native | Name, vibe, goals, archetype, personality details | KEEP — overlaps SOUL.md intentionally (SOUL=values, IDENTITY=persona spec) |
| `USER.md` | OpenClaw native | Info about Cole for Nova | KEEP |
| `BOOTSTRAP.md` | OpenClaw native, customized | Session startup: read files, run rules.py, greet Cole | KEEP |
| `README.md` | Standard | Project overview | LOW PRIORITY |

---

### `_admin/` DIRECTORY (not visible to Nova)

| File | What it is |
|------|------------|
| `_admin/NOVA_PROJECT_PLAN.md` | This file |
| `_admin/passover/3 MAR 2026/` | Historical session notes moved from `logs/passover/` |

---

### `memory/` DIRECTORY

| File | What it does | Status |
|------|--------------|--------|
| `memory/STATUS.md` | Current project state, active goals | KEEP |
| `memory/JOURNAL.md` | Nova's session log, append-only | KEEP |
| `memory/COLE.md` | Living notes about Cole | KEEP |
| `memory/session_start.json` | Boot timestamp, read by checkin.py to filter old messages | KEEP — actively used |
| `memory/archive/archive_2026-02.md` | Archived old journal entries | KEEP |

---

### `logs/` DIRECTORY

| Path | What it contains | Status |
|------|-----------------|--------|
| `logs/chat_sessions/` | nova_chat session JSONL files | KEEP — active. Bug: not rolling to new daily file (0.8 pending) |
| `logs/sessions/` | Nova agent session logs from nova_memory.logger | KEEP — logger.py may not be writing during runs |
| `logs/proposed/` | Proposed changes staging area | KEEP — working |
| `logs/backups/sessions/` | Hourly session zips | KEEP — now clean (2 recent only) ✅ |
| `logs/backups/weekly/` | Weekly backup | KEEP |

**Cleaned up:**
- `logs/passover/` moved to `_admin/passover/` ✅
- `logs/autonomy_test.py` deleted ✅
- 30+ old session zips pruned ✅
- `tools/logs/` misplaced nova_thoughts.jsonl files gone ✅

---

### `skills/` DIRECTORY

**Deleted entirely 2026-03-23.** Was injecting a false capability map into Nova's system prompt every session via OpenClaw's skill loader (`formatSkillsForPrompt`), causing hallucinations. Nova was trying to use playwright, deepgram voice, and Zapier automation tools that don't exist in our stack.

Removed: `automation-workflows`, `discord-voice-deepgram`, `playwright-scraper-skill`, `github`

---

### `tools/` DIRECTORY

#### `tools/nova_sync/`
| File | Status | Notes |
|------|--------|-------|
| `watcher.py` | KEEP | Script only. **`NovaWatcher` class does not exist** — stale name from old version causes ImportError |
| `drive.py` | KEEP | Google Drive sync for Gemini |
| `backup.py` | KEEP | Session zip backups |
| `dir_patch.py` | REVIEW | Unclear active use |
| `FILE_INDEX.md` | KEEP — auto-generated | Do not edit manually |
| `FILE_INDEX_LINK.md` | KEEP — critical | Claude permanent bootstrap URL |
| `GEMINI_INDEX.md` | KEEP | Gemini index |

#### `tools/` root additions
| File | Status | Notes |
|------|--------|-------|
| `calls.py` | KEEP — NEW | Generates calls.md per package + Calls_Master_Index.md |
| `Calls_Master_Index.md` | AUTO-GENERATED | Cross-package call graph |
| `NovaChatLauncher.py` | KEEP — NEW | Source for NovaChatLauncher.exe |
| `build_launcher.py` | KEEP — NEW | Builds NovaChatLauncher.exe via PyInstaller |

#### `tools/nova_memory/`
| File | Status | Notes |
|------|--------|-------|
| `logger.py` | DELETED ✅ | Replaced entirely by `tools/nova_logs/logger.py` |
| `journal.py` | KEEP | Working correctly |
| `log_reader.py` | KEEP | Provides real session data |
| `status.py` | KEEP | Function is `update_status()`. **`update_pulse()` DOES NOT EXIST** — stale name causes ImportError |
| `state.py` | KEEP — needs update | ThinkOrSwim-focused. `build_context_snapshot()` pending addition from proposed refactor |

#### `tools/nova_logs/` (NEW 2026-03-26)
| File | Status | Notes |
|------|--------|-------|
| `logger.py` | KEEP — active | Unified logger. Sections: agent tools, chat thoughts, index writer |
| `Logger_Index.md` | AUTO-GENERATED | Updated by logger.py every 30s |
| `calls.md` | AUTO-GENERATED | Generated by tools/calls.py |

#### `tools/nova_core/`
| File | Status | Notes |
|------|--------|-------|
| `rules.py` | KEEP | Loaded every session via BOOTSTRAP.md |
| `checkin.py` | KEEP | Yield protocol, reads `memory/interrupt_inbox.json` |
| `brain.py` | STUB ONLY | Returns "standby" for everything. Not connected to anything. Phase 4 work |

#### `tools/nova_action/`
| File | Status | Notes |
|------|--------|-------|
| `hands.py` | KEEP | pyautogui — not in active use (ThinkOrSwim paused) |
| `autonomy.py` | KEEP — needs update | `evaluate_action()` pending integration from mentor.py refactor |
| `verify.py` | KEEP | Supports autonomy loop |

#### `tools/nova_perception/`
| File | Status | Notes |
|------|--------|-------|
| `eyes.py` | KEEP | pywinauto primary, Claude Haiku fallback |
| `vision.py` | KEEP | Vision wrapper |
| `explorer.py` | KEEP | pywinauto element finder, used by eyes.py |
| `vision_backup.py` | DELETED ✅ | Dead code from pre-pywinauto era |

#### `tools/nova_advisor/`
| File | Status | Notes |
|------|--------|-------|
| `mentor.py` | DEPRECATE | Replaced by nova_chat. Refactor approved. `build_context_snapshot()` written in `logs/proposed/nova_advisor_refactor.py`. Pending: `evaluate_action()` migration to autonomy.py, stub creation |

#### `tools/nova_chat/`
| File | Status |
|------|--------|
| `server.py` | KEEP — core |
| `launch.py` | KEEP |
| `session_manager.py` | KEEP |
| `transcript.py` | KEEP |
| `workspace_context.py` | KEEP — now excludes `_admin/` ✅ |
| `orchestrator.py` | KEEP |
| `nova_bridge.py` | KEEP — working (`[WRITE:]`, `[EXEC:]`, `[READ:]`) |
| `clients/claude.py` | KEEP |
| `clients/gemini.py` | KEEP |
| `clients/nova.py` | KEEP |
| `context_export.py` | KEEP |
| `check_keys.py` | KEEP |
| `static/index.html` | KEEP |
| `server_runner.py` | KEEP |

---

### OPEN BUGS

| # | Bug | Root cause | Fix |
|---|-----|-----------|-----|
| B1 | `ImportError: update_pulse` in gateway log | Stale function name in Nova's compacted session history | Reset OpenClaw session file |
| B2 | `ImportError: NovaWatcher` in gateway log | Same compacted session history | Same session reset |
| B3 | Chat log not rolling daily | `session_manager.py` doesn't create new file per day | Step 0.8 |
| B4 | `brain.py` is a stub | Not yet implemented | Phase 4 |
| B5 | ~~`logger.py` may not write during agent runs~~ | RESOLVED — nova_logs/logger.py verified writing correctly ✅ | — |

**Session reset command (stop OpenClaw first):**
```powershell
Remove-Item "C:\Users\lafou\.openclaw\agents\main\sessions\097d915a-e7c6-44df-af0e-ead44542bcec.jsonl"
```

---

## SECTION 2 — OPENCLAW MAP

| Component | We use it? | Replacement plan |
|-----------|------------|-----------------|
| Gateway daemon | YES | Phase 3: custom Python FastAPI daemon |
| Discord provider | YES | Phase 3: direct Discord.py |
| Cron scheduler | YES | Phase 3: Python APScheduler |
| Session storage | YES | Phase 3: unified JSONL store |
| Skill loader | WAS — now disabled (skills deleted) | REPLACED: `workspace_context.py` |
| Bootstrap file injection | YES | Phase 3: runtime injector in our own daemon |
| `read` tool | YES | Keep |
| `write` tool | AVOIDED | `nova_bridge.py` is the safe replacement |
| `exec` tool | YES | Keep for now |
| Canvas UI | NO | Replaced by nova_chat |
| WebSocket control API | NO | Policy 1008 blocks — not needed |
| Multi-surface session separation | YES — the core problem | Phase 3: unified session layer |

### OpenClaw files outside workspace

| Location | What it is |
|----------|------------|
| `C:\Users\lafou\.openclaw\agents\main\sessions\*.jsonl` | Nova's thought log per run |
| `C:\Users\lafou\.openclaw\cron\runs\*.jsonl` | Cron execution logs |
| `C:\Users\lafou\.openclaw\cron\jobs.json` | Scheduled job definitions |
| `C:\tmp\openclaw\openclaw-YYYY-MM-DD.log` | Gateway daemon log |
| `C:\Users\lafou\AppData\Roaming\npm\node_modules\openclaw\` | OpenClaw install — bundled skills to audit in Phase 2 |

---

## SECTION 3 — REBUILD ROADMAP

### PHASE 0 — Immediate Cleanup

- [x] **0.1** Delete `skills/automation-workflows/`
- [x] **0.2** Delete `skills/discord-voice-deepgram/`
- [x] **0.3** Delete `skills/playwright-scraper-skill/`
- [x] **0.4** Delete `skills/github/`
- [x] **0.5** Reset Nova's OpenClaw session file (fixes B1 + B2)
- [x] **0.6** ~~Find NovaWatcher caller~~ — covered by 0.5 session reset
- [x] **0.7** ~~Fix nova_thoughts.jsonl path~~ — already resolved, files gone
- [x] **0.8** Chat session log design confirmed — per-thread by design, not per-day
- [x] **0.9** Delete `nova_perception/vision_backup.py`
- [x] **0.10** Remove `logs/autonomy_test.py`
- [x] **0.11** Create `_admin/` directory
- [x] **0.12** Move passover files and planning docs to `_admin/`
- [x] **0.13** Add `_admin` to `workspace_context.py` SKIP_DIRS
- [x] **0.14** ~~mentor.py refactor~~ — CANCELLED, deprioritised
- [x] **0.15** Rewrite TOOLS.md — accurate, current, stale references fixed
- [x] **0.16** Logger verified writing to `logs/sessions/YYYY-MM-DD/` correctly

- [x] **0.17** Created `tools/nova_logs/` package — unified logger.py with all logging methods
- [x] **0.18** Created `tools/calls.py` — auto-generates calls.md per package + Calls_Master_Index.md
- [x] **0.19** Fixed all nova_* packages to import from `nova_logs.logger` (with nova_memory fallback)
- [x] **0.20** Gateway button in nova_chat — 🟢 Gateway On / 🔴 Gateway Off with start/stop
- [x] **0.21** Log dropdown — dark themed, human-readable names, noise filtered
- [x] **0.22** watcher.py --pup now supports .html files
- [x] **0.23** Update AGENTS.md — removed stale `session_status` ref, added nova_logs section, deleted nova_memory.logger references
- [x] **0.24** Update TOOLS.md — nova_logs package added, nova_memory.logger removed (file is deleted not deprecated)

### PHASE 1 — Visibility and State ✅ COMPLETE (2026-03-27)

- [x] **1.1** Create `nova_status.json` schema — defined in `nova_core/nova_status.py`
- [x] **1.2** Add writer to AGENTS.md — `nova_status.nova_status()` required at end of every agent run. Cole applied directly.
- [x] **1.3** Add reader to `server.py` — 30s background poll, injects summary silently into Nova's ws_context
- [x] **1.4** Gateway error detection — tails gateway log every 10s, broadcasts `gateway_error` WS event, calls `update_gateway()`
- [x] **1.5** Persistent Nova status bar in nova_chat UI — dot, label, pulse text, task, error, age display
- [x] **1.6** `[PAUSE: task]` and `[RESUME: task]` directives in nova_bridge.py
- [x] **1.7** `tasks/active.json` — simple task state tracking via `set_task()` / `clear_task()`

**Committed:** `510a32e` (Phase 1 code) + `4aaff91` (STATUS.md rewrite) — local only, not yet pushed

### PHASE 2 — Infrastructure Audit and Design ✅ COMPLETE (2026-03-27)
_eGPU not required for audit/design — only for Phase 3 build._

- [x] **2.1** Audit bundled OpenClaw skills in AppData — native skills inaccessible (outside mount), workspace skills already deleted in Phase 0. No action needed.
- [x] **2.2** Read OpenClaw source — session JSONL schema v3 fully mapped, tool list enumerated, compaction mechanism understood
- [x] **2.3** Document full dependency tree — see `_admin/PHASE2_ARCHITECTURE.md` Section 2
- [x] **2.4** Design replacement gateway — `nova_gateway/` package, 8-module design, see Section 3
- [x] **2.5** Design unified session layer — JSONL v4 format, date-organized, compaction via Nova-self or Gemini fallback
- [ ] **2.6** Architecture doc — **AWAITING COLE SIGN-OFF** → `_admin/PHASE2_ARCHITECTURE.md`

### PHASE 3 — Infrastructure Rebuild ⚙️ IN PROGRESS
_eGPU not required to build. Only required before 3.13 (cutover). Build and test first, cut over after eGPU._

- [x] **3.1** `nova_gateway/config.py` — settings loader (reads nova_gateway.json)
- [x] **3.2** `nova_gateway/context_builder.py` — workspace .md injector (replaces OpenClaw bootstrap)
- [x] **3.3** `nova_gateway/session_store.py` — JSONL v4 writer/reader/compaction
- [x] **3.4** `nova_gateway/tool_executor.py` — exec/read/message dispatch
- [x] **3.5** `nova_gateway/agent_loop.py` — Ollama inference + tool loop
- [x] **3.6** `nova_gateway/discord_client.py` — discord.py bot (replaces OpenClaw Discord provider)
- [x] **3.7** `nova_gateway/scheduler.py` — APScheduler cron (replaces OpenClaw cron)
- [x] **3.8** `nova_gateway/gateway.py` — FastAPI entry point (port 18790)
- [x] **3.9** Write `nova_gateway.json` config file (Discord token pre-filled)
- [x] **3.10** Update nova_chat `server.py` — port 18790 primary, 18789 legacy fallback; log path; sessions API
- [x] **3.10b** Nova dashboard — Chat/Dashboard tabs, status cards, gateway controls, manual trigger modal
- [x] **3.10c** `NovaLauncher.py` + `build_nova.py` — unified pywebview desktop app → Nova.exe
- [x] **3.10d** All hardcoded `.openclaw` paths → dynamic `Path(__file__)` (Project_Nova ready)
- [x] **3.10e** `_admin/migrate_to_project_nova.py` — one-shot migration script
- [ ] **3.11** Live test: `python nova_gateway_runner.py` → send Discord message → verify session written
- [ ] **3.12** Test: cron fires (30 min), health check completes, Discord message sent
- [ ] **3.13** Retire OpenClaw: `openclaw gateway stop`, remove from startup _(no eGPU required)_
- [ ] **3.14** Run `python _admin/migrate_to_project_nova.py` → verify → remove old workspace
- [ ] **3.15** `pip install pywebview` → `python tools/NovaLauncher.py` → verify app window opens
- [ ] **3.16** `python tools/build_nova.py` → Nova.exe built and working

**Committed:** `e45a6e8` (Phase 3 build) + `61b2ba6` (app + dashboard + migration) — local only.

### PHASE 4 — Nova's Native Intelligence

- [ ] **4.1** Implement `nova_core/brain.py`
- [ ] **4.2** Full bidirectional `nova_status.json`
- [ ] **4.3** Fine-tuning pipeline on RTX 3090
- [ ] **4.4** Custom Modelfile rebuild post-eGPU
- [ ] **4.5** `/nova-trigger` endpoint
- [ ] **4.6** ThinkOrSwim automation

---

## QUICK REFERENCE

| What | Path / URL |
|------|-----------|
| Workspace root | `C:\Users\lafou\.openclaw\workspace` |
| Nova's thought log | `C:\Users\lafou\.openclaw\agents\main\sessions\*.jsonl` |
| Session to reset | `C:\Users\lafou\.openclaw\agents\main\sessions\097d915a-e7c6-44df-af0e-ead44542bcec.jsonl` |
| Gateway log | `C:\tmp\openclaw\openclaw-YYYY-MM-DD.log` |
| nova_chat URL | `http://127.0.0.1:8765` |
| GitHub repo | `https://github.com/cklafou/nova-workspace` |
| Gemini Drive | `https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya` |
| Claude bootstrap | `https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md` |
| Claude Desktop Code tab | Point at `C:\Users\lafou\.openclaw\workspace` — can edit files directly, no --pup needed |

---

## HARDWARE

| Component | Spec |
|-----------|------|
| CPU | Intel Core i9-13900HX, 5.4GHz boost |
| Laptop GPU | RTX 4090 16GB GDDR6, 175W TGP |
| eGPU | EVGA RTX 3090 FTW3 Ultra 24GB GDDR6X |
| eGPU dock | MINISFORUM DEG1, Oculink PCIe 4.0 x4 |
| eGPU PSU | Corsair RM1000x 1000W |
| RAM | Up to 64GB DDR5 4800MHz |
| Storage | 1x NVMe 1.81TB (slot 2 free for Oculink adapter) |
| eGPU status | All parts in. Waiting on vertical GPU mount bracket before install |

---

## DECISIONS LOG

| Date | Decision | Reasoning |
|------|----------|-----------|
| 2026-03-23 | Delete all 4 skills | Injecting false capability map, causing hallucinations |
| 2026-03-23 | Build `nova_status.json` instead of using Skills | We already have a better system |
| 2026-03-23 | Keep OpenClaw, replace incrementally | Don't demolish before eGPU installed |
| 2026-03-23 | `_admin/` excluded from Nova's context | Planning docs not part of Nova's operational context |
| 2026-03-23 | Skills = muscle, tools = skeleton | Mental model confirmed, guides all future architecture |
| 2026-03-25 | Session reset to fix B1+B2 | Stale function names only in compacted history, not in any file |
| 2026-03-25 | TOOLS.md fully rewritten |
| 2026-03-26 | `nova_logs/` created as unified logging package | All loggers in one place, importable, auto-indexed |
| 2026-03-26 | Chat session logs are per-thread by design | Daily rollover would break session resume |
| 2026-03-26 | `calls.py` at tools/ root | Cross-package tool, each package stays self-contained for future OSS |
| 2026-03-26 | nova_memory/logger.py deleted (not deprecated) | Replaced entirely by nova_logs/logger.py |
| 2026-03-26 | NovaChatLauncher.exe = dumb wrapper only | All logic stays in launch.py; exe just calls it via subprocess |
| 2026-03-26 | Phase 1 injection = silent system prompt | Status data injected silently; Nova's voice used only for errors/completions |
| 2026-03-26 | Claude Desktop Code tab available | Can edit workspace files directly without --pup; use FILE_INDEX URL to bootstrap |
| 2026-03-27 | Phase 1 complete | All 7 tasks done — nova_status.py, status bar UI, bridge directives, server polling, gateway watcher |
| 2026-03-27 | STATUS.md fully rewritten | Was stale (2026-03-19, pre-package-restructure). Now accurate. NULL padding stripped. |
| 2026-03-27 | Cowork session established | Cowork Claude has direct file access + code execution on live PC files via mount |
| 2026-03-27 | Phase 2 audit + design complete | OpenClaw internals mapped, dependency tree documented, nova_gateway architecture drafted |
| 2026-03-27 | nova_chat bypasses OpenClaw confirmed | clients/nova.py talks directly to Ollama:11434 — OpenClaw only needed for Discord trigger path |
| 2026-03-27 | Session JSONL schema v3 mapped | type: session/message/compaction/tool_call. 39 active sessions, 85 reset. Compaction = summary + firstKeptEntryId |
| 2026-03-27 | nova_gateway design: 8 modules | context_builder, session_store, tool_executor, agent_loop, discord_client, scheduler, gateway. Port 18790. |
| 2026-03-27 | Phase 3 build complete (3.1–3.9) | nova_gateway package built, syntax-checked, smoke-tested. 2859 lines. Committed e45a6e8. |
| 2026-03-27 | eGPU gate removed from Phase 3 | Build doesn't require hardware. Only cutover (3.13) needs eGPU + model rebuild. |
| 2026-03-27 | nova_gateway.json written | Discord token pre-filled from openclaw.json. allowlist [] = responds to all channels. |

---
_Last updated: 2026-03-27_
_Next: Cole runs `pip install discord.py apscheduler` → test `--dry` run → live Discord test (3.11) → update nova_chat server.py (3.10)_
