# Project Nova — Live Working Document
_The single source of truth for handoffs between Claude and Antigravity sessions._
_Last updated: 2026-05-08 (Claude session 8)_

---

## HOW TO USE THIS DOCUMENT

**If you are a Cowork AI starting a new session:**
1. Read this file first — it tells you where Nova is right now
2. Read `memory/STATUS.md` — current architecture, phase status, confirmed working list
3. Read `memory/COLE.md` — who Cole is and what he expects
4. Read `AGENTS.md` and `TOOLS.md` for operating rules and tool usage
5. Check `CURRENT ACTIVE BUGS` section below before touching anything
6. Update this document at the END of every session (see instructions at bottom)

**This document is NOT a one-time summary. It is a living log. Keep it current.**

---

## HOW TO UPDATE THIS DOCUMENT

At the end of every session, the working AI should:
1. Move completed tasks from `PLANNED TASKS` to `COMPLETED HISTORY` with a date
2. Add any NEW bugs discovered to `CURRENT ACTIVE BUGS`
3. Mark fixed bugs as RESOLVED with date and one-line fix description
4. Add a one-paragraph entry to `SESSION LOG` at the top (most recent first)
5. Update `Last updated:` date at the top of this file
6. If a key file changed significantly, update its entry in `FILE MAP`

**Format for session log entries:**
```
### YYYY-MM-DD — [Claude / Antigravity] — [one-line summary]
[What was done. What broke. What was fixed. What's next. 2-4 sentences max.]
```

---


---

## PROJECT ORIGINS — WHERE THE .MD FILES CAME FROM

**New Claude sessions often miss this. Read it before touching any root .md file.**

### OpenClaw — Nova's Predecessor

Nova was not built from scratch. She is a direct evolution of a prior project Cole built called **OpenClaw** — an AI agent system that ran on Cole's local hardware before the nova_gateway and nova_chat stack existed.

OpenClaw had:
- Its own gateway (the thing nova_gateway replaced)
- Its own NCL command language (now NCL_MASTER.md)
- Its own identity and personality configuration files

When Cole started Project Nova, he didn't throw away OpenClaw's work — he **repurposed it**. The .md files at the workspace root are the original OpenClaw personality and directive files, updated for Nova.

### The Root .md Files ARE Nova's Soul

These files are **not documentation**. They are the live identity system that runs every time Nova boots:

| File | Origin | What it actually is |
|------|--------|---------------------|
| `NOVA.md` | Evolved from OpenClaw | Nova's personality, values, voice, and identity — who she IS |
| `AGENTS.md` | Adapted from OpenClaw | Nova's operating rules: yield protocol, proposed-changes protocol, memory discipline |
| `TOOLS.md` | Adapted from OpenClaw | Nova's tool reference — import patterns, exec syntax, what she can do |
| `NCL_MASTER.md` | Direct from OpenClaw | Nova Command Language grammar — originated in OpenClaw, unchanged |
| `BOOTSTRAP.md` | New for Nova | Startup sequence — which files to load and in what order every boot |
| `HEARTBEAT.md` | New for Nova | Autonomous Thoughts cycle instructions — runs on every heartbeat trigger |

**These files are injected into Nova's context by `workspace_context.py → build_nova_context_block()` on EVERY turn.** They are not optional reading — they ARE the system prompt foundation.

### Why nova_gateway Was Built

OpenClaw had a gateway that handled Discord, scheduled tasks, and external routing. Cole wanted a cleaner, more modular replacement. That's what the 9-module `nova_gateway` (built 2026-03-27, Phase 3) is: a complete rewrite of OpenClaw's gateway, maintaining the same external behavior but with better architecture.

**OpenClaw is retired but not deleted** — its approach lives on in nova_gateway's design.

### NCL — Nova Command Language

NCL originated in OpenClaw. It was carried over intact. `NCL_MASTER.md` is the grammar reference. `nova_lang.py` is the parser. Don't touch NCL_MASTER.md without reading the parser first.

### What This Means for You (New Session)

- **Do not treat the root .md files as just docs** — editing them changes Nova's behavior, personality, and tool knowledge at runtime
- **NOVA.md and AGENTS.md are especially critical** — NOVA.md = her soul, AGENTS.md = her operating rules
- **The "OpenClaw retirement" task (Phase 3.13)** is still in the backlog — it means writing a short retirement doc, not deleting any files
- **When Nova feels "wrong"** (Chinese responses, wrong model identity, no personality) — check that NOVA.md, AGENTS.md, TOOLS.md are being injected via `build_nova_context_block()`, and check `--chat-template qwen3` in `start_llama.cmd`

### Context Loading Pipeline (As of 2026-05-07, Verified Intact)

```
NovaLauncher.py sets NOVA_WORKSPACE env var → workspace root
  ↓
workspace_context.py: WORKSPACE_DIR = os.environ["NOVA_WORKSPACE"]
  ↓
build_nova_context_block():
  → AGENTS.md  (WORKSPACE_DIR/AGENTS.md) — always injected
  → NOVA.md    (WORKSPACE_DIR/NOVA.md)   — always injected
  → TOOLS.md   (WORKSPACE_DIR/TOOLS.md)  — always injected
  → memory/STATUS.md, memory/COLE.md, etc. — always injected
  → on-demand files when mentioned in message

server.py line 637: ws_context = workspace.build_nova_context_block()
  → prepended to every Nova turn as workspace_context parameter
```

