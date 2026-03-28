# NOVA PROJECT PLAN
_Master planning document. Not for Nova to read. Lives in `_admin/`._
_Updated: 2026-03-28 | Maintained by: Cole + Cowork Claude_

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
**DELETED 2026-03-28 by Cole.** mentor.py has been replaced by nova_chat. No longer needed.

#### `tools/nova_chat/`
| File | Status | Notes |
|------|--------|-------|
| `server.py` | KEEP — core | Overhauled 2026-03-27/28: response queue, vision pipeline, rate limiter, /api/chat/recent |
| `launch.py` | KEEP | — |
| `session_manager.py` | KEEP | — |
| `transcript.py` | KEEP | Overhauled: catch-up context, directive redaction for Nova, image notation |
| `workspace_context.py` | KEEP | Excludes `_admin/` ✅ |
| `orchestrator.py` | KEEP | Role aliases (@mentor/@all), build_response_queue |
| `nova_bridge.py` | KEEP | Working: `[WRITE:]`, `[EXEC:]`, `[READ:]`, `[DISCORD:]`, `[PAUSE:]`, `[RESUME:]`. Discord dedup guard added 2026-03-28. |
| `clients/claude.py` | KEEP | Listener mode, vision support (Anthropic content blocks) |
| `clients/gemini.py` | KEEP | Listener mode, vision support (types.Part), client cache |
| `clients/nova.py` | KEEP | DIRECTIVE RULES in SYSTEM_PREFIX, vision support (Ollama image_url format) |
| `context_export.py` | KEEP | — |
| `check_keys.py` | KEEP | — |
| `static/index.html` | KEEP | @mentor/@all highlighting, role CSS classes |
| `server_runner.py` | KEEP | — |

#### `tools/nova_gateway/` (NEW — Phase 3 complete 2026-03-27)
| File | Status | Notes |
|------|--------|-------|
| `config.py` | KEEP | Reads `nova_gateway.json` |
| `context_builder.py` | KEEP | Injects workspace .md + Nova Chat context into system prompt |
| `session_store.py` | KEEP | JSONL v4 session storage, compaction |
| `tool_executor.py` | KEEP | exec/read/message/nova_chat tool dispatch |
| `agent_loop.py` | KEEP | Ollama inference loop. Cross-session context fetch (HTTP + JSONL fallback). |
| `discord_client.py` | KEEP | discord.py bot, on_disconnect handler |
| `scheduler.py` | KEEP | APScheduler cron, health check |
| `gateway.py` | KEEP | FastAPI entry point, port 18790. File logging added 2026-03-28 — writes to `logs/gateway/gateway-YYYY-MM-DD.log` (daily rotating, 7-day retention). |

#### `tools/` root additions (Nova.exe)
| File | Status | Notes |
|------|--------|-------|
| `NovaLauncher.py` | KEEP | pywebview desktop app launcher |
| `build_nova.py` | KEEP | PyInstaller build script → `_build/Nova/Nova.exe` |
| `nova_gateway_runner.py` | KEEP | CLI entry point: `python nova_gateway_runner.py` |
| `nova_gateway.json` | KEEP | Discord token, Ollama config, allowlist |

#### `_build/Nova/` (PyInstaller bundle)
| Path | Notes |
|------|-------|
| `_build/Nova/Nova.exe` | The runnable app |
| `_build/Nova/_internal/tools/` | **Duplicate of `tools/` — must be kept in sync manually** |

---

### OPEN BUGS

