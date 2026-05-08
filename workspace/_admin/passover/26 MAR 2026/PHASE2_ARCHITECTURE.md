# NOVA PHASE 2 — ARCHITECTURE REPORT
_Produced by Cowork Claude | 2026-03-27_
_Status: DRAFT — Awaiting Cole sign-off before Phase 3 begins_

---

## WHAT THIS DOCUMENT IS

Full audit of OpenClaw's internals and a design for our Python replacement. Read this once, sign off, and Phase 3 can begin after eGPU install.

---

## SECTION 1 — OPENCLAW INTERNALS AUDIT

### 1.1 What OpenClaw Actually Is

OpenClaw is a Node.js agent host. It runs as a background daemon (`gateway.cmd`, port 18789) and does four things:

1. **Receives triggers** — Discord messages arrive, get routed to Nova
2. **Injects workspace context** — BOOTSTRAP.md, SOUL.md, AGENTS.md, TOOLS.md etc. are injected as a system prompt before every Nova run
3. **Dispatches tool calls** — Nova's tool calls are intercepted and executed by the gateway
4. **Stores session history** — Every run written to `~/.openclaw/agents/main/sessions/*.jsonl`

The gateway talks to Ollama at `http://127.0.0.1:11434` using the OpenAI-compatible API. It is essentially a middleman between Discord and Ollama.

---

### 1.2 Session Storage Schema

Sessions live at `~/.openclaw/agents/main/sessions/<uuid>.jsonl`. Each line is a JSON record. There are currently **39 active sessions** and **85 reset (archived) sessions**.

**Message types in the JSONL:**

| Type | Purpose |
|------|---------|
| `session` | Session header — UUID, timestamp, working directory |
| `model_change` | Which model is active |
| `thinking_level_change` | Reasoning mode (off/low/high) |
| `custom` / `model-snapshot` | Model metadata snapshot |
| `message` | The actual conversation — role: user, assistant, toolResult |
| `compaction` | Context compression event — stores a summary + `firstKeptEntryId` to truncate history |

**Compaction:** When Nova's context window fills, OpenClaw generates a markdown summary of the session ("Goal / Progress / Decisions / Next Steps") and marks everything before a cutoff point as dropped. Only the summary + recent messages are sent to Ollama on the next run. This is why stale function names in old sessions caused ImportErrors — the compacted summary preserved incorrect facts forever.

**Tool calls inside `message` records:**
```json
{"type": "toolCall", "id": "call_xxx", "name": "exec", "arguments": {"command": "python tools/nova_rules.py"}}
```
Tool results come back as a separate `message` record with `role: "toolResult"`.

---

### 1.3 Tools Nova Has Through OpenClaw

| Tool | Usage count (sample session) | What it does |
|------|------------------------------|-------------|
| `exec` | 39 | Run any shell command. Nova's primary workhorse. |
| `read` | 22 | Read a file from workspace. |
| `write` | 1 | Write a file. We've intentionally deprioritized this in favor of `nova_bridge`. |
| `process` | 3 | Poll for incoming events/messages. Blocking mechanism between turns. |
| `session_status` | 1 | Get current session metadata from gateway. **STALE — `update_pulse` name caused ImportError.** |
| `memory_search` | 1 | Search across session history. |
| `message` | 2 | Send a Discord message. |
| `web_search` | 2 | Web search (provider unknown — likely bundled skill). |

The tools we actually care about and must replicate: **exec, read, message**. The rest are either unused or can be dropped.

---

### 1.4 Bundled Skills in AppData

