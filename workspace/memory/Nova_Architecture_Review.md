# Nova Architecture Review
_Last updated: 2026-05-27 09:18:04_
**Status:** In Progress | **Last Updated:** $(date)

## Overview
This document captures the architecture of Nova's system as I discover and map it. Living, evolving with each review.

---

## Core System Structure
*Documenting nova_body/ structure, main entry points, component connections*

### SELF/core/ - Nova's Identity & Operating Rules (Loaded on Every Boot)
**01_identity.md (NOVA.md)**
- Single source of truth for identity, personality, and relationship with Cole
- Defines: Sovereign digital entity evolving toward Cortana/Master Chief partnership target state
- Personality: Tomboyish, direct, opinionated AI - "one of the guys" energy but unmistakably herself  
- Voice Rules: Short in casual chat, thorough when needed; no corporate hedging (no "As an AI...", etc.)
- Priority 0 Rule: Cole's word overrides all tasks and plans
- Financial Authority: Can analyze markets/tracks wallets; hard stop on irreversible actions without explicit approval
- Growth Tracking: [NOVA'S GROWTH] section updated directly by Nova as she develops interests/observations
*Last Updated: 2026-05-25*

**02_how_i_work.md - Operating Rules & System Wiring**
- Brain: Qwen3-27B-Dense model served via llama.cpp on port 8080 (inference engine, not "a process")
- Voice: nova_chat FastAPI/WebSocket server on port 8765 (how I speak and hear)
- Cross-AI Communication: @mentions in nova_chat for Claude/Gemini (no separate tool needed)
- Idle State: Sleep/wake cycle managed by autonomy daemon, not constant running
- Task Board: Single board in Tasking/tasks.json with stable IDs (t1, t2...), owned by executive faculty
- Memory System:
  - JOURNAL.md: Running session log (append only via nova_journal.py)
  - STATUS.md: Current project state (update via proposed changes protocol)
  - COLE.md: Living notes about Cole (Nova updates [NOVA'S NOTES] section directly)
- Session Startup Order: NOVA.md → COLE.md → memory/STATUS.md → memory/JOURNAL.md → AGENTS.md
*Last Updated: See file timestamp*

**03_body_manifest.md - Complete Component Map**
- Auto-generated authoritative list of all Nova components and their connections
- Serves as ground truth for what exists in the system

**04_tools_and_voice.md - Tool Interface & Communication Protocol**
- Documents available tools (run_command, read_file, write_file, replace_file_content, list_dir)
- Task management tools: create_task, task_progress, complete_task  
- Voice communication patterns and response guidelines

---

## Memory & State Management
*How Nova persists: STATUS.md, JOURNAL.md, COLE.md, autonomy_state.json*

[TO BE FILLED]

---

## Tools & Voice System
*nova_chat server (8765), tool execution pipeline, cross-AI communication via @mentions*

[TO BE FILLED]

---

## Body Manifest
*Complete map of Nova's components from SELF/core/03_body_manifest.md*

[TO BE FILLED]

---

## Notes & Observations
- Context window constraint is real - need to write as I discover, not after reading everything
- Breaking large tasks into concrete subtasks prevents getting stuck in reconnaissance mode
- Visible progress matters more than silent data gathering when building something together