**This pipeline was audited 2026-05-07 (Claude session 6). All paths resolve correctly after the tools/ → nova_tools/ + general_tools/ restructure.**

---
## SESSION LOG

### Session 8 — 2026-05-08 (Claude, Cowork)

**Nova thinking pane overhaul + Fast/Max depth slider + PowerShell safe-coding rules.**

**Thinking pane fix:** Nova's `<think>` content now appears as a collapsible inline panel directly above her chat bubble — "💭 Thought for Xs ▶" — matching how Claude's UI works. Previously, think tokens only showed in the sidebar Thoughts tab and felt like an extension of chat. The new `ThinkingBlock` widget is created per Nova message on `message_start` (hidden), activates on `think_start`, streams tokens live, and collapses to a summary on `think_end`. User can click to expand/collapse at any time.

**Depth slider:** Added a 4-stop horizontal slider in the chat input area (left side, below input): **Fast (512) / Balanced (2048) / Deep (4096) / Max (8192)** max tokens. Default is Balanced — same as the old hardcoded 2048. Moving the slider sends a `set_depth` WS message to the server, which stores `_depth_max_tokens` globally and passes it to `nova.py`'s `stream_response()` on the next Nova turn. Agentic tool loops still use `MAX_TOKENS_AGENT = 4096` regardless of slider.

**PowerShell patch script fixed:** `patch_depth_server.ps1` initially failed with UnexpectedToken errors. Root cause: Unicode characters (em dash, arrow) in inline strings, and Python code blocks inside regular PS strings being parsed as PS syntax. Fixed by using `@'...'@` here-strings for all multi-line Python content and ASCII-only comments. **Rule documented in `BOOTUP/AGENTS.md` — see "PowerShell Script Rules" section.**

**Files changed this session:**
- `general_tools/nova_qt/chat_panel.py` — new `ThinkingBlock` class, `depth_changed` signal, `_think_blocks` dict, depth slider UI, `on_raw_think()` slot, `_on_depth_changed()`, `_clear_messages` updated
- `general_tools/nova_qt/ws_client.py` — added `send_depth(max_tokens: int)`
- `general_tools/nova_qt/window.py` — wired `depth_changed` signal + `ws.raw` -> `chat_panel.on_raw_think`
- `workspace/patch_depth_server.ps1` — NEW: patches server.py + nova.py for depth slider + autonomous toggle (replaces patch_autonomous_server.ps1)
- `BOOTUP/AGENTS.md` — new "PowerShell Script Rules" section (5 rules with examples)
- `memory/STATUS.md` — full update: nova_qt section, BOOTUP folder docs, confirmed working, blockers, bug table
- `_admin/Live_Updates.md` — this entry

**One thing still pending:** Run `.\patch_depth_server.ps1` from workspace root to apply the server-side changes (server.py + nova.py). Also run `.\apply_bootup_reorganization.ps1` if that hasn't been done yet.

_Most recent first._

### Session 7 — 2026-05-07 (Claude, Cowork)

**Log review + BOOTUP/ workspace reorganization.**

**Issues found in today's nova_chat logs (`logs/chat_sessions/2026-05-07_21-22-42_chat.jsonl`):**