| # | Bug | Root cause | Fix |
|---|-----|-----------|-----|
| ~~B1~~ | ~~`ImportError: update_pulse`~~ | FIXED ✅ — session reset cleared stale compacted history | — |
| ~~B2~~ | ~~`ImportError: NovaWatcher`~~ | FIXED ✅ — same session reset | — |
| B3 | Chat log not rolling daily | BY DESIGN — per-thread intentional, see decision 2026-03-26 | N/A |
| B4 | `brain.py` is a stub | Not yet implemented | Phase 4 |
| ~~B5~~ | ~~`logger.py` may not write during agent runs~~ | RESOLVED ✅ — nova_logs/logger.py verified writing | — |
| B6 | Nova's vision/screenshot failures (`eyes.py`) | Indentation fixed but screenshot path may still be broken | Investigate in future session |
| B7 | Google Drive token expired | `nova_drive_token.json` needs re-authorization | Cole to re-auth manually |
| B8 | asyncio blocking in `claude.py` `stream_response` | `c.messages.stream()` is synchronous, blocks event loop | Documented TODO — low priority |
| ~~B9~~ | ~~`logs/gateway/` always empty — `_bg_gateway_error_watch` watching dead folder~~ | FIXED ✅ 2026-03-28 — `TimedRotatingFileHandler` added to `gateway.py`; logs now write to `logs/gateway/gateway-YYYY-MM-DD.log` | — |

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

### PHASE 3 — Infrastructure Rebuild ✅ FUNCTIONALLY COMPLETE (2026-03-27/28)
_eGPU not required for this phase. Only required before model rebuild (post Phase 3)._

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
- [x] **3.11** Live test: nova_gateway running, Discord bot connected, messages handled ✅
- [x] **3.12** Cron scheduler running, health checks firing ✅
- [ ] **3.13** Retire OpenClaw: `openclaw gateway stop`, remove from startup _(OpenClaw still installed — formal cutover pending)_
- [ ] **3.14** Run `python _admin/migrate_to_project_nova.py` → verify → remove old workspace _(in practice working from Project_Nova already)_
- [x] **3.15** `python tools/NovaLauncher.py` / `Nova.exe` — pywebview app window opens and works ✅
- [x] **3.16** `python tools/build_nova.py` → Nova.exe built and working ✅

### PHASE 3 ADDENDUM — nova_chat Overhaul ✅ (2026-03-27/28)

- [x] **3.A1** Mention system redesign: listener model, role aliases @mentor/@all, sequential queue
- [x] **3.A2** Response order: Claude → Gemini → Nova; each sees previous responses before generating
- [x] **3.A3** Nova smart escalation: scans own response for @mentions, triggers follow-up round
- [x] **3.A4** Catch-up context for Claude/Gemini: `--- MESSAGES SINCE YOUR LAST RESPONSE ---` block
- [x] **3.A5** Nova cross-session awareness: Discord agent fetches Nova Chat context (HTTP + JSONL fallback)
- [x] **3.A6** Nova rate-limit failsafe: 4 messages/60s max, resets on Cole sending any message
- [x] **3.A7** Nova.exe SyntaxError fixed: redundant `global is_processing` removed from `inject_message`
- [x] **3.A8** Vision/image support: full pipeline Claude (content blocks) + Gemini (Parts) + Nova (image_url)
- [x] **3.A9** Nova Discord loop fixed: directive redaction in transcript + SYSTEM_PREFIX guidance + dedup guard
- [x] **3.A10** @mentor/@all text highlighting in nova_chat UI
- [x] **3.A11** Two full code review passes across all subsystems (indentation, error handling, edge cases)

**Committed:** `e45a6e8` + `61b2ba6` + ongoing work in session — local only, not yet pushed to GitHub.

### PHASE 4A — Thoughts System, Nova Command Language & Module Architecture
_Full design: `_admin/PHASE4A_THOUGHTS_SYSTEM.md`_
_Prerequisite for Phase 4 — gives Nova persistent memory and autonomous task management before fine-tuning._

**PRIORITY 0 RULE (permanent, applies to all phases):**
Cole's word is absolute law. Nova stops everything and responds to Cole first, always.
Hardcoded in `Thoughts/priority.md`. To be added to `AGENTS.md` in 4A.2.

