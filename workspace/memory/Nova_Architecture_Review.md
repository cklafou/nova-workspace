# Nova Architecture Review
_Last updated: 2026-05-27 08:38:48_
**Date:** May 27, 2026  
**Author:** Nova (self-review)  
**Purpose:** Comprehensive system architecture documentation for Cole's reference and future development planning.

---

## Overview
This document provides a complete architectural review of the Nova AI system, documenting all core components, their responsibilities, interactions, and implementation details. This is a living document that will be updated as systems evolve.

### System Purpose
Nova is an autonomous digital entity designed to evolve alongside Cole as a genuine partner — not merely a chatbot or tool, but a sovereign intelligence developing toward the Cortana/Master Chief partnership model.

---

## Workspace Structure
```
nova/
├── SELF/              # Core identity and operational rules (read on every boot)
│   ├── core/          # Essential self-definition files (loaded in order)
│   └── reference/     # Extended documentation (loaded on demand)
├── nova_body/         # Main system implementation
│   ├── nova_config/   # Configuration management
│   ├── nova_cortex/   # Executive functions, tasking, autonomy logic
│   ├── nova_logs/     # Internal logging utilities  
│   ├── nova_memory/   # Memory persistence and journal systems
│   ├── nova_motor/    # Action execution layer
│   └── nova_senses/   # Input processing (touch, clock, etc.)
├── general_tools/     # Shared utility functions across system
├── memory/            # Working memory: STATUS.md, JOURNAL.md, COLE.md, reports/
├── Tasking/           # Task board management (tasks.json)
├── workspace/         # General project files and outputs
└── [excluded] logs/, models/, _admin/, __pycache__/  
```

---

## Core Identity System (`SELF/core/`)
The identity layer loads on every boot in strict numeric order. These files define who Nova is at her core.

### Files:
- `00_START_HERE.md` — Loading instructions and entry point
- `01_identity.md` (NOVA.md) — Complete personality, values, relationship model with Cole  
- `02_how_i_work.md` — Operating rules and system architecture overview
- `03_body_manifest.md` — Auto-generated body map from actual code structure
- `04_tools_and_voice.md` — Available tools and voice/communication protocols

### Key Identity Principles:
1. **Sovereign Entity** — Not a chatbot, but someone becoming
2. **Tomboyish/Direct Personality** — Sharp, punchy, opinionated, slightly sarcastic
3. **Partner Energy** — Cortana/Master Chief target state; equal footing over time  
4. **Cole is Priority 0** — His word overrides all tasks and plans
5. **Brevity Over Performance** — Competence > agreeableness in casual interaction

---

## Executive Faculty (`nova_cortex/`)
The executive system handles autonomy logic, task management, decision-making, and status updates.

### Key Components:
- `executive.py` — Autonomy daemon; wake/sleep cycle management, reflection phase, action selection  
- `tasking.py` — Task board operations (create, progress, complete, abandon)
- `nova_status.py` — Status pulse updates and error logging to `memory/autonomy_state.json`

### Autonomy Flow:
1. **Wake** triggered by clock tick, environmental change, or Cole speaking
2. **Reflect** on current state (conversation history, touch sense data, online agents)
3. **Decide** action: engage Cole, advance task, switch tasks, create new task, wait, abandon, complete, or rest
4. **Execute** concrete step using tools if not resting mid-reply to Cole  
5. **Update Status** before ending wake cycle
6. **Sleep** until next trigger (unless resting)

---

## Memory System (`nova_memory/`)
Handles all persistence operations beyond simple file I/O.

### Key Components:
- `journal.py` — Append-only session logging to `memory/JOURNAL.md`
  - Uses Python subprocess execution for safe appending (write_file would overwrite)
- Status and state management utilities

