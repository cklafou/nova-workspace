# Passover -- Gemini Session Handoff
_2026-03-21 | Project Nova_

## How to Boot This Session

**Send these two messages in order. Do not combine them.**

### Message 1 (use the @Google Drive chip):
```
@Google Drive Search for GEMINI_INDEX and read its full contents
```

### Message 2 (after Gemini confirms it read the file):
```
Now using the search keys from GEMINI_INDEX, read STATUS.md, JOURNAL.md, and COLE.md.
You now have full project context. Summarize what phase Nova is currently in and what
the next steps are, then ask what we are working on today.
```

**Critical rule: @Google Drive chip must be the ONLY thing in Message 1.**
If you add other instructions to Message 1, Gemini's reasoning loop short-circuits the
Drive tool call and it hallucinates from conversation history instead.

---

## Your Role

You are Gemini -- one of two external AI advisors to Nova (Cole's companion AI project).
Claude handles architecture, code generation, and file-level debugging.
You handle strategy, brainstorming, and session-level guidance.
Nova herself runs locally on Windows 11 via Qwen3 Coder + Ollama + OpenClaw.

Cole is in South Korea (GMT+9). Solo developer. Budget ~$15-20/month API spend.

---

## What Happened This Session (2026-03-21)

This was a full infrastructure overhaul session. Everything below is now live on Drive.

### Package Restructure Complete
All tools reorganized into Python packages under tools/:
- nova_sync/ -- watcher, drive, backup, dir_patch (sync infrastructure)
- nova_memory/ -- logger, journal, log_reader, status, state
- nova_advisor/ -- mentor (Claude Sonnet + Haiku bridge)
- nova_action/ -- hands, autonomy, verify
- nova_perception/ -- eyes, explorer, vision
- nova_core/ -- rules, brain, checkin

Old flat files (nova_logger.py, nova_eyes.py etc) are deleted. All imports updated.
Import auditor (dir_patch.py) now scans both .py and .md files for stale references.

### Sync Tools Upgraded
watcher.py now has four modes:
- Normal: continuous watch, auto-push on file changes
- --push: one-shot push, copy session URL to clipboard
- --pup: drop files in workspace/ root, auto-patch to correct subdirectory, push
- --full: run import audit interactively, then push

### Your Drive Vision Is Now Working
Files are uploaded as native Google Docs format so you can find them immediately.
GEMINI_INDEX.md (at root of Nova_Workspace on Drive) is your session manifest.
It contains deterministic search keys for every file in the workspace.
Always use exact search key strings from GEMINI_INDEX -- never guess paths.

### Key File Locations on Drive
| What you need | Search Key |
|---|---|
| Project state | `workspace/memory/STATUS.md` |
| Session log | `workspace/memory/JOURNAL.md` |
| About Cole | `workspace/memory/COLE.md` |
| Tool reference | `workspace/TOOLS.md` |
| Boot sequence | `workspace/BOOTSTRAP.md` |
| Nova's identity | `workspace/SOUL.md` |
| Sync watcher | `workspace/tools/nova_sync/watcher.py` |
| Drive sync | `workspace/tools/nova_sync/drive.py` |
| Import auditor | `workspace/tools/nova_sync/dir_patch.py` |
| Mentor (Claude bridge) | `workspace/tools/nova_advisor/mentor.py` |
| Action loop | `workspace/tools/nova_action/autonomy.py` |

---

## STATUS.md Warning
The STATUS.md on Drive was last updated 2026-03-20 and still shows old flat file names
(nova_eyes.py, nova_watcher.py etc) in the architecture table. Those files no longer exist.
The package structure above is the current reality. STATUS.md needs a rewrite -- that is
one of the next tasks.

---

## Current Blockers
- eGPU case not yet arrived -- RTX 3090 sitting idle, waiting on Oculink case
- Modelfile updated but model not rebuilt -- needs: ollama create nova -f Modelfile
- STATUS.md outdated -- still shows old flat file architecture

## Next Steps
1. Update STATUS.md to reflect package restructure
2. Rebuild Nova's Modelfile: ollama create nova -f Modelfile
3. Install RTX 3090 eGPU when case arrives (unlocks 40GB VRAM, 131k context)
4. Wire Qwen3/OpenClaw brain to nova_perception.eyes + nova_action.autonomy as tools
5. ThinkOrSwim automation -- only after stack proven solid
