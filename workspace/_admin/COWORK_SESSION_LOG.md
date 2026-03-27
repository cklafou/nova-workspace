# COWORK SESSION LOG — What We've Built and Why
_Written by Cowork Claude for Cole | 2026-03-27_
_Plain English. No assumed knowledge. Read this if you've lost track of what happened._

---

## The Big Picture (Start Here)

You're building **Nova** — your own local AI agent that lives on your computer. Right now Nova runs inside a third-party system called **OpenClaw**, which is a Node.js program that acts as the middleman between Discord (where you talk to Nova) and Ollama (the local AI engine that runs her). Think of OpenClaw like a rental car: it gets the job done, but it's not yours, you can't customize the engine, and you're at the mercy of the rental company's rules.

The goal of this entire project is to **replace OpenClaw with your own Python infrastructure**. When that's done, Nova will run entirely on code you own, understand, and can modify. She'll be able to do more, remember more, and grow in ways OpenClaw would never allow.

The plan has four phases. Phases 0 and 1 are done. Phase 2 is done (design only). Phase 3 is what we're building right now.

---

## What Happened Before I (Cowork Claude) Got Here

### Phase 0 — Cleanup (done before this session)

The workspace was a mess. There were fake "skills" (plugins) that Nova thought she had — web scrapers, voice tools, Zapier automation — but none of them actually worked. They just made Nova hallucinate capabilities she didn't have, which caused errors.