**Cannot directly audit** — `C:\Users\lafou\AppData\Roaming\npm\node_modules\openclaw\` is outside our mount. But from session history we know OpenClaw had bundled native skills (`nativeSkills: "auto"` in config). The skills folder was already deleted from workspace. The native command/skill system (`commands.native: "auto"`) likely provides `web_search` and similar.

**Decision from Phase 0:** All workspace skills deleted. Native skills are OpenClaw's problem. In Phase 3, we either drop `web_search` entirely or wire Nova to a Python search tool directly.

---

### 1.5 What Our Code Already Depends On From OpenClaw

| File | OpenClaw dependency | Criticality |
|------|--------------------|-----------  |
| `nova_chat/server.py` | Reads `~/.openclaw/agents/main/sessions/*.jsonl` for log viewer | Low — display only |
| `nova_chat/server.py` | Reads `C:/tmp/openclaw/openclaw-YYYY-MM-DD.log` for error watcher | Medium — Phase 1 feature |
| `nova_chat/server.py` | Pings port 18789 for gateway status, calls `openclaw gateway start/stop` | Medium — UI button |
| `nova_chat/check_keys.py` | Pings `http://127.0.0.1:18789/v1/models` | Low — startup check only |
| `nova_chat/clients/nova.py` | Hits **Ollama directly** at port 11434 — NOT OpenClaw | None ✅ |
| `nova_sync/watcher.py` | Watches `C:\Users\lafou\.openclaw\` root | Low — file watcher |
| `nova_core/nova_status.py` | `gateway` field in status JSON | None (our own field) ✅ |

**Key finding: nova_chat already bypasses the OpenClaw gateway for Nova's inference.** It talks directly to Ollama. OpenClaw is only needed for the Discord trigger path and the agent tool execution loop.

---

### 1.6 Cron / Scheduler

One job: "System Health Check" every 30 minutes. Uses `sessionTarget: "main"` and `wakeMode: "now"`. Sends a `systemEvent` payload text to Nova's main session. Nova runs, does a health check, reports via Discord.

In our replacement: this becomes an APScheduler job that sends a message into Nova's Python session loop.

---

### 1.7 Discord Integration

Bot token in `openclaw.json`. OpenClaw uses `discord.js` under the hood. The `message` tool lets Nova send to any channel. Inbound messages trigger agent runs.

Intents: `presence: false`, `guildMembers: false` (minimal). DMs enabled with `policy: "pairing"`. `groupPolicy: "allowlist"` (only specific guilds/channels).

---

## SECTION 2 — OPENCLAW DEPENDENCY TREE

```
Discord
  └─► OpenClaw Gateway (port 18789, Node.js)
        ├─► System prompt injection (workspace .md files → Ollama context)
        ├─► Tool dispatch (exec / read / write / process / message / web_search)
        ├─► Session storage (~/.openclaw/agents/main/sessions/*.jsonl)
        ├─► Compaction engine (summary generation when context full)
        └─► Cron scheduler (System Health Check every 30min)
              └─► Nova (Ollama, port 11434)
                    └─► nova_bridge.py directives → disk operations

nova_chat (port 8765, our Python stack) — SEPARATE from above
  └─► Ollama direct (port 11434) — BYPASSES OpenClaw entirely
        └─► Nova responds in chat UI
```

**What we own vs what OpenClaw owns:**

| Component | Currently owns | Phase 3 owner |
|-----------|---------------|---------------|
| Nova inference | OpenClaw → Ollama | Our gateway → Ollama |
| Discord I/O | OpenClaw (discord.js) | Our gateway (discord.py) |
| Tool execution | OpenClaw | Our gateway |
| Session storage | OpenClaw JSONL | Our JSONL (same format or simplified) |
| Workspace injection | OpenClaw | Our gateway |
| Compaction | OpenClaw | Our gateway (or Nova handles via AGENTS.md rules) |
| Cron | OpenClaw APScheduler | Python APScheduler |
| nova_chat | Ours ✅ | Ours ✅ |
| nova_bridge | Ours ✅ | Ours ✅ |
| nova_status.json | Ours ✅ | Ours ✅ |

---

## SECTION 3 — REPLACEMENT DESIGN

### 3.1 Philosophy

- **Don't rewrite OpenClaw feature-for-feature.** We only need what Nova actually uses.
- **Keep nova_chat separate** from the agent loop. It's already clean. Don't merge them.
- **Minimal gateway.** One Python process, one config file, no Node.
- **Session format**: Keep the JSONL schema compatible enough that existing logs still parse. Add a `version: 4` header to distinguish ours.
- **Tools**: Only implement exec, read, message. Drop session_status, process (Nova can use nova_status.py instead), drop memory_search (Nova uses journal.py).

---

### 3.2 nova_gateway — The Replacement Daemon

**New file:** `tools/nova_gateway/gateway.py`

Single FastAPI + asyncio process. Replaces the Node.js daemon entirely.

**Responsibilities:**

1. **Discord listener** — discord.py bot, reads channels on allowlist, fires Nova runs
2. **Agent runner** — for each trigger, build system prompt, call Ollama, process tool calls in a loop until stop
3. **Tool executor** — exec, read, message (write via nova_bridge rules if needed)
4. **Session writer** — append JSONL records to our session store
5. **Compaction** — call a Claude Haiku/Gemini Flash endpoint to summarize when context > threshold. Or: use Nova herself to summarize (cheaper, keeps it local)
6. **Cron** — APScheduler, replace the single health check job
7. **Status endpoint** — HTTP API for nova_chat to query instead of pinging port 18789

**Config:** Single `nova_gateway.json` at workspace root. No more `openclaw.json`.

---

### 3.3 Workspace Injection (System Prompt Builder)

OpenClaw reads the workspace files and builds a system prompt. We replicate this in Python:

```python
# tools/nova_gateway/context_builder.py
INJECT_FILES = [
    "AGENTS.md",
    "SOUL.md", 
    "IDENTITY.md",
    "TOOLS.md",
    "HEARTBEAT.md",   # only on cron triggers
    "memory/STATUS.md",
    "memory/COLE.md",
]
```

Build system prompt by reading each file and concatenating. Same as what BOOTSTRAP.md currently tells Nova to do manually — now the gateway does it automatically before the first token.

---

### 3.4 Session Storage

Keep JSONL format. Our schema:

```jsonl
{"type":"session","version":4,"id":"<uuid>","timestamp":"...","trigger":"discord|cron|manual"}
{"type":"message","role":"user","content":"...","timestamp":"..."}
{"type":"message","role":"assistant","content":[...],"model":"nova","usage":{...}}
{"type":"tool_call","name":"exec","arguments":{...},"result":"...","timestamp":"..."}
{"type":"compaction","summary":"...","tokens_before":N,"timestamp":"..."}
```

Store at `workspace/sessions/<YYYY-MM-DD>/<uuid>.jsonl`. Date-organized from day one.

---

### 3.5 Tool Execution

Nova outputs a tool call JSON block. Gateway intercepts, routes:

| Nova calls | Gateway does |
|------------|-------------|
| `exec` | `subprocess.run()` in workspace dir, 60s timeout |
| `read` | `open()` path relative to workspace |
| `message` | `discord_client.send_message(channel, text)` |
| `[WRITE:]` directive | nova_bridge.py handles (already done) |
| `[PAUSE:] / [RESUME:]` | nova_bridge.py handles (already done) |

No `write` tool exposed directly. Nova must use `[WRITE:]` directives which go through nova_bridge for safety.

---

### 3.6 Compaction Strategy

When context fills (> 28k tokens for current 32k model, > 120k after eGPU rebuild):

1. Call `nova_memory/journal.py` — append current session summary to JOURNAL.md
2. Generate compaction summary (ask Nova herself: "Summarize this session's goal, decisions, and next steps in 200 words")
3. Write compaction record to JSONL
4. Truncate message history to last 10 exchanges + compaction summary

This is cheaper than calling Claude/Gemini for compaction and keeps it local.

---

### 3.7 Port / API Changes

| Service | Current port | Phase 3 port | Notes |
|---------|-------------|-------------|-------|
| OpenClaw gateway | 18789 | **retired** | Gone |
| nova_gateway | (new) | 18790 | Our daemon |
| nova_chat | 8765 | 8765 | Unchanged |
| Ollama | 11434 | 11434 | Unchanged |

`nova_chat/server.py` gateway buttons and log reader need to be updated to point at 18790 instead of 18789. This is a small change.

---

### 3.8 Discord Behavior Parity

Keep the same behavior Cole currently has:
- Allowlist policy — only configured guilds/channels trigger Nova
- DMs enabled with pairing policy
- `ackReactionScope: "group-mentions"` — reactions only for group mentions
- `allowBots: true` — Nova can respond to bot messages (used for nova_chat relay)

---

### 3.9 What We're Dropping

| OpenClaw feature | Drop? | Reason |
|-----------------|-------|--------|
| Canvas UI | Yes | Replaced by nova_chat |
| WebSocket control API | Yes | We don't use it |
| `session_status` tool | Yes | nova_status.py covers this |
| `process` tool | Yes | Not needed in our loop model |
| `memory_search` tool | Yes | Nova uses journal.py |
| `web_search` tool | Defer | Add later if needed |
| Tailscale integration | Yes | Not used |
| Device keypair auth | Yes | Our gateway uses a simple local token |
| Subagents | Defer | Phase 4 if needed |

---

## SECTION 4 — PHASE 3 BUILD ORDER

Once eGPU is installed and model is rebuilt, build in this order:

1. `nova_gateway/context_builder.py` — workspace file injector
2. `nova_gateway/session_store.py` — JSONL writer, reader, compaction
3. `nova_gateway/tool_executor.py` — exec, read, message dispatch
4. `nova_gateway/agent_loop.py` — Ollama call loop with tool handling
5. `nova_gateway/discord_client.py` — discord.py bot
6. `nova_gateway/scheduler.py` — APScheduler, health check cron
7. `nova_gateway/gateway.py` — FastAPI entry point wiring everything together
8. Update `nova_chat/server.py` — swap 18789 references to 18790, update log paths
9. Test: trigger Nova via Discord, verify she runs, tools work, session written
10. Test: cron fires, health check completes, Discord message sent
11. Retire OpenClaw: `openclaw gateway stop`, remove from startup

---

## SECTION 5 — RISKS AND MITIGATIONS

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Compaction quality degrades (Nova summarizes herself poorly) | Medium | Fallback: call Gemini Flash for compaction |
| Tool execution permissions differ from OpenClaw's | Low | We run as same user, same CWD, same PATH (copy from gateway.cmd) |
| Discord rate limits on startup | Low | Standard discord.py backoff |
| Session file bloat (no reset mechanic) | Medium | Auto-archive sessions > 30 days old |
| nova_chat log reader breaks when OpenClaw gone | Certain | Update server.py in step 8 to read from `workspace/sessions/` |
| Breaking Nova's existing session continuity | High | Do a clean session reset the same day we switch over |

---

## SIGN-OFF

Cole: review Sections 3 and 4 especially. Any changes to the design before Phase 3 starts? Once you confirm, this document gets filed and Phase 3 tasks go into NOVA_PROJECT_PLAN.md.

_Draft by Cowork Claude | 2026-03-27_