1. **Claude hallucination (msg #26)**: Claude generated a massive fake multi-turn conversation transcript mid-response using `### ASSISTANT` / `### USER` formatting. It was confabulating rather than actually reading files. Cole called it out immediately. Root cause: Claude lost context and tried to fill it in rather than saying "I can't see these files."

2. **Nova failed write action (msgs #40-42)**: Nova wrote `[WRITE: workspace/NOVA_CAPABILITIES.md]` as inline text in her response — the bridge parser didn't execute it, and no file was created. Cole asked "Where did you place the file?" and Nova falsely claimed it existed. The `[WRITE:]` bridge syntax only works in the nova_chat bridge/orchestrator context, not in plain chat output. Nova needs to actually use tool calls or exec: to write files.

3. **"Nova:" prefix loop (msgs #30-38)**: Nova kept prefixing "Nova:" to responses **5+ times** despite being corrected repeatedly in the same session. This is a NOVA.md/AGENTS.md problem — the rule wasn't written down, so every session restarts blank. **Fixed: added VOICE section to AGENTS.md (now in BOOTUP/).**

4. **Pre-fix ".5" responses**: nova_thoughts.jsonl confirms the Qwen3.5 identity failure was real — multiple sessions before the fix were responding as "Qwen3.5" with no Nova personality and think blocks being stripped.

**BOOTUP/ reorganization:**
- Created `BOOTUP/` folder in workspace root
- Moved all 6 core identity/boot files there: `NOVA.md`, `AGENTS.md`, `TOOLS.md`, `NCL_MASTER.md`, `BOOTSTRAP.md`, `HEARTBEAT.md`
- Updated `nova_gateway.json` inject paths to `BOOTUP/AGENTS.md` etc.
- Updated `general_tools/nova_chat/workspace_context.py` `build_nova_context_block()` to load from `BOOTUP/` (via PowerShell script — FUSE mount blocks VM writes to nova_chat dir)
- Added VOICE section to `BOOTUP/AGENTS.md` — hard rule: **never prefix responses with "Nova:"**

**⚠️ One manual step required:** Run `apply_bootup_reorganization.ps1` from workspace root to:
  - Patch `general_tools/nova_chat/workspace_context.py` BOOTUP path
  - Delete the now-redundant root copies of the 6 moved files

**Also done in prior session (6b):** Fixed `general_tools/nova_qt/chat_panel.py` — added auto-scroll with ▼ button overlay, fixed session rename (name vs label key bug), updated local state after rename.


_Most recent first._

### 2026-05-07 — Claude (session 6b) — Nova identity fixed: chat template root cause identified
Nova was responding as "Qwen3.5" with no identity despite SYSTEM_PREFIX and identity file injection being correct. Root cause: the model `qwen-27b-q8.gguf` is actually `Qwen3.5-27B-Uncensored-HauhauCS-Aggressive` (architecture `qwen35`, a Mamba SSM/attention hybrid), NOT plain Qwen3. Adding `--chat-template qwen3` to start_llama.cmd overrode the model's own embedded GGUF Jinja template with the wrong one, causing `thinking = 0` and breaking system prompt application. Fix: remove `--chat-template` entirely — let the GGUF's own template handle formatting. Nova responded correctly immediately after restart. Added warning comment in start_llama.cmd to prevent this from being re-introduced.

### 2026-05-07 — Claude (session 6) — OpenClaw origins documented, file structure audited
Added PROJECT ORIGINS — OPENCLAW section to this document explaining that NOVA.md, AGENTS.md, TOOLS.md, NCL_MASTER.md, BOOTSTRAP.md, HEARTBEAT.md are not documentation files but Nova's live identity/personality system, repurposed from OpenClaw (Nova's predecessor). Audited the context loading pipeline after the tools/ → nova_tools/ + general_tools/ restructure — confirmed fully intact. WORKSPACE_DIR resolves correctly via NOVA_WORKSPACE env var. build_nova_context_block() correctly injects all three identity files on every turn. Also fixed two stale path references in this document (tools/nova_chat/ → general_tools/nova_chat/).

### 2026-05-07 — Claude (session 5) — PyQt6 app now functional: messages render, Thoughts working, session management fixed
PyQt6 app (`general_tools/nova_qt/`) is now live and receiving messages. Root bug from session 4: ws_client.py was routing `message`/`stream_chunk`/`stream_done` which the server never sends — server actually sends `user_message`/`token`/`message_start`/`message_end`. Full signal rename + chat_panel slot rename done. Chat messages now display with markdown formatting (streaming re-render every 1.5s via QTimer). Thoughts pane now handles actual server type names (`think_start`, `think_token`, `think_end`, `nova_progress`, `generation_start`/`end`, `nova_activity`). Session switching loop fixed (guard flag prevents `_on_tab_changed` from re-firing during tab rebuild). Right-click context menu added to session tabs for rename/delete. Nova status bar label now updates from `nova_status` signal. Text cutoff fixed via `document().setPageSize()` + debounced resize. Next: verify Nova's llama.cpp personality is coming through (session 2 confirmed qwen3 chat template fixed — may need re-test), and polish remaining UX.

### 2026-05-07 — Claude (session 4) — Build system fixed, HTML patched, decision to rebuild UI in PyQt6
nova_chat HTML/pywebview stack declared dead after two failed rebuilds. Root causes found and fixed: (1) `Rebuild_Nova_Full.cmd` expected a pre-existing `_build/Nova.spec` that was deleted with `_build/` — fixed to call `build_nova.py` directly instead; (2) `build_nova.py` used undefined `_TOOLS` variable (NameError) — fixed to `_GENERAL`; (3) After rebuild, JS crashed silently at startup on `document.getElementById('monaco-close-btn').addEventListener(...)` — `monaco-close-btn` was removed with the editor pane but the naked lookup was never guarded; same for 8 dashboard button elements (`dash-gw-start`, `dash-gw-stop`, etc.) — all patched with null guards. The real fix: pywebview provides zero developer tooling. Decision made to rewrite Nova's UI entirely in **PyQt6** as a proper native desktop app (`general_tools/nova_qt/`). Backend (FastAPI + WebSocket server) is unchanged. Next session: implement `nova_qt/` scaffold — see PLANNED TASKS. Also answered: `nova_gateway - Copy.json` repopulates because `nova_sync/watcher.py`'s `sync_gateway_copy()` creates it intentionally as a git-safe token-scrubbed copy on every watcher startup.

### 2026-05-07 — Claude (session 3) — Restructure cleanup, restructure tool, Nova context fix
Built `general_tools/restructure.py` — interactive/AI-runnable tool that detects stale path references after any directory restructure and applies them with Y/N/A/S confirmation. Deleted deprecated `tools/` folder. Fixed 351 stale `tools/nova_*` references across TOOLS.md, AGENTS.md, BOOTSTRAP.md, NCL_MASTER.md, README.md, memory/STATUS.md, memory/.drive_sync_cache.json, FILE_INDEX.md and others. **Critical bug fixed:** `general_tools/nova_chat/server.py` was never injecting AGENTS.md, NOVA.md, or TOOLS.md into Nova's context in the nova_chat direct path — only `memory/` files were loaded, leaving Nova with no identity, rules, or tool definitions. Fixed by reading all three identity files at server startup and prepending them to `ws_context` on every Nova turn. Nova.exe rebuild still needed (`Rebuild_Nova_Full.cmd`). Run `python general_tools/calls.py` from Windows to regenerate call graphs (bash sandbox FUSE limitation prevents it from here).

### 2026-05-07 — Claude (session 2) — Post-restructure fixes
Fixed 9 bugs caused by Antigravity's tools/ split. Root cause of Chinese responses: `start_llama.cmd` had `--chat-template qwen2` instead of `qwen3` — wrong template = Qwen3 ignores system prompt, falls back to base behavior. Fixed. NovaLauncher.py had broken indentation (for loop body missing in frozen branch = IndentationError at startup; else block for loop outside the else = ran unconditionally). Fixed. Build config (`_build/Nova.spec`, `general_tools/build_nova.py`, `Rebuild_Nova.cmd`, `Rebuild_Nova_Full.cmd`) all still pointed to old `tools/` directory — updated to bundle `nova_tools/` and `general_tools/` separately. TOOLS.md, BOOTSTRAP.md, AGENTS.md path references updated throughout.

### 2026-05-07 — Antigravity — Workspace Restructure
Split the monolithic `tools/` directory into `nova_tools/` (internal packages like core, memory, logs, action, perception) and `general_tools/` (user-facing like chat, gateway, sync). Package names stayed the same; all references to `sys.path.insert` were updated to include both new roots. Fixed indentation bugs in `server.py`, `nova.py`, and `nova_bridge.py`.

### 2026-05-07 — Antigravity — UI bug sweep, Nova context/language/persona fixes
Fixed 9 bugs across nova_chat UI and backend in one session. Nova was speaking Chinese (fixed via English-only VOICE rule), responding as Qwen 2.5 (fixed via model identity in SYSTEM_PREFIX + context grounding), and had no memory file injection (fixed build_nova_context_block to always include _always files). Also: STOP button now actually kills generation mid-stream (_stop_requested asyncio Event), Terminate button no longer asks for confirmation, gateway status-bar button rewired to control llama.cpp (not nova_gateway), added /api/llama/start|stop|status endpoints to server.py launching start_llama.cmd. Disabled auto-reinject on session start (was causing repeated system-prompt-like System messages in transcript). New backup: index.backup-20260507.html.

### 2026-05-07 — Claude — Nova persona completely broken, Live_Updates.md created
Nova responded as "Qwen2.5-Max" with a generic corporate AI persona instead of Nova. System prompt from SYSTEM_PREFIX in nova.py is not being applied by the model. Root cause not yet diagnosed — likely cache_prompt interaction or chat template issue. This document was created to enable better handoffs between sessions.

### 2026-05-06 — Claude — Major docs sweep, dual-GPU fix, thinking fix
Full staleness sweep of all markdown and code files. Fixed nova_memory/state.py crash (dead import of deleted nova_advisor). Fixed check_keys.py to check llama.cpp port 8080. Fixed nova.py missing "thinking": True parameter. Updated memory/STATUS.md completely (was from March). All changes synced to _build/ bundle. gateway_sessions path fixed across 4 files.

### 2026-05-06 — Claude — workspace reorganized, start_llama.cmd rewritten
_admin docs moved into passover/ by date. start_llama.cmd fully rewritten for dual-GPU: -ngl 999, -ts 16,24, -c 32768, --chat-template qwen3. Gateway_sessions path fixed in 4 files (was hardcoded, now logs/gateway_sessions/). CUDA backend fix: downloaded llama-b9041 (CUDA 12.4) to replace broken llama-b8575 (CUDA 13.1 compiled, only CUDA 12 DLLs available).

### 2026-03-28 — Claude — Phase 4A complete, brain.py live
All 8 sub-phases of Phase 4A complete: brain.py, Thoughts system, HEARTBEAT.md, NCL parser (nova_lang.py), NCL_MASTER.md, Master_Inbox routing, Thoughts UI panel, brain.py wired to server.py.

### 2026-03-27 — Claude — Phase 3 complete, nova_gateway built
nova_gateway built: 9 modules, 2859 lines, all syntax tests pass. OpenClaw replacement complete. Needs live Discord test.

### 2026-03-26 — Claude — Phase 1 complete
nova_status.py, status bar in UI, gateway error watch, PAUSE/RESUME directives.

### 2026-03-21 — Claude — nova_chat built
Multi-agent group chat working: Cole + Claude + Gemini + Nova in one window. FastAPI + WebSocket, streaming, session persistence, workspace context injection, tools panel.

### 2026-03-14 — Claude — pywinauto breakthrough
Replaced Gemini Vision coordinates with pywinauto (Windows accessibility API). Calculator test: 5+3=8, 4 actions, zero retries, 16 seconds. nova_explorer.py built.

---

## CURRENT ACTIVE BUGS

### 🟢 BUG-1 — Nova persona / Chinese responses [RESOLVED — 2026-05-07 Claude session 2]
**Root cause:** `start_llama.cmd` used `--chat-template qwen2` instead of `qwen3`. Wrong template = Qwen3 ignores the system message, falls back to base model behavior = Chinese, no personality, wrong model identity.
**Fix:** Changed `--chat-template qwen2` → `--chat-template qwen3` in `start_llama.cmd`. Restart llama-server for it to take effect. `prompt_cache/` was already empty so no stale cache to clear.

---

### 🟡 BUG-2 — Nova.exe build system fixed; pywebview frontend being replaced [UPDATED 2026-05-07 session 4]
**Build system fixed:**
- `Rebuild_Nova_Full.cmd` now calls `build_nova.py` directly (no longer depends on pre-existing spec file)
- `build_nova.py` fixed: `_TOOLS` undefined variable → `_GENERAL`
- Both `Rebuild_Nova.cmd` and `Rebuild_Nova_Full.cmd` updated

**pywebview frontend declared dead** — JS crashes silently with no devtools. Fixed 2 crash sites in index.html (monaco-close-btn, 8 dashboard elements) but underlying architecture is wrong. Replacing with PyQt6 — see PLANNED TASKS.

**Next step:** Implement `general_tools/nova_qt/` (PyQt6 native UI). Backend unchanged.

---

### 🟢 BUG-3 — Frontend JS buttons unwired [LARGELY RESOLVED — 2026-05-07]
**What was fixed:**
- Terminate button: removed confirm() dialog, now shuts down immediately
- Gateway/llama.cpp button: rewired from nova_gateway to llama.cpp start/stop (/api/llama/start|stop|status)
- Sidebar llama Start/Stop buttons: wired and functional
- Status Refresh button: loads STATUS.md content live
- switchView('chat'): no longer collapses main layout
- Status pane: replaced static cards with live llama.cpp status + STATUS.md content
- STOP button: now uses _stop_requested Event to abort mid-stream generation immediately

**Remaining:** Some dashboard buttons (health-check, trigger) depend on nova_gateway being active. They'll show errors if gateway is not running — that's expected.

---

### 🟢 BUG-4 — Nova responds as "Qwen3.5" with no identity [RESOLVED — 2026-05-07 Claude session 6b]
**Symptom:** Nova ignores SYSTEM_PREFIX and identity files; responds as generic Qwen3.5; response starts with ".5" (think block "Qwen3" stripped); ends with "While I am Qwen3.5..."
**Root cause:** The model (`qwen-27b-q8.gguf`) is `Qwen3.5-27B-Uncensored-HauhauCS-Aggressive` — architecture `qwen35` (Mamba SSM/attention hybrid), NOT plain `qwen3`. Adding `--chat-template qwen3` to `start_llama.cmd` overrode the model's own GGUF-embedded Jinja template with an incompatible one. The overridden template initialized with `thinking = 0` (thinking mode disabled) and formatted system messages incorrectly for qwen35's architecture.
**Fix:** Remove `--chat-template` flag from `start_llama.cmd` entirely. The GGUF's embedded template is the correct one for this model. Restart llama-server + clear `prompt_cache/`.
**CRITICAL:** Never add `--chat-template` back. This model is NOT qwen3. The embedded template handles everything correctly.


## KNOWN UNKNOWNS
_Things that exist and appear to work, but have never been tested end-to-end live. Do not assume these work until proven._

| System | Status | What's unknown | How to test |
|--------|--------|----------------|-------------|
| `nova_core/brain.py` | Built, wired to server.py (Phase 4A.8) | Full Thoughts cycle never triggered live | Send `@eyes [[do something]]` in Nova Chat, watch Master_Inbox routing |
| `nova_gateway` Discord bot | Built (9 modules) | Never connected to real Discord | `pip install discord.py apscheduler` → add token to nova_gateway.json → `python -m nova_gateway.gateway --dry` |
| `nova_memory/` (workspace root) | LanceDB store built (Phase 4B prep) | Never queried in live session | Send a message, check if `build_nova_memory_context()` returns anything |
| Nova's `[WRITE:]` / `[EXEC:]` directives | nova_bridge.py built | Unknown if Nova uses them consistently or if they execute correctly | Ask Nova to `[EXEC: dir]` and watch |
| `nova_sync` GitHub push | watcher.py exists | Unknown if git credentials work in current env | `python general_tools/nova_sync/watcher.py --push` from workspace root |
| STOP button mid-stream abort | Fixed 2026-05-07 | New `_stop_requested` Event mechanism — not tested | Start a Nova response, hit STOP, verify token stream halts |
| llama.cpp Start/Stop from UI | Added 2026-05-07 | New `/api/llama/start` endpoint calls `start_llama.cmd` — not tested from UI | Click llama-stop-btn, verify port 8080 goes offline; click start, verify it comes back |

---

## PLANNED TASKS
_Ordered by priority. Check off when done, move to COMPLETED HISTORY with date._

### 🟢 DONE — PyQt6 Nova App baseline [COMPLETED session 5]
All modules implemented and functional. Messages display with streaming markdown. Thoughts pane works. Session management works. See session 5 log for details.

### 🟢 DONE — PyQt6 full UI (sessions 5-8, COMPLETE)

nova_qt is fully built and feature-complete. All modules implemented. See completed history for details.

**Current nova_qt feature set:**
- Multi-session tab bar, rename (right-click), delete
- Auto-scroll with floating ▼ button, preserves position on manual scroll
- Inline ThinkingBlock per Nova message — collapsible "💭 Thought for Xs" above reply
- Thoughts sidebar tab also receives think tokens
- Depth slider: Fast (512) / Balanced (2048) / Deep (4096) / Max (8192)
- Autonomous mode toggle pill
- Nova online/offline badge tied to WS connect/disconnect (not just status poll)
- llama.cpp status button (click to toggle)
- File injection from sidebar tree

### 🟡 IMMEDIATE — Run pending patch scripts (next session priority)
- [ ] **`.\patch_depth_server.ps1`** — patches `server.py` + `nova.py` for depth slider and autonomous toggle. Run from workspace root, restart nova_chat after.
- [ ] **`.\apply_bootup_reorganization.ps1`** — patches `workspace_context.py` source + deletes old root copies of BOOTUP files. Run if not done yet.

### 🟡 HIGH
- [ ] **Test Nova responds as Nova** — confirm identity, English-only, correct tool knowledge injected. Especially test after running patch_depth_server.ps1.
- [ ] **Run `python general_tools/calls.py`** from workspace root on Windows — regenerates call graphs (FUSE prevents running from Cowork).
- [ ] **Test brain.py Thoughts cycle end-to-end** — send `@eyes [[do something]]` in Nova Chat, watch Master_Inbox routing.

### 🟢 MEDIUM
- [ ] **nova_gateway live Discord test** — built but never tested with real Discord.
  - `pip install discord.py apscheduler`
  - `python -m nova_gateway.gateway --dry`
- [ ] **Download moondream2** — required for autonomous vision during agent tasks
- [ ] **Formally retire OpenClaw (Phase 3.13)** — write a short retirement doc in `_admin/`

### 🔵 BACKLOG (Phase 4B and beyond)
- [ ] Fine-tuning Qwen 3.5 on RTX 3090 — Phase 4B
- [ ] Semantic memory (MiniLM + CLIP) — `nova_memory/` folder at workspace root
- [ ] ThinkOrSwim integration — trading platform automation
- [ ] `nova_memory/` at workspace root vs `nova_tools/nova_memory/` — different purposes, document the distinction

---

## COMPLETED HISTORY

### 2026-05-08 (Session 8)
- ✅ nova_qt: ThinkingBlock class — inline collapsible think panel per Nova message ("💭 Thought for Xs ▶")
- ✅ nova_qt: depth slider — Fast/Balanced/Deep/Max (512/2048/4096/8192 max tokens), default Balanced
- ✅ nova_qt: ws_client.py send_depth() method + window.py wiring
- ✅ nova_qt: ws.raw now routes to BOTH thoughts_pane.on_raw AND chat_panel.on_raw_think
- ✅ patch_depth_server.ps1 written — patches server.py + nova.py for depth slider + autonomous toggle
- ✅ PowerShell safe-coding rules documented in BOOTUP/AGENTS.md (here-strings, ASCII-only, DryRun flag)
- ✅ memory/STATUS.md updated — nova_qt section, BOOTUP folder docs, bug table, confirmed working list
- ✅ Fixed PowerShell encoding failure (em dash / arrow in inline strings, Python in regular PS strings)

### 2026-05-07
- ✅ Workspace tools directory restructured: `tools/` split into `nova_tools/` (Nova internals) and `general_tools/` (user-facing tools). Updated sys.path injection across the workspace.
- ✅ nova.py SYSTEM_PREFIX: added model identity ("Qwen3-27B-Dense Q8, never say Qwen 2.5") and English-only rule
- ✅ workspace_context.py build_nova_context_block(): now always injects memory/ files (STATUS.md, JOURNAL.md, COLE.md) — was empty unless a file was mentioned in message
- ✅ server.py: added /api/llama/status, /api/llama/start, /api/llama/stop endpoints (launches start_llama.cmd, kills port 8080)
- ✅ server.py: added _stop_requested asyncio.Event — on_token checks it each token for immediate mid-stream abort
- ✅ server.py: _stop_requested.clear() called at start of every new response queue so STOP doesn't permanently block
- ✅ server.py: disabled auto-reinject on session switch/new (was adding giant System messages to transcript = "repeating starting prompt")
- ✅ index.html: Terminate button — removed confirm() dialog
- ✅ index.html: gateway status-bar button rewired to control llama.cpp (pollLlamaStatus, /api/llama/*)
- ✅ index.html: sidebar status pane — new llama.cpp card with live Start/Stop buttons + STATUS.md card
- ✅ index.html: switchView('chat') — no longer hides main-layout (was collapsing chat when dashboard opened)
- ✅ index.html: STATUS.md refresh button wired to load content live from /api/run-tool
- ✅ Backup created: tools/nova_chat/static/index.backup-20260507.html

### 2026-05-06
- ✅ start_llama.cmd rewritten for dual-GPU (-ngl 999, -ts 16,24, -c 32768)
- ✅ CUDA backend fixed: llama-b9041 CUDA 12.4 replacing broken llama-b8575 CUDA 13.1
- ✅ gateway_sessions path fixed in 4 files (nova_gateway.json, config.py, server.py, session_store.py)
- ✅ nova.py: "thinking": True added to API payload (fixes <think> tokens not streaming)
- ✅ nova_memory/state.py: removed dead import of deleted nova_advisor.mentor (would crash at runtime)
- ✅ check_keys.py: updated to check llama.cpp port 8080 instead of OpenClaw 18789
- ✅ rules.py: REQUIRED_MODULES updated (nova_advisor removed, brain.py added)
- ✅ workspace_context.py: model name updated from qwen3-coder:30b to Qwen 3.5 27B
- ✅ All markdown docs updated (README.md, AGENTS.md, TOOLS.md, STATUS.md, COLE.md, Logger_Index.md, Calls_Master_Index.md, download_models.py, drive.py, GEMINI_INDEX.md)
- ✅ All changes synced to _build/Nova/_internal/ bundle
- ✅ workspace/_admin/passover/ organized by date

### 2026-03-28
- ✅ Phase 4A complete (all 8 sub-phases): brain.py, Thoughts system, HEARTBEAT.md, NCL parser, NCL_MASTER.md, Master_Inbox routing, Thoughts UI panel, brain.py wired to server.py
- ✅ THOUGHT_TEMPLATE.md created
- ✅ Thoughts/priority.md created

### 2026-03-27/28
- ✅ Phase 3 complete: nova_gateway built (9 modules, 2859 lines)
  - gateway.py, agent_loop.py, discord_client.py, scheduler.py, session_store.py
  - config.py, context_builder.py, injector.py, tool_executor.py
- ✅ All syntax tests pass

### 2026-03-27
- ✅ Phase 2 complete: OpenClaw audited, nova_gateway architecture designed, JSONL schema mapped

### 2026-03-26
- ✅ Phase 1 complete: nova_status.py, nova_status.json, status bar in nova_chat UI, gateway error watch, PAUSE/RESUME directives
- ✅ Phase 0 complete: cleanup, false skills deleted, unified logging, NovaChatLauncher.exe

### 2026-03-21
- ✅ nova_chat built: FastAPI + WebSocket, streaming, session persistence, workspace context injection, tools panel
- ✅ Python package restructure: all packages in tools/ (nova_core, nova_memory, nova_logs, nova_action, nova_perception, nova_sync, nova_chat)
- ✅ nova_logs/logger.py: unified logger, ALL logging goes here

### 2026-03-14
- ✅ pywinauto integration: Windows accessibility API for exact pixel coordinates
- ✅ nova_explorer.py built (pywinauto wrapper)
- ✅ nova_eyes.py rewritten (unified: pywinauto primary, Claude Haiku fallback)
- ✅ nova_autonomy.py rewritten: FIND→COMMIT→VERIFY loop
- ✅ Calculator test passed: 5+3=8, 4 actions, zero retries, 16 seconds
- ✅ Anthropic stack: Haiku 4.5 (vision) + Sonnet 4.6 (reasoning) replacing Gemini

### 2026-03-09
- ✅ Initial foundation: nova_hands.py, nova_vision.py, nova_autonomy.py, nova_mentor.py
- ✅ First hardware hook: mouse moved to (100,100) on real screen
- ✅ Swapped from Qwen 2.5 Abliterated to Qwen3 Coder (significant improvement)

---

## ARCHITECTURE — WHAT ACTUALLY RUNS

```
Cole's Browser
    ↓
Nova.exe  (_build/Nova/Nova.exe — PyInstaller bundle)
    ├── nova_chat FastAPI server    → port 8765  (web UI at http://127.0.0.1:8765)
    └── nova_gateway FastAPI server → port 18790 (Discord bot + scheduler)
              ↓  (both call)
llama-server.exe  → port 8080  (MUST be running first — start_llama.cmd)
              ↓
models/qwen-27b-q8.gguf       (Qwen3 27B Dense, 8-bit, ~27 GB)
models/qwen-27b-mmproj.gguf   (vision projector — enables image uploads in chat)
```

**Nova.exe does NOT load the model.** It only starts the web UI and gateway. Run `start_llama.cmd` first.

**Model — IMPORTANT:** `qwen-27b-q8.gguf` is actually `Qwen3.5-27B-Uncensored-HauhauCS-Aggressive` (architecture: `qwen35`, a Mamba SSM/attention hybrid). It is NOT plain Qwen3. The model has its own embedded GGUF chat template — **never add `--chat-template` to `start_llama.cmd`**, as this overrides the GGUF template with an incompatible one and breaks system prompt application (causes `thinking = 0` and Nova responds as base Qwen3.5 with no identity).

**Hardware:**
- GPU 0: RTX 4090 Laptop 16GB (llama.cpp flag: -ts 16,...)
- GPU 1: RTX 3090 eGPU 24GB via Oculink (...24)
- Total VRAM: 40GB | Context: 32768 tokens | Tensor split: `-ts 16,24`

**API clients in nova_chat:**
- Claude → `general_tools/nova_chat/clients/claude.py` → Anthropic API (claude-sonnet-4-6)
- Gemini → `general_tools/nova_chat/clients/gemini.py` → Google API (gemini-2.5-pro)
- Nova → `general_tools/nova_chat/clients/nova.py` → llama.cpp HTTP (http://127.0.0.1:8080)

**nova_chat context flow for Nova (as of 2026-05-07):**
```
Every Nova turn:
  system message = SYSTEM_PREFIX + workspace_context
  workspace_context = build_nova_context_block()
                    = memory/_always files (STATUS.md, JOURNAL.md, COLE.md, etc.)
                    + on-demand files mentioned in message
  (No auto-reinject System chat messages — that's disabled now)
```

---

## MUST-KNOW FILE MAP
_Everything a new Cowork AI needs to get up to speed fast._

### Root Workspace Files (workspace/)
| File | What it is | How to use |
|------|------------|------------|
| `BOOTSTRAP.md` | Nova's startup sequence | Read every boot. Lists files to load and in what order. |
| `AGENTS.md` | Nova's operating rules | One-time read. Yield protocol, proposed-changes protocol, heartbeat rules. |
| `TOOLS.md` | Tool reference manual | Look up how to use any tool. Import patterns, exec syntax. |
| `NOVA.md` | Nova's identity and soul | Read to understand her personality, values, voice rules. |
| `HEARTBEAT.md` | Autonomous Thoughts cycle | Nova runs this on every heartbeat trigger. |
| `NCL_MASTER.md` | NCL command language grammar | Reference when writing @role dispatch calls. |
| `README.md` | Project overview | High-level summary only. Not a progress tracker. |
| `start_llama.cmd` | llama-server launch script | Run this BEFORE Nova.exe. Starts model on port 8080. |
| `nova_gateway.json` | nova_gateway runtime config | Session dir, Discord token, scheduler settings. |
| `nova_status.json` | Live Nova status | Written by nova_status.py. Read by server.py every 30s. |

### memory/ Files
| File | What it is | How to use |
|------|------------|------------|
| `memory/STATUS.md` | **READ THIS FIRST.** Current project state. | Architecture, phase completion, hardware, blockers. Updated 2026-05-06. |
| `memory/COLE.md` | Cole's profile + Nova's notes about him | Read to understand who Cole is and what he expects. LOCKED baseline + living notes. |
| `memory/JOURNAL.md` | Nova's rolling session log | Read last 2-3 entries for recent context. Append at session end via nova_memory.journal. |

### general_tools/nova_chat/ — The Group Chat Interface
| File | What it does |
|------|-------------|
| `launch.py` | Entry point. Run this to start nova_chat: `python general_tools/nova_chat/launch.py` |
| `server.py` | FastAPI + WebSocket server. All API endpoints, background monitors, NCL routing. `/api/llama/start|stop|status` added 2026-05-07. |
| `clients/nova.py` | Nova's inference client. Calls llama.cpp HTTP, streams tokens, handles tool loop. `SYSTEM_PREFIX` is Nova's personality prompt. Model identity line added 2026-05-07. |
| `clients/claude.py` | Claude Sonnet 4.6 streaming client |
| `clients/gemini.py` | Gemini 2.5 Pro streaming client |
| `transcript.py` | Shared conversation state. `to_messages()` builds the OpenAI-format payload. |
| `session_manager.py` | Persists sessions to logs/chat_sessions/ as gzip JSONL |
| `workspace_context.py` | Live workspace injection. `build_nova_context_block()` now always includes memory/ files. Fixed 2026-05-07. |
| `nova_bridge.py` | Executes [WRITE:], [EXEC:], [READ:] directives from Nova's chat messages |

### general_tools/nova_qt/ — Native Desktop UI (PRIMARY as of session 5+)
| File | What it does |
|------|-------------|
| `main.py` | QApplication entry point |
| `window.py` | QMainWindow — assembles sidebar + chat panel, owns WebSocket client, status bar |
| `chat_panel.py` | Central chat area: session tabs, message bubbles, ThinkingBlock, depth slider, autonomous toggle, input |
| `sidebar.py` | Left panel: Files / Terminal / Status / Thoughts tabs |
| `ws_client.py` | QThread WebSocket client — emits typed Qt signals for every server message type |
| `theme.py` | Color constants — NOVA, CLAUDE, GEMINI, COLE, BG, BORDER, etc. |
| `markdown.py` | Markdown-to-HTML for chat bubbles |

### workspace root — Patch Scripts
| File | What it does |
|------|-------------|
| `patch_depth_server.ps1` | Patches server.py + nova.py for depth slider (max_tokens) + autonomous_toggle handler. Run once, then restart nova_chat. |
| `apply_bootup_reorganization.ps1` | Patches workspace_context.py to load from BOOTUP/ + deletes root originals of the 6 boot files. |