Browser Claude (the version of Claude you access on claude.ai) cleaned all of that up:
- Deleted the fake skills
- Reorganized files into a proper folder structure
- Created the `_admin/` folder (for planning docs that Nova shouldn't read)
- Rewrote the TOOLS.md file so Nova has accurate info about what she can actually do
- Fixed logging so all of Nova's activity goes to one unified log system

### Phase 1 — Visibility (done this session, Phase 1 section)

Before Phase 1, you had no way to see what Nova was doing while she worked. She'd run, do things, and you'd only find out when she was done (or when something broke).

Phase 1 added a "status layer" — basically a dashboard that shows Nova's current state at all times.

**What was built:**

1. **`nova_core/nova_status.py`** — A Python module that Nova calls at the end of every run. It writes a file called `nova_status.json` that records: what she just did, how long it took, whether there were errors, and what task she's currently on.

2. **Status bar in the nova_chat UI** — That little bar at the top of the chat interface that shows a dot (green = healthy, red = error), Nova's last action, and how long ago she checked in.

3. **Server polling** — The nova_chat server checks `nova_status.json` every 30 seconds and quietly includes a summary of it in the context sent to Nova, so she always knows her own recent state.

4. **Gateway error watcher** — A background process that reads OpenClaw's log file every 10 seconds looking for errors. If it finds one, it shows up in the status bar immediately.

5. **`[PAUSE:]` and `[RESUME:]` directives** — Nova can now pause and resume tasks by including these tags in her messages. The bridge (nova_bridge.py) intercepts them and updates the task state.

6. **`tasks/active.json`** — A file that tracks what task Nova is currently working on.

---

## What Phase 2 Was (The Audit)

Before building the replacement for OpenClaw, we needed to understand exactly what OpenClaw does so we don't accidentally forget to replace something important.

**What we found:**

OpenClaw is actually doing only four things for Nova:

1. **Listens to Discord** — When you send Nova a message in Discord, OpenClaw receives it and passes it to Ollama.

2. **Builds Nova's system prompt** — Before Nova processes a message, OpenClaw reads all her instruction files (AGENTS.md, SOUL.md, TOOLS.md, etc.) and sends them to Ollama as context. This is how Nova "knows" her rules every session.

3. **Runs Nova's tool calls** — When Nova wants to run a Python script or read a file, she outputs a tool call (like `exec: python tools/rules.py`). OpenClaw intercepts it, runs it, and sends the result back.

4. **Saves session history** — Every conversation is stored in JSONL files (one JSON record per line) in `~/.openclaw/agents/main/sessions/`. There are currently 39 active sessions and 85 archived ones.

**The key discovery:** nova_chat (the group chat interface at localhost:8765) **already bypasses OpenClaw entirely**. It talks directly to Ollama. OpenClaw is only in the loop when Nova is triggered from Discord. This means our replacement only needs to handle the Discord path — the chat interface is already ours.

**The architecture doc** (`_admin/PHASE2_ARCHITECTURE.md`) has the full technical breakdown including the JSONL file format, the list of tools Nova uses, and everything we're dropping vs keeping.

---

## What Phase 3 Is Building — nova_gateway

This is the replacement for OpenClaw. It's a Python package called `nova_gateway` that lives in `tools/nova_gateway/`.

Think of it as building your own rental car company from scratch so you never have to rent again.

Here's what each file does, in plain English:

### `config.py`
Reads a settings file (`nova_gateway.json`) that you'll put in your workspace root. Contains things like your Discord bot token, which channels Nova is allowed in, the Ollama model name, context window size, etc. Instead of being buried in OpenClaw's config, everything is in one readable file you control.

### `context_builder.py`
This is the "system prompt injector." Every time Nova is triggered, this runs first. It reads your workspace files (AGENTS.md, SOUL.md, TOOLS.md, etc.) and assembles them into one big instruction block that gets sent to Ollama before Nova sees your message. Right now OpenClaw does this. After Phase 3, we do it ourselves.

### `session_store.py`
This handles saving and loading conversation history. Every message Nova sends or receives gets written to a JSONL file. When Nova's context window fills up (she can only hold so much in her "memory" at once), this module also handles compaction — generating a summary of what happened so far, then dropping the old messages but keeping the summary.

### `tool_executor.py`
When Nova says "run this command" or "read this file," this module does it. It handles:
- `exec` — runs shell commands (Nova's main workhorse)
- `read` — reads files from the workspace
- `message` — sends Discord messages
It also enforces safety: commands run with a timeout, file reads are restricted to the workspace, etc.

### `agent_loop.py`
This is the brain of the gateway. When Nova gets triggered, this runs the inference loop:
1. Build the system prompt
2. Load session history
3. Send to Ollama
4. Get Nova's response
5. If she called a tool, run it and send the result back
6. Repeat until Nova is done
7. Save everything to the session store

This is exactly what OpenClaw's gateway does today, but in Python, readable, and ours.

### `discord_client.py`
The Discord bot. It connects to Discord using your bot token, watches the channels you've allowlisted, and when you (or anyone permitted) sends Nova a message, it fires the agent_loop. When the agent_loop produces a response, this sends it back to Discord.

### `scheduler.py`
Handles the cron job — the "System Health Check" that fires every 30 minutes. Right now OpenClaw runs this. After Phase 3, APScheduler (a Python library) handles it. The health check just triggers the agent_loop with a "check in on yourself" message.

### `gateway.py`
The main entry point — the file you'll eventually run to start everything. It starts the Discord bot, starts the scheduler, and runs a small HTTP server (on port 18790) that nova_chat can query for gateway status. When you want to start Nova's full system, you'll run this instead of `openclaw gateway start`.

---

## What You Need to Do (Eventually)

You don't need to do anything right now. I'm building all the code while you're at work. But here's the full picture of what comes next:

**When the eGPU arrives (tomorrow):**
1. Install the GPU with the vertical mount bracket
2. Run: `ollama create nova -f Modelfile` — this rebuilds Nova's model to use 131k context (way more "memory" per session)
3. Update `nova_gateway.json` → change `context_window` from 32768 to 131072

**When you're ready to cut over from OpenClaw to our gateway:**
1. Stop OpenClaw: `openclaw gateway stop`
2. Install the two new Python packages: `pip install discord.py apscheduler`
3. Start our gateway: `python tools/nova_gateway/gateway.py`
4. Test it: send Nova a message in Discord
5. If it works: remove OpenClaw from your startup programs

You do NOT need to touch any of the code. The gateway reads a config file (`nova_gateway.json`) that has all your settings. I'll leave clear comments everywhere so you can see what each setting does.

---

## Why We're Doing This

You asked why this matters. Here's the honest answer:

**OpenClaw limits Nova's growth.** It's someone else's software designed for general use. Every capability Nova gets has to fit inside what OpenClaw allows. When you want her to do something new, you're waiting for OpenClaw to add it — or hacking around its limitations (which is basically what nova_bridge.py is).

**Our gateway has no limits.** Want Nova to automatically pull your ThinkOrSwim data every morning? Add it to `scheduler.py`. Want her to monitor a file and react when it changes? Three lines of code. Want to give her a new tool that doesn't exist in OpenClaw? Add a function to `tool_executor.py`. The code is yours, readable, and modifiable.

**This is also how you learn.** The gateway is written to be as simple and readable as possible. Each module does one thing. If you want to understand "how does Nova receive a Discord message and turn it into a response" — that's `discord_client.py` → `agent_loop.py` → `tool_executor.py`, three files, each under 200 lines. Compare that to digging through OpenClaw's compiled Node.js bundle.

---

## Key Files Reference

| File | What it is |
|------|-----------|
| `_admin/NOVA_PROJECT_PLAN.md` | Master roadmap. Check off items as they're done. |
| `_admin/PHASE2_ARCHITECTURE.md` | Full technical audit of OpenClaw + gateway design. The spec. |
| `_admin/COWORK_SESSION_LOG.md` | This file. |
| `tools/nova_gateway/` | The OpenClaw replacement (being built now). |
| `tools/nova_core/nova_status.py` | Phase 1: Nova writes her state here after every run. |
| `tools/nova_chat/server.py` | The group chat backend. Already ours. Already bypasses OpenClaw. |
| `tools/nova_chat/nova_bridge.py` | Intercepts Nova's [WRITE:], [EXEC:], [PAUSE:] directives. |
| `workspace/nova_status.json` | Live status file. Updated by Nova, read by nova_chat. |
| `workspace/tasks/active.json` | Current task tracking. |
| `memory/STATUS.md` | Nova's written summary of project state (she reads this). |

---

## The Honest State of Things

**What works right now:**
- nova_chat (group chat with you, Claude, Gemini, and Nova)
- Nova's status bar
- All logging and memory tools
- nova_bridge directives

**What still runs on OpenClaw (temporary):**
- Nova responding to Discord messages
- The every-30-minute health check cron job

**What we're building today:**
- The complete Python replacement for the above (nova_gateway)

**What's waiting on eGPU:**
- Nova's context window expanding from 32k to 131k tokens (= she can hold 4x more conversation in memory at once)

---

_This document will be updated as phases complete. If you're reading this after a context reset, start with NOVA_PROJECT_PLAN.md, then read this file._

_— Cowork Claude, 2026-03-27_