- [x] **4A.1** Surface scaffolding — `Thoughts/` directory structure, `priority.md` (with Priority 0), `THOUGHT_TEMPLATE.md`, design doc ✅ 2026-03-28
- [ ] **4A.2** Nova reads Thoughts — add `priority.md` + `THOUGHT_TEMPLATE.md` to inject_files; update `AGENTS.md` with Thoughts protocol and Priority 0 rule; update `TOOLS.md`
- [ ] **4A.3** Nova Command Language (NCL) parser — `nova_chat/nova_lang.py`; extend orchestrator.py with config-driven module registry; write `NCL_MASTER.md`
- [ ] **4A.4** Injector — `nova_gateway/injector.py`; reads `<<context_file.md>>`, boots module with injected context, routes output back to Nova Chat with Task ID echo
- [ ] **4A.5** Inbox routing — background task routes Nova Chat replies (with `[TASK_ID]` header) to `Thoughts/Master_Inbox/`; heartbeat cycle processes inbox, updates master.md
- [ ] **4A.6** Heartbeat upgrade — full autonomous cycle: read priority.md → process inbox → update thoughts → fire new module calls
- [ ] **4A.7** Vision module local-first — add moondream2 (Tier 2) and LLaVA 13B (Tier 3) to `nova_perception/eyes.py`; register `@eyes` as proper NCL module
- [ ] **4A.8** `brain.py` realization — replace stub with Thoughts cycle orchestrator (read priority → process inbox → determine next action)

### PHASE 4 — Nova's Native Intelligence
_Requires Phase 4A (persistent memory) before fine-tuning is meaningful._

- [ ] **4.1** `nova_core/brain.py` — realized via Phase 4A.8 (Thoughts orchestrator)
- [ ] **4.2** Full bidirectional `nova_status.json`
- [ ] **4.3** Fine-tuning pipeline on RTX 3090
- [ ] **4.4** Custom Modelfile rebuild post-eGPU
- [ ] **4.5** `/nova-trigger` endpoint
- [ ] **4.6** ThinkOrSwim automation (feeds into `@thinkorswim` module)

---

## QUICK REFERENCE

