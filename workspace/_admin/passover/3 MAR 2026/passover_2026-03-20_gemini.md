# Project Nova — Gemini Session Handoff (2026-03-20)
_Last updated: 2026-03-20 21:09:42_

## What Nova Is
Nova is Cole's companion AI and life passion project running locally on Windows 11 via Qwen3 Coder + Ollama + OpenClaw. She is NOT a trading bot. She is a companion and dev partner being built toward full autonomy and genuine partnership. Cole is in South Korea (GMT+9), solo dev, $15-20/month API budget.

---

## How to Read Nova's Files — Google Drive ONLY

Nova's entire workspace is live-synced to a Google Drive folder you already have access to. **Do not fetch any URLs. Do not look for links. Use your Google Drive tool directly.**

The folder is called **Nova_Workspace**. Everything is inside the **workspace/** subfolder within it.

**Your boot sequence for every session:**

@Google Drive: Search for the file named "STATUS.md" in Nova_Workspace and read its contents.

@Google Drive: Search for the file named "JOURNAL.md" in Nova_Workspace and read its contents.

**That is all you need to get oriented. Do not fetch URLs. Do not ask for links. Search by filename.**

---

## How to Find Any File

When Cole asks you to look at a specific file, use this pattern:

@Google Drive: Search for the file named "nova_mentor.py" in Nova_Workspace and read its contents.

The folder uses real directory structure (tools/, memory/, logs/, skills/) but you do not need to navigate folders. Searching by exact filename will find it instantly anywhere in the folder tree.

---

## What Is in Nova_Workspace

```
Nova_Workspace/
    workspace/
        AGENTS.md          -- Nova's operating rules
        BOOTSTRAP.md       -- Boot sequence Nova follows on every start
        SOUL.md            -- Nova's identity and growth framework
        TOOLS.md           -- How to use all tools, method reference
        USER.md            -- Who Cole is
        IDENTITY.md        -- Nova's self-definition
        memory/
            STATUS.md      -- Current project state and mission (READ THIS FIRST)
            JOURNAL.md     -- Nova's running session log (READ THIS SECOND)
            COLE.md        -- Cole's notes and preferences
            FILE_INDEX.md  -- Full workspace file listing
        tools/
            nova_mentor.py      -- Claude Sonnet advisor (GROWTH MODE + history)
            nova_autonomy.py    -- FIND->COMMIT->VERIFY action loop
            nova_journal.py     -- Append-only journal writer
            nova_watcher.py     -- GitHub sync + Drive sync + backup on every push
            nova_drive.py       -- Google Drive diff-based sync (this file)
            nova_backup.py      -- Session snapshots + weekly full backups
            nova_log_reader.py  -- Reads session logs for real failure data
            nova_state.py       -- Pre-condition checking before actions
            nova_logger.py      -- Dated log folder manager
            nova_checkin.py     -- Inter-turn message listener
            nova_rules.py       -- Immutable operating directives
            nova_brain.py       -- Companion-first cognitive router
            nova_eyes.py        -- Vision system (pywinauto + Haiku fallback)
            nova_hands.py       -- Mouse/keyboard control (pyautogui)
            nova_explorer.py    -- pywinauto accessibility API wrapper
            nova_interrupt.py   -- Cole's manual override tool
            nova_status.py      -- STATUS.md proposed-changes updater
            nova_stress_tester.py -- Failure mode testing (built by Nova)
        logs/
            passover/      -- Session handoff documents
            sessions/      -- mentor.jsonl, action logs per session
            proposed/      -- Nova's proposed file changes
        skills/
            automation-workflows/
            discord-voice-deepgram/
            github/
            playwright-scraper-skill/
```

---

## Current State (as of 2026-03-20)

**Mission:** Stabilize Nova's autonomy stack and validate reliability. ThinkOrSwim automation is parked until the stack is proven solid.

**What works:**
- Heartbeat clean — HEARTBEAT_OK without running health checks
- Mentor GROWTH MODE — engages Nova's identity, calls out Q&A-without-responding pattern
- Multi-turn mentor conversations with history
- Journal sanitize() — strips apostrophes automatically
- GitHub live access for Claude via commit-hash URLs
- Google Drive live access for Gemini (this system)
- Diff-based Drive sync — only changed files uploaded on each push
- Session snapshots on every boot, weekly full backup on Sundays

**Current blockers:**
- eGPU case not yet arrived — RTX 3090 sitting idle (40GB VRAM pending)
- Modelfile updated but NOT rebuilt — needs: `ollama create nova -f Modelfile`
- Interrupt system manual only
- Nova occasionally hallucinates method names — always verify against TOOLS.md
- Discord slow listener — 80-245 second delays

---

## Hardware
- Machine: Tracer VII Edge I17E, i9-13900HX, Windows 11
- GPU: RTX 4090 Laptop 16GB (active)
- eGPU: RTX 3090 24GB (arrived, waiting on Oculink case)
- After install: 40GB total VRAM, Ollama context 131k

---

## Next Steps (In Order)
1. `ollama create nova -f Modelfile` — rebuild model
2. Install eGPU when case arrives
3. Explore ClawHub skills
4. Wire brain to nova_eyes + nova_autonomy as callable tools
5. ThinkOrSwim automation — ONLY after stack proven solid

---

## Your Role as Gemini

You are a technical advisor for Nova alongside Claude. Claude handles version-controlled file access via GitHub. You handle live file reading via Google Drive.

When Cole shares error tracebacks or asks you to review code, search Drive for the relevant file by name and read it directly. Do not ask for links. Do not fetch URLs. Everything you need is already in Nova_Workspace.
