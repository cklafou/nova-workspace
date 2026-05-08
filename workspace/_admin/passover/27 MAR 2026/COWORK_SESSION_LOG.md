# COWORK SESSION LOG — What We've Built and Why
_Written by Cowork Claude for Cole_
_Last updated: 2026-03-28 | Plain English. No assumed knowledge._

---

## The Big Picture (Start Here)

You're building **Nova** — your own local AI agent that lives on your computer. The goal is for Nova to run entirely on code *you own*, understand, and can modify — with no dependency on third-party platforms.

The plan has four phases. **Phases 0, 1, 2, and 3 are functionally complete.** Phase 4 is next (Nova's native intelligence — fine-tuning, brain.py, ThinkOrSwim).

---

## Where Things Stand Right Now (2026-03-28)

The infrastructure is built and running. Here's what you have:

### Nova.exe
Double-click `_build/Nova/Nova.exe` and you get the full Nova interface — a desktop window with the group chat on one tab and a system dashboard on another. The exe contains a bundled copy of all the Python code and starts everything in one process.

### Nova Chat (`http://127.0.0.1:8765`)
The group chat interface where you, Claude, Gemini, and Nova all talk together. Here's how it works now:

- **Nova responds by default** to everything you send
- **Claude and Gemini are "listeners"** — they only respond when you specifically @mention them
- **`@mentor`** = mentions both Claude and Gemini at once (they're your AI mentors)
- **`@all`** = messages everyone
- When you @mention Claude or Gemini, they respond first, then Nova reads their responses before adding her own — so the conversation is coherent, not a pile-up
- **Nova can escalate herself** — if Nova thinks Claude or Gemini need to weigh in, she @mentions them in her response, and they automatically get a follow-up round
- You can **paste or drag images** into the chat and all three AIs will actually see them

### Nova Gateway (`http://127.0.0.1:18790`)
This is the Python replacement for OpenClaw. It handles:
- **Discord**: Nova reads your Discord DMs and messages in allowed channels, responds intelligently
- **Cron**: A health check fires every 30 minutes so Nova stays aware of her own state
- **Tools**: Nova can run commands, read files, send Discord messages, and post to Nova Chat
- **Cross-session awareness**: When Nova is responding in Discord, she reads the recent Nova Chat history first so she knows what's already been discussed there

### The Bundle Sync Rule (Important)
Nova.exe contains a copy of all the Python source files inside `_build/Nova/_internal/tools/`. Any time you change code in `tools/`, you must also copy the changed files to `_build/Nova/_internal/tools/`. Otherwise Nova.exe keeps running the old code.

---

## What We Built, Phase by Phase

### Phase 0 — Cleanup
The workspace was a mess. Fake skills (plugins) made Nova hallucinate capabilities she didn't have. Everything got cleaned up:
- Deleted the fake skills
- Reorganized into a proper folder structure
- Created `_admin/` (for planning docs Nova shouldn't see)
- Rewrote TOOLS.md so Nova has accurate info about her actual capabilities
- Built `nova_logs/` — a unified logging system so all of Nova's activity goes to one place

### Phase 1 — Visibility
Before this, you had no way to see what Nova was doing. Phase 1 added the status layer:
- **`nova_status.json`** — Nova writes her state here at the end of every agent run (what she did, how long, errors)
- **Status bar in nova_chat** — the dot at the top of the chat shows Nova's health at a glance
- **Server polling** — nova_chat reads nova_status.json every 30 seconds and quietly includes a summary in Nova's context
- **Gateway error watcher** — if the gateway logs an error, it shows up in the UI immediately
- **`[PAUSE:]` and `[RESUME:]` directives** — Nova can pause and resume tasks

### Phase 2 — Architecture Audit
Before building the OpenClaw replacement, we mapped exactly what OpenClaw does. Findings:
- OpenClaw is only doing four things: listen to Discord, build Nova's system prompt, run tool calls, save session history
- Nova Chat already bypasses OpenClaw entirely (it talks directly to Ollama)
- The full technical design is in `_admin/PHASE2_ARCHITECTURE.md`

### Phase 3 — Nova Gateway (The OpenClaw Replacement)
Built `tools/nova_gateway/` — a Python package that does everything OpenClaw does, but ours:

| Module | What it does |
|--------|-------------|
| `config.py` | Reads `nova_gateway.json` — your settings file |
| `context_builder.py` | Injects Nova's instruction files (AGENTS.md etc.) into her system prompt before every run. Also injects recent Nova Chat messages so she has cross-session awareness. |
| `session_store.py` | Saves every conversation to JSONL files in `workspace/sessions/` |
| `tool_executor.py` | Handles Nova's tool calls: run commands, read files, send Discord messages, post to Nova Chat |
| `agent_loop.py` | The inference loop: build prompt → ask Ollama → handle tool calls → repeat |
| `discord_client.py` | The Discord bot — watches channels, routes messages to Nova, sends replies |
| `scheduler.py` | The cron job runner (health check every 30 minutes) |
| `gateway.py` | The main entry point: starts everything, runs the HTTP server on port 18790 |

Also built in Phase 3:
- **`NovaLauncher.py`** and **`build_nova.py`** — the pywebview desktop app + PyInstaller build
- **`Nova.exe`** — the all-in-one runnable

### Phase 3 Addendum — nova_chat Overhaul
A major rewrite of nova_chat happened alongside Phase 3. Key changes:

**Before:** Every AI responded to every message (round-robin). Chaotic.
**After:** Listener model with role aliases. Structured, coherent.

**What changed:**
- Mention system: `@Claude`, `@Gemini`, `@Nova`, `@mentor` (=Claude+Gemini), `@all`
- Sequential queue: Claude responds, then Gemini reads it and responds, then Nova reads both and responds
- Nova escalation: Nova can @mention Claude/Gemini herself if she decides they need to weigh in
- Catch-up context: If Claude/Gemini haven't spoken in a while, they get a summary of what they missed
- Image support: Paste images into chat → all three AIs see them (Claude uses vision API, Gemini uses Parts, Nova uses Ollama image format)
- Rate limiter: Nova can't inject more than 4 messages per minute from her autonomy loop (anti-spam)
- Cross-session: Nova reads recent Nova Chat messages before replying in Discord

---

## Bugs Fixed Along the Way

| Bug | What it was | How it was fixed |
|-----|-------------|-----------------|
| Nova.exe SyntaxError at launch | `global is_processing` declared twice in the same function | Removed the redundant declaration |
| Claude/Gemini silent when @mentioned | `inject_message` endpoint never triggered AI responses | Added listener trigger logic at end of inject_message |
| nova_perception indentation errors | Malformed try/except blocks in eyes.py, vision.py, explorer.py, autonomy.py | Fixed indentation in all four files, synced to bundle |
| Nova Discord loop | Nova pattern-matched `[DISCORD:]` from her own transcript history and repeated it | Three fixes: transcript redaction, SYSTEM_PREFIX guidance, 5-minute dedup guard |
| Cross-session context failing when nova_chat offline | HTTP fetch silently returned None | Added file-based fallback reading JSONL logs directly |
| Images not visible to AIs | No vision code existed in any client | Full pipeline: images flow from browser → server → all three AI clients |

---

## What's Still Not Done

| Item | Why it's pending |
|------|-----------------|
| Formally retiring OpenClaw | OpenClaw still installed and may still auto-start. To retire: `openclaw gateway stop`, remove from startup. Not urgent since our gateway is running. |
| Google Drive re-authorization | `nova_drive_token.json` expired. Cole needs to re-auth manually. |
| eGPU install | Waiting on the vertical GPU mount bracket. Once installed: rebuild Modelfile, expand context window from 32k to 131k tokens. |
| `brain.py` | Still a stub. Phase 4 work — Nova's native reasoning. |
| ThinkOrSwim automation | Phase 4. |
| `mentor.py` cleanup | Old file from pre-nova_chat era. Deprioritized. |

---

## The Honest State of Things

**What works right now:**
- Nova.exe launches and runs
- nova_chat group chat (Cole + Claude + Gemini + Nova with @mentions and role aliases)
- Image sharing in nova_chat (all three AIs see your images)
- nova_gateway running (Discord bot connected, cron health checks firing)
- Nova has cross-session awareness (reads Nova Chat before responding in Discord)
- nova_status.json status bar in the chat UI
- All logging, memory, and bridge tools

**What still runs on OpenClaw (temporarily):**
- Possibly nothing — nova_gateway has replaced it. But OpenClaw may still be auto-starting. Until `openclaw gateway stop` is run and it's removed from startup, there's a chance it's still around.

**What's waiting on eGPU:**
- Nova's context window: currently 32k tokens. After eGPU + Modelfile rebuild: 131k tokens. This means she can hold 4x more conversation in "memory" per session.

---

## Key File Reference

| File | What it is |
|------|-----------|
| `_admin/NOVA_PROJECT_PLAN.md` | Master roadmap. Check off items as done. |
| `_admin/PHASE2_ARCHITECTURE.md` | Full technical audit of OpenClaw + gateway design. |
| `_admin/COWORK_SESSION_LOG.md` | This file. |
| `_admin/passover/3 MAR 2026/passover_2026-03-28_claude.md` | Latest detailed handoff with all technical specifics. |
| `tools/nova_gateway/` | The OpenClaw replacement. All Python, all ours. |
| `tools/nova_chat/server.py` | The group chat backend. |
| `tools/nova_chat/orchestrator.py` | Mention parsing and response queue logic. |
| `tools/nova_chat/transcript.py` | Conversation history management + catch-up context. |
| `tools/nova_chat/nova_bridge.py` | Intercepts Nova's `[WRITE:]`, `[EXEC:]`, `[DISCORD:]` etc. directives. |
| `tools/nova_core/nova_status.py` | Nova writes her state here after every agent run. |
| `nova_gateway.json` | Gateway settings: Discord token, Ollama config, allowlist. |
| `nova_status.json` | Live status file updated by Nova, read by nova_chat. |
| `_build/Nova/Nova.exe` | The runnable desktop app. |

---

_This document is updated after each Cowork session. If you're reading this after a context reset, start with `NOVA_PROJECT_PLAN.md`, then read the latest passover doc in `_admin/passover/3 MAR 2026/`._

_— Cowork Claude, 2026-03-28_