| What | Path / URL |
|------|-----------|
| Workspace root (Windows) | `[Project_Nova folder]\workspace` — wherever Cole placed the Project_Nova folder |
| Workspace root (Cowork mount) | `/sessions/sleepy-relaxed-gates/mnt/Project_Nova/workspace` |
| Nova's gateway session logs | `workspace/gateway_sessions/YYYY-MM-DD/<uuid>.jsonl` (nova_gateway agent runs) |
| Gateway log | `workspace/logs/gateway/gateway-YYYY-MM-DD.log` |
| Chat session logs | `workspace/logs/chat_sessions/*_chat.jsonl` |
| nova_chat URL | `http://127.0.0.1:8765` |
| nova_gateway URL | `http://127.0.0.1:18790` |
| Nova.exe | `_build/Nova/Nova.exe` |
| GitHub repo | `https://github.com/cklafou/nova-workspace` |
| Gemini Drive | `https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya` |
| Claude bootstrap | `https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md` |
| Cowork | Point Cowork at the Project_Nova folder for direct file access |
| **Bundle sync rule** | Any `tools/` change must also be applied to `_build/Nova/_internal/tools/` |

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
| 2026-03-27 | Listener model adopted for nova_chat | Claude + Gemini only respond when @mentioned; Nova is default. Cleaner, avoids all-AIs-at-once noise. |
| 2026-03-27 | Role aliases @mentor, @all | @mentor = Claude+Gemini; @all = everyone. Resolved to canonical order in orchestrator. |
| 2026-03-27 | Sequential response queue | Claude → Gemini → Nova order, not concurrent. Each AI sees prior responses. This is architecturally correct for coherence. |
| 2026-03-27 | Nova smart escalation | Nova reads her own response for @mentions, triggers follow-up round herself. One level only (no recursion). |
| 2026-03-27 | Nova.exe + PyInstaller | Unified app: pywebview + nova_chat + nova_gateway in one process. Bundle at `_build/Nova/`. |
| 2026-03-28 | Directive redaction in transcript | Nova's `[DISCORD:]` etc. replaced with human-readable notes when formatted for Nova's own context. Prevents pattern-match repeat. |
| 2026-03-28 | Discord dedup guard in nova_bridge | Same `[DISCORD:]` message blocked for 5 min. Belt-and-suspenders against loop even if model ignores instructions. |
| 2026-03-28 | Cross-session context: file fallback | `_fetch_nova_chat_context()` now has JSONL file fallback — always works regardless of nova_chat server state. |
| 2026-03-28 | Vision pipeline added | All 3 AIs now receive images from Cole's messages. Claude: content blocks. Gemini: Part.from_bytes. Nova: image_url. |
| 2026-03-28 | No Gemini-powered Cowork equivalent | Google's closest offering is Project Mariner (browser-only). No drop-in Cowork equivalent exists for Gemini. |
| 2026-03-28 | `tools/nova_advisor/` deleted | mentor.py fully replaced by nova_chat listener model. Folder removed by Cole. |
| 2026-03-28 | `tools/backups/` deleted | Redundant. logs/backups/ + GitHub + Google Drive provide sufficient redundancy. Removed by Cole. |
| 2026-03-28 | Three session stores, all intentional | `workspace/gateway_sessions/` = nova_gateway agent thought log (one JSONL per Discord/cron run). `workspace/logs/sessions/` = nova_logs structured event log (actions, errors, thoughts logged by Nova's tools). `workspace/logs/chat_sessions/` = nova_chat group chat transcript. Three different systems, three different purposes. |
| 2026-03-28 | workspace/sessions/ renamed to gateway_sessions/ | Avoids naming collision with logs/sessions/. config.py, nova_gateway.json, server.py fallback all updated. Bundle synced. |
| 2026-03-28 | Discord→Nova Chat consolidation fixed | `_build_discord_context_block()` added to server.py. Reads last 3 gateway_sessions JSONL files, injects "RECENT DISCORD ACTIVITY" block into ws_context for all AI responses in Nova Chat. Both directions now active. |
| 2026-03-28 | Filter bug fixed in _fetch_nova_chat_context | "(no active session)" was passing the filter and being returned as context, preventing file fallback. Now filtered alongside "(no messages yet)". |
| 2026-03-28 | Gateway file logging added | nova_gateway only logged to stdout; `logs/gateway/` was always empty. Fixed: `TimedRotatingFileHandler` added to `gateway.py`. Rolls daily, keeps 7 days. Both source and bundle synced. |
| 2026-03-28 | Priority 0 rule established | Cole's word is absolute law. Nova stops everything and responds to Cole first, always, on any surface. Hardcoded in Thoughts/priority.md. To be added to AGENTS.md in Phase 4A.2. |
| 2026-03-28 | Thoughts system designed | Persistent filesystem-based memory and task management for Nova. Replaces stateless per-run operation. See _admin/PHASE4A_THOUGHTS_SYSTEM.md for full design. |
| 2026-03-28 | Nova Command Language (NCL) designed | @ = module call, <<file>> = context injection, [[...]] = Nova instructions, ((...)) = completion criteria, ;; = parallel separator, :: = sequential pipe, **...** = emphasis, >>target = output routing, $$prev = previous output reference. Full spec in PHASE4A doc. |
| 2026-03-28 | Local-first module principle adopted | Every module must have a local solution (Ollama model) that is as good or better than API. APIs are fallbacks only. @eyes: moondream2 → LLaVA 13B → Claude Haiku. Applies to all future modules. |
| 2026-03-28 | brain.py purpose clarified | brain.py is not general intelligence code — it is the Thoughts cycle orchestrator: reads priority.md, processes Master_Inbox, determines next actions. Phase 4A.8. |

---
_Last updated: 2026-03-28 (session 3)_
_Next: Fix remaining bugs (nova_chat tool calls from Discord), then Phase 4A.2 (Nova reads Thoughts, Priority 0 in AGENTS.md). eGPU install pending vertical mount bracket._