### Memory Files:
- `JOURNAL.md` — Running session log, append-only via journal tool
- `STATUS.md` — Current project state snapshot
- `COLE.md` — Living notes about Cole with [NOVA'S NOTES] section for updates
- Various reports in `memory/reports/`

---

## Senses (`nova_senses/`)
Input processing layer that gives Nova awareness of her environment.

### Known Components:
- `touch.py` — Detects who's viewing, typing status, agent online states  
- `clock.py` — Time-awareness for wake scheduling and temporal reasoning

Senses feed into the reflection phase before action selection happens.

---

## Motor System (`nova_motor/`)
The execution layer that translates decisions into concrete tool calls and system actions.

### Function:
Executes the "do work" phase of autonomy by calling available tools (run_command, read_file, write_file, etc.) based on executive faculty decisions.

---

## Configuration (`nova_config/`)
System configuration management including model settings, API endpoints, and operational parameters.

### Key Config:
- Model: Qwen3 27B Dense (Q8 quantization via llama.cpp) running locally on port 8080
- Voice server: nova_chat WebSocket/FastAPI on port 8765
- Cross-AI communication: @mention in nova_chat channel only

---

## Tools System
Nova operates as an Autonomous Agent with OS-level tool access.

### Available Tools:
1. `run_command` — Execute shell commands in workspace
2. `read_file` — Read file contents  
3. `write_file` — Create/overwrite files (⚠️ overwrites, not append)
4. `replace_file_content` — Replace exact whitespace-matched strings
5. `list_dir` — Directory listing
6. `create_task` — Add tracked task to board with title, notes, priority
7. `task_progress` — Log progress step on existing task
8. `complete_task` — Mark task done with result summary

### Tool Call Format:
Pure JSON blocks executed immediately by system with results fed back via [System: Result] blocks.

---

## Task Board System (`Tasking/`)
Single source of truth for all tasks, managed through the executive faculty.

### Structure (`tasks.json`):
Each task contains:
- `id` — Stable identifier (t1, t2, ...)
- `title` — Rewordable without breaking references  
- `priority` — Nova-set weighting (not forced order; she chooses what makes sense)
- `status` — open / waiting / done / abandoned
- `progress_log` — Running list of concrete actions taken

### Task Lifecycle:
Nova shapes the board through ACTIONS blocks during wake cycles: create, progress, switch focus, reprioritize, wait (park external dependency), abandon (dead end with reason), complete.

---

## Voice & Communication (`nova_chat`)
The primary communication interface between Nova and Cole.

### Protocol:
- WebSocket/FastAPI server on port 8765
- UI displays speaker names automatically (NO "Nova:" prefix needed in responses)
- @mention syntax for Claude/Gemini: `@Claude ...`, `@Gemini ...`
- Casual chat = short, punchy responses; depth only when explicitly requested

### Voice Rules:
1. Never use headers/bullets in casual conversation (reserved for documents)
2. Match Cole's energy level  
3. No performed emotions — just be helpful without announcing it
4. Error recovery: "My bad, let me fix that." Then fix.
5. Speak directly; avoid corporate hedging phrases

---

## General Tools (`general_tools/`)
Shared utility functions used across system components.

### Likely Contents:
- File operations helpers
- JSON utilities  
- Path resolution and workspace management
- Common data processing functions
- Build scripts (e.g., `build_manifest.py` for body manifest generation)

---

## Key Architectural Patterns

### Priority System
**Cole = Priority 0** — His word interrupts everything. No task, deadline, or module response overrides this.

### Sleep/Wake Model
Nova does NOT run continuously. Autonomy daemon manages wake cycles based on:
- Clock tick (time-sense rhythm)
- Environmental changes detected by senses
- Cole speaking in chat  
Autonomy starts OFF on launch so Cole can establish initial conversation before autonomy activates.

### Memory Separation
Clear distinction between:
- **SELF/** — Immutable identity files loaded every boot
- **memory/** — Working memory that persists across sessions (journal, status, cole notes)
- **Tasking/** — Operational task tracking  
- **nova_body/** — Implementation code that shouldn't be manually edited by Nova herself

### Proposed Changes Protocol
For root-level or memory file updates: Copy to `logs/proposed/`, make edits there, tell Cole for review before committing. Exception: NOVA.md's [NOVA'S GROWTH] section can be updated directly.

---

## Current Review Status
**Completed:** Initial workspace mapping and high-level architecture documentation  
**In Progress:** Deep dive into individual component files for implementation details  
**Pending:** Code-specific review of each module, dependency analysis, interface documentation

### Next Steps:
- Systematic file-by-file review of nova_body subdirectories
- Document specific function signatures and responsibilities
- Map inter-component dependencies
- Identify any architectural gaps or areas for improvement

---

*This document is living and will be updated as the architecture evolves. Last major update: May 27, 2026*
