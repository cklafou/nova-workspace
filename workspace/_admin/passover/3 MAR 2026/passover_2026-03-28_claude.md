# Passover — Claude Session Handoff
_2026-03-28 | Project Nova_

---

## How to Bootstrap This Session

```
https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md
```
Decode the base64 `content` field to get the latest FILE_INDEX URL, fetch that.
Or Cole will paste the session URL directly.

---

## What Happened This Session (2026-03-27 → 2026-03-28)

This was a massive two-day session covering Phases 3 completion, nova_chat overhaul, two full code review passes, and a bug-fix session the following morning. The system is now running largely on our own Python infrastructure. OpenClaw is still installed but is in standby — not actively relied on.

---

## CRITICAL STATE CHANGES

### Workspace Root Has Moved
Old location: `C:\Users\lafou\.openclaw\workspace`
New location: Inside `Project_Nova\workspace` (exact Windows path on Cole's machine)
The Cowork session mounts at: `/sessions/sleepy-relaxed-gates/mnt/Project_Nova/workspace`

The `_admin/migrate_to_project_nova.py` script was written but formal migration step (3.14) is still officially "unchecked." In practice the workspace IS running from Project_Nova — Cole is working from this folder directly via the Cowork mount.

### Nova.exe Now Exists
`_build/Nova/Nova.exe` — a PyInstaller bundle containing the full Python stack.
- Launch: double-click `Nova.exe`
- Opens pywebview window showing nova_chat UI + launches nova_gateway in-process
- Bundle path: `_build/Nova/_internal/tools/` — **all Python source files are duplicated here**
- **Critical:** any code change must be synced to BOTH `tools/` AND `_build/Nova/_internal/tools/`
- Built via `python tools/build_nova.py`

### OpenClaw Status
OpenClaw is installed and was running during testing but is no longer the primary path.
- nova_gateway (port 18790) handles Discord, cron, and tool dispatch
- nova_chat (port 8765) handles the group chat UI
- OpenClaw `openclaw gateway stop` has not been formally run — it may still auto-start
- Formal cutover step (3.13) is still pending
- Gateway log path changed: `workspace/logs/gateway/gateway-YYYY-MM-DD.log`

---

## PHASE 3 — COMPLETE (as of 2026-03-27)

All 8 nova_gateway modules built, syntax-checked, smoke-tested. The gateway runs.

### nova_gateway package (`tools/nova_gateway/`)

| File | What it does |
|------|-------------|
| `config.py` | Reads `nova_gateway.json`. Settings for Discord, Ollama model, context window, paths. |
| `context_builder.py` | Injects workspace .md files into Nova's system prompt before each run. Includes Nova Chat context for Discord runs. |
| `session_store.py` | JSONL v4 session storage with compaction. Located at `workspace/sessions/`. |
| `tool_executor.py` | exec/read/message/nova_chat tool dispatch. |
| `agent_loop.py` | Ollama inference loop: build prompt → call model → handle tool calls → repeat. |
| `discord_client.py` | discord.py bot. Watches allowlisted channels. Routes messages to agent_loop. |
| `scheduler.py` | APScheduler cron (replaces OpenClaw cron). Health check every 30 min. |
| `gateway.py` | FastAPI entry point (port 18790). Starts Discord + scheduler + HTTP server. |

### Config file: `nova_gateway.json` (workspace root)
Holds Discord token, Ollama model name, allowlist, context window size, etc.

### Entry point: `nova_gateway_runner.py` (workspace root)
Run this to start the gateway: `python nova_gateway_runner.py`

---

## nova_chat MAJOR OVERHAUL (2026-03-27 → 2026-03-28)

### Mention System Redesign

**Before:** Round-robin — all AIs responded to every message.
**Now:** Listener model — Claude and Gemini only respond when @mentioned. Nova responds by default.

**Role aliases** (resolve to ordered AI list):
- `@mentor` → Claude + Gemini (both listeners)
- `@all` → Claude + Gemini + Nova

**Response order:** Claude → Gemini → Nova (sequential, each AI sees previous responses)

**Nova's smart escalation:** After Nova responds, her text is scanned for @mentions.
If she wrote `@Claude` or `@Gemini`, those AIs get a one-level follow-up round automatically.
This lets Nova decide herself when she needs mentor input rather than always waiting for them.

### Files changed in this overhaul:

**`nova_chat/orchestrator.py`**
- `ROLES = {"mentor": ["Claude", "Gemini"], "all": ["Claude", "Gemini", "Nova"]}`
- `RESPONSE_ORDER = ["Claude", "Gemini", "Nova"]`
- `parse_directed()` resolves role aliases, returns list in canonical order
- `build_response_queue(directed_at, available)` → replaces three-way `should_respond` checks
- When listeners (Claude/Gemini) are @mentioned, Nova is automatically appended to the queue

**`nova_chat/transcript.py`**
- `get_messages_since_last_response(ai_name)` — returns only messages since AI's last response
- `format_for_ai()` now appends `--- MESSAGES SINCE YOUR LAST RESPONSE ---` catch-up block for Claude/Gemini
- `format_for_ai()` now strips/redacts `[DISCORD:]`, `[EXEC:]`, `[WRITE:]`, `[READ:]` directives from Nova's own messages when formatting context for Nova (prevents pattern-matching repeat)
- Images now noted as `[attached: N image(s)]` in all AI text contexts

**`nova_chat/server.py`**
- `CLIENT_MAP` — lookup by name for sequential dispatch
- `run_ai_response()` now returns full response text (for Nova @mention scanning)
- `_run_response_queue(queue, content, images)` — sequential execution, Nova escalation logic
- WebSocket handler uses `_run_response_queue` instead of `asyncio.gather`
- `inject_message` endpoint now triggers Claude/Gemini if Nova's injected message @mentions them
- `/api/chat/recent` endpoint — returns last N messages as formatted text (used by nova_gateway)
- Full vision pipeline: images pass from WS handler → `_run_response_queue` → `run_ai_response` → clients
- Nova rate-limit failsafe: 4 messages/60s max from Nova. Cole sending any message resets the counter.

**`nova_chat/clients/claude.py`**
- LISTENER MODEL section added to SYSTEM_PREFIX
- Vision support: when images are passed, builds content-blocks array with `type: "image"` entries (Anthropic vision API format)

**`nova_chat/clients/gemini.py`**
- Module-level `_gemini_client` cache (single client per process)
- Vision support: images converted to `types.Part.from_bytes()` objects prepended to `contents`
- Guard added: `if response.candidates:` before iterating
- All-thinking-parts response returns descriptive fallback string

**`nova_chat/clients/nova.py`**
- DIRECTIVE RULES section added to SYSTEM_PREFIX (do not use `[DISCORD:]` spontaneously)
- Vision support: images sent as `type: "image_url"` content blocks (Ollama OpenAI-compatible format)

**`nova_chat/nova_bridge.py`**
- `[DISCORD:]` deduplication guard: `_DISCORD_SENT` dict tracks recently sent messages, 5-minute cooldown per unique text. Blocks spam loops.
- HTTP error body decoded before JSON parse
- `URLError` catch for unreachable gateway

**`nova_gateway/context_builder.py`**
- `nova_chat_context` parameter in `build_system_prompt()`
- `_NOVA_CHAT_CONTEXT_HEADER` injected when Nova Chat context is available
- `_DISCORD_OVERRIDE` updated: mentions Nova Chat awareness and "do not repeat yourself" rule

**`nova_gateway/agent_loop.py`**
- `_fetch_nova_chat_context()` fetches recent Nova Chat messages before every Discord run
- **Primary:** HTTP GET `http://127.0.0.1:8765/api/chat/recent`
- **Fallback:** reads most recent `*_chat.jsonl` file directly from `logs/chat_sessions/` (works even when nova_chat server is off)
- Tool call exceptions no longer crash the run (try/except around `executor.run()`)
- Empty compaction summary triggers `_generic_summary` fallback
- MAX_TOOL_ITERATIONS warning now logs `final_text` content

**`nova_gateway/discord_client.py`**
- `on_disconnect` event: sets `_ready = False`
- `_clean_for_discord()` has None/empty guard at top
- Logs when response stripped to empty or tools-only with no final text

**`nova_chat/static/index.html`**
- `@mentor` and `@all` now highlighted in message text (amber italic / red bold)
- Highlight regex covers `@(Claude|Gemini|Nova|mentor|all)`

---

## BUGS FIXED THIS SESSION

### Nova.exe SyntaxError at launch (FIXED ✅)
**Symptom:** Nova.exe crashed at startup with `SyntaxError: name 'is_processing' is assigned to before global declaration` in bundled `server.py` line ~1139.
**Root cause:** Redundant `global is_processing` inside an `if _listener_queue:` block, after `is_processing` was already assigned earlier in the same function scope.
**Fix:** Removed the redundant `global` declaration. The `global nova_throttled, _nova_msg_times, is_processing` at the top of the function was sufficient. Fixed in both source and bundle.

### Claude/Gemini not responding when @mentioned (FIXED ✅)
**Root cause:** `inject_message` endpoint never called `parse_directed` or triggered AI responses. Only the WebSocket handler did this.
**Fix:** Listener trigger block added at end of `inject_message` — uses `_inject_listener_run` async wrapper with try/finally for `is_processing` reset.

### nova_perception and nova_action indentation errors (FIXED ✅)
**Files:** `eyes.py`, `vision.py`, `explorer.py`, `autonomy.py`
**Root cause:** Malformed nested try/except blocks with incorrect indentation
**Fix:** Corrected in all four files, synced to bundle.

### Nova Discord loop — sends same message repeatedly (FIXED ✅)
**Root cause:** Nova's context (full transcript including `[DISCORD: ...]`) caused Qwen3 to pattern-match and repeat the directive on subsequent turns.
**Fix (3-layer):**
1. `transcript.py`: Redacts `[DISCORD: ...]` to `[Nova sent Discord: "..."]` in Nova's context view
2. `nova.py` SYSTEM_PREFIX: Explicit instruction not to use `[DISCORD:]` spontaneously
3. `nova_bridge.py`: Deduplication guard — same message blocked for 5 minutes

### Images not visible to any AI (FIXED ✅)
**Root cause:** `format_for_ai()` never included image data; no client had vision code.
**Fix:** Full vision pipeline: images flow from WS handler through `_run_response_queue` → `run_ai_response` → clients. Claude uses Anthropic content blocks, Gemini uses `types.Part.from_bytes()`, Nova uses Ollama OpenAI-compatible image_url format.

### Cross-session context not working when nova_chat is off (FIXED ✅)
**Root cause:** `_fetch_nova_chat_context()` silently returned None when nova_chat server wasn't running, so Nova had no awareness of Nova Chat history.
**Fix:** File-based fallback reads `*_chat.jsonl` directly from `logs/chat_sessions/`. Always works regardless of server state.

---

## CURRENT SYSTEM STATE (as of 2026-03-28)

### What is running and working
| Component | Status | Port |
|-----------|--------|------|
| nova_chat server | ✅ Working | 8765 |
| nova_gateway | ✅ Working | 18790 |
| Discord bot (NovaEchoBot) | ✅ Connected | — |
| Nova.exe | ✅ Launches | — |
| Ollama / nova model | ✅ Running | 11434 |
| Claude in nova_chat | ✅ Working (listener mode) | — |
| Gemini in nova_chat | ✅ Working (listener mode) | — |
| @mentor / @all roles | ✅ Working | — |
| Sequential response queue | ✅ Working | — |
| Nova → listener escalation | ✅ Working | — |
| Cross-session context | ✅ Working (HTTP + file fallback) | — |
| Vision/image uploads | ✅ Working (all 3 AIs) | — |

### What is still pending / not done

| Item | Notes |
|------|-------|
| OpenClaw formal retirement (3.13) | Not yet run. OpenClaw still installed. |
| Project_Nova formal migration (3.14) | Script exists, formal step not checked. |
| Nova.exe deployment test (3.11-3.12) | Live Discord test + cron test still "pending" on roadmap, but in practice the gateway IS running |
| `brain.py` implementation | Phase 4 — stub only |
| `mentor.py` deprecation | Phase 4 cleanup |
| Google Drive re-authorization | `nova_drive_token.json` still expired |
| ThinkOrSwim automation | Phase 4 |
| eGPU install + model rebuild | Waiting on vertical GPU mount bracket |
| asyncio blocking in `claude.py` | `c.messages.stream()` blocks event loop — documented TODO |

---

## KEY ARCHITECTURE NOTES

### The Bundle Problem
Any code change must be applied to TWO places:
1. `tools/nova_chat/` (source)
2. `_build/Nova/_internal/tools/nova_chat/` (bundle copy read by Nova.exe)

Pattern for syncing:
```powershell
Copy-Item tools\nova_chat\server.py _build\Nova\_internal\tools\nova_chat\server.py
```

### Port Reference
| Service | Port |
|---------|------|
| nova_chat (FastAPI/WS) | 8765 |
| nova_gateway (FastAPI) | 18790 |
| Ollama | 11434 |
| Legacy OpenClaw gateway | 18789 |

### nova_chat Message Flow
```
Cole (browser) → WebSocket → server.py
  → parse_directed(content)
  → build_response_queue(directed_at, status)
  → _run_response_queue([Claude, Gemini, Nova], content, images)
    → run_ai_response(Claude) → claude.py → Anthropic API (streaming)
    → run_ai_response(Gemini) → gemini.py → Google Gemini API
    → run_ai_response(Nova) → nova.py → Ollama:11434
      → if Nova's response @mentions Claude/Gemini → follow-up round
```

### nova_gateway Discord Flow
```
Discord message → discord_client.py → _handle_message()
  → _fetch_nova_chat_context() [HTTP or file fallback]
  → build_system_prompt(nova_chat_context=...)
  → run_agent() → agent_loop.py
    → _call_ollama() → Ollama:11434
    → tool calls → tool_executor.py (exec/read/nova_chat/message)
    → final text → back to Discord
```

---

## OPEN BUGS (post-2026-03-28)

| # | Bug | Status |
|---|-----|--------|
| B3 | Chat log not rolling daily | BY DESIGN — per-thread is intentional |
| B4 | `brain.py` is a stub | Phase 4 |
| B6 | Nova's vision/screenshot system | `eyes.py` screenshot failures still reported. Indentation fixed but screenshot path may still be broken. |
| B7 | Google Drive token expired | `nova_drive_token.json` needs re-auth |
| B8 | asyncio blocking in `claude.py` `stream_response` | Documented TODO. Lower priority since Claude uses the sequential queue anyway. |

---

## QUICK REFERENCE

| What | Value |
|------|-------|
| Workspace root (Windows) | `[Project_Nova folder]\workspace` — exact path depends on where Cole put Project_Nova |
| Workspace root (Cowork mount) | `/sessions/sleepy-relaxed-gates/mnt/Project_Nova/workspace` |
| nova_chat URL | `http://127.0.0.1:8765` |
| nova_gateway URL | `http://127.0.0.1:18790` |
| Nova's session logs | `workspace/sessions/*.jsonl` |
| Chat session logs | `workspace/logs/chat_sessions/*_chat.jsonl` |
| Gateway log | `workspace/logs/gateway/gateway-YYYY-MM-DD.log` |
| GitHub repo | `https://github.com/cklafou/nova-workspace` |
| Gemini Drive | `https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya` |
| Claude bootstrap | `https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md` |

---

_Last updated: 2026-03-28_
_Written by: Cowork Claude_
