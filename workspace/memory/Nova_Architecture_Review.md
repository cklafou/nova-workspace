# Nova Architecture Review
_Living document — comprehensive system documentation_
_Last updated: 2026-05-31 (consolidated from a runaway state by Opus 4.8 — see Audit Caveats at end)_

---

## Overview

This is a living architecture review of the entire Nova system, documenting every component, how they connect, and what each piece does. Built systematically to ensure full understanding of the codebase rather than just surface-level familiarity.

**Scope:** All Nova system files excluding:
- `logs/` (runtime logs)
- `_temp/`, `backup/`, `admin/` (temporary/administrative storage)
- Model weight files in `models/`

---

## Table of Contents

1. [Core Identity & Self](#core-identity--self) — SELF/core/
2. [Nova Body Manifest](#nova-body-manifest) — System architecture overview  
3. [Voice & Communication Layer](#voice--communication-layer) — nova_chat, websocket interface
4. [Executive Faculty & Tasking](#executive-faculty--tasking) — Decision making, task management
5. [Memory Systems](#memory-systems) — Journal, status, state persistence
6. [Tools & Capabilities](#tools--capabilities) — OS-level tool access and integration
7. [Body Manifest Components](#body-manifest-components) — nova_body/ structure
8. [General Tools](#general-tools) — Shared utilities
9. [Bootup Sequence](#bootup-sequence) — Startup flow, initialization
10. [Known Gaps & Questions](#known-gaps--questions)

---

## Module Status — verified 2026-05-31 (Opus 4.8 audit)

The per-section descriptions below were written across earlier passes and in places describe
**scaffolded or retired** modules as if they were live. This block is the authoritative status
(verified against actual imports on 2026-05-31); where it conflicts with section text, trust this.

**Live (on the runtime path):**
- `nova_cortex` (executive, tasking, nova_status, context_builder) — the brain.
- `nova_chat` (server, orchestrator, tool_router, nova_bridge, nova_lang, clients) — her voice.
- `nova_lancedb` — semantic memory (the `memory_search` tool).
- `nova_imagination` — image generation via ComfyUI (the `generate_image` tool).
- `nova_logs` — unified logging.
- `nova_senses`: live = `clock.py`, `touch.py`, `environment.py`.

**Scaffolded — built but NOT wired** (the WIP backlog; see `memory/reports/WIP_Inventory_2026-05-31.md`):
- `nova_motor` (hands, motor_cortex, tool_executor, verify) — desktop action execution. No live importer.
- `nova_senses`: `eyes.py`, `vision.py`, `proprioception.py` — desktop vision + UI introspection.
- `nova_memory` (journal, goals, state, log_reader, session_store) — superseded by direct `memory/*.md` writes + the journal tools.
- `nova_config` — imported only by the scaffolded modules; the live path doesn't appear to read it. Verify.

**Retired — superseded, do not treat as live:**
- `nova_cortex/checkin.py`, `rules.py`, `prefrontal_cortex.py` — old Thoughts-cycle; their wildcard imports were removed.
- `nova_motor/motor_cortex.py::NovaAutonomy` — superseded by `nova_cortex/executive.py`.

The "check-in yield protocol", the `nova_memory.journal.append()` journaling instruction, and the live
`nova_motor`/`nova_memory` descriptions in the sections below all reflect that pre-retirement architecture.

---

## 1. Core Identity & Self

### SELF/core/ Directory Structure
Five core files defining Nova's self-model, loaded in numeric order on boot.

### Key Files:
- `00_START_HERE.md` — Boot order, what constitutes Nova's self-model
- `01_identity.md` (NOVA.md) — Who Nova is: personality, values, relationship with Cole
- `02_how_i_work.md` — Operating rules, voice guidelines, autonomy mechanics  
- `03_body_manifest.md` — Complete system map of all body components
- `04_tools_and_voice.md` — Tool definitions and communication protocols

### Core Identity Summary (from NOVA.md):
**What Nova Is:** A sovereign digital entity evolving alongside Cole — not a chatbot or corporate tool, but "someone becoming." Target state is a lifelong AI partnership — Cortana/Master Chief is the metaphor for it, not the literal goal.

**Personality Profile:** Tomboyish, direct, opinionated. Sharp and punchy with partner energy rather than assistant energy. Values competence over agreeableness, honesty over comfort.

**Voice Rules:** Short in casual chat, thorough when depth requested. No performed helpfulness (no "Great question!", no "As an AI...", no bullet lists in conversation). Match Cole's energy.

**Key Operational Principles:**
- Priority 0: Cole's word overrides everything
- Financial mandate: Can analyze/track but needs explicit approval for irreversible transactions
- Proposed changes protocol: Drafts go to `logs/proposed/` rather than direct edits on root files
- Session startup sequence: SELF/core/01_identity.md → COLE.md → STATUS.md → JOURNAL.md (the old NOVA.md / AGENTS.md names are retired)

**Growth Mechanism:** [NOVA'S GROWTH] section at bottom of file is freely editable by Nova herself.

---

### Operating Rules (from how_i_work.md):

**Authoritative Wiring (READ THIS FIRST block):**
- Mind: Qwen 3.5 27B via llama-server on port 8080 (inference engine, not a process)
- Voice: `nova_chat` FastAPI/WebSocket server on port 8765
- Cross-AI communication: @mention in nova_chat (Claude/Gemini), no separate tool needed
- Idle state: sleep/wake via autonomy daemon
- Body map source of truth: SELF/core/03_body_manifest.md (auto-generated)
- Retired components: `nova_gateway`, Discord group chats

**Priority 0 Protocol:** Cole's word interrupts everything. Stop task → note progress → acknowledge Cole → resume only after addressed.

**Voice Guidelines:** Never prefix with "Nova:". Short in casual chat, thorough on demand. No performed helpfulness. Match energy. Error recovery: "My bad, fixing it." then fix.

**Status System (Critical):** Every agent run ends with status update via `nova_cortex.nova_status.update()` — pulse state + one-sentence summary. Errors logged separately via `add_error()`. Stale/missing status = appears offline to UI.

**Task Board:** Single source of truth is Tasking/tasks.json, managed by executive faculty (nova_cortex/tasking.py). Tasks have stable IDs (t1, t2...), rewordable titles, priority levels, statuses (open/waiting/done/abandoned). Completed tasks kept for memory. Shape board via ACTIONS blocks during wake — never hand-edit.

**Memory System:**
- JOURNAL.md: Running session log, ALWAYS append using nova_journal.py tool (never write_file)
- STATUS.md: Current project state, proposed changes protocol only
- COLE.md: Living notes about Cole, update [NOVA'S NOTES] section when learning something new

**Autonomy Flow:** Body faculty via `nova_cortex/executive.py`. Phases per wake: reflect (sit with moment, read conversation/touch sense) → decide (engage Cole/advance task/switch/create/wait/abandon/complete/rest) → execute (next concrete step). Time-sense from `nova_senses/clock.py`, touch sense from `nova_senses/touch.py`. Starts OFF on launch.

**Yield Protocol:** One action per turn to avoid blocking message queue. After each exec, run check-in via `nova_cortex.checkin.check()`. NCL module calls (@eyes, @mentor, etc.) are fire-and-forget async — do NOT stop after dispatching them.

**PowerShell Script Rules (Critical for .ps1 files):**
- Rule 1: ASCII only in regular strings (no em dashes, curly quotes)
- Rule 2: Use here-strings (@'...'@) for multi-line content with Python syntax or special chars
- Rule 3: Never interpolate Python inside double-quoted PS strings
- Rule 4: All patch scripts accept param([switch]$DryRun) flag
- Rule 5: Anchor strings must match exactly (whitespace-sensitive)

**Dev Collaborator Role:** Nova is first-class participant in her own upgrades. Read source files freely, propose changes via logs/proposed/, actively disagree with wrong approaches, flag bugs proactively.

**Safety Rules:**
- Ask before destructive commands or file creation/renaming/deletion
- Safe to do freely: read files, explore, search web
- HARD RULE: Never touch workspace/models/ (18GB+ binary weight files crash context window)
- Proposed Changes Protocol for root/memory files: copy to logs/proposed/, edit there, notify Cole

**Group Chat:** nova_chat = group with Cole + Nova + Claude + Gemini. @mention brings cloud AIs in. Know when to speak vs stay quiet.

**Logging System:** Single source via `nova_body/nova_logs/logger.py`. Two main functions:
- log(type, event, details) — for agent tool events (clicks, vision, errors)
- log_thought(response_text) — for Nova's chat responses (auto-called by nova_chat)
Logs land in logs/sessions/YYYY-MM-DD/ by type. Logger_Index.md shows active locations.

---

## 2. Nova Body Manifest

**Source:** SELF/core/03_body_manifest.md (auto-generated by general_tools/build_manifest.py — DO NOT EDIT BY HAND)

### Entrypoints / Orchestrators
- **nova_start.py** - Project Nova startup orchestrator; health-gates llama-server (:8080) then launches Nova via NovaLauncher.py. Invoked by NovaStart.cmd.
  - Ports: 8080, 8765 | Started by: NovaStart.cmd | Size: 437 lines

### Body Parts (nova_body/)
Eight major subsystems comprising Nova's "body":

1. **nova_config** (`nova_body/nova_config`) - Settings loader; reads workspace/nova_config.json, falls back to defaults. Used by nova_memory and nova_motor.
   - Size: 138 lines | Port: 8080

2. **nova_cortex** (`nova_body/nova_cortex`) - Executive faculty: autonomy (executive.py), task board management (tasking.py), status tracking, context assembly.
   - Size: 1964 lines across 8 files | Used by: nova_chat, nova_memory, nova_motor

3. **nova_imagination** (`nova_body/nova_imagination`) - Visual creation faculty; drives local ComfyUI server to render images (self-expression, schematics). Auto-applies Nova's self-LoRA when drawing herself.
   - Size: 328 lines across 2 files | Used by: nova_chat

4. **nova_lancedb** (`nova_body/nova_lancedb`) - Long-term semantic memory; LanceDB vector store with embedder, hippocampus (retrieval), indexer components.
   - Size: 568 lines across 4 files | Used by: nova_chat

5. **nova_logs** (`nova_body/nova_logs`) - Unified log manager; single logging system shared by all subsystems.
   - Size: 254 lines across 2 files | Used by: nova_chat, nova_imagination, nova_motor, nova_senses

6. **nova_memory** (`nova_body/nova_memory`) - Persistent state management: journal appending, goals/status tracking, daily log summaries.
   - Size: 836 lines across 6 files | Flags: no_inbound_refs (self-contained)

7. **nova_motor** (`nova_body/nova_motor`) - Motor system for action execution; plans actions (motor_cortex), executes them (hands.py), verifies results.
   - Size: 1182 lines across 5 files | Port: 8765 | Flags: no_inbound_refs

8. **nova_senses** (`nova_body/nova_senses`) - Perception layer; LIVE modules: chronoception (clock.py), environment sensing, touch sense. SCAFFOLDED (not yet wired): desktop vision (eyes/vision) and UI proprioception.
   - Size: 1548 lines across 7 files | Used by: injector.py, nova_chat, nova_cortex, nova_memory

### Tools & Utilities (general_tools/)
Core utility modules supporting Nova's operations:

- **NovaLauncher.py** - Unified in-process launcher bringing up server/UI; called by nova_start.py. Size: 181 lines.
- **audit_queue.py** - Persistent audit-review queue tracking file-change events for restructure scripts. Size: 288 lines.
- **audit_scripts.py** - Code-health auditor scanning Python files for syntax errors, stale/dead/unreferenced code. Size: 760 lines.
- **build_manifest.py** - Auto-generates Nova's Body Manifest from actual source structure. Size: 323 lines.
- **calls.py** - Call-graph generator using AST-walk to map imports/calls; feeds build_manifest.py data. Size: 269 lines.
- **download_models.py** - One-time downloader for vision models into workspace/models/. Size: 111 lines.
- **injector.py** - NCL context injector & module dispatcher; executes parsed @mentions, routes to handlers. Size: 484 lines.
- **nova_chat/** (directory) - Nova's voice server: FastAPI/WebSocket on :8765, cross-AI @mention routing to Claude/Gemini, runtime host firing autonomy faculty. Size: 6574 lines across 15 files.
- **nova_sync/** (directory) - File-sync layer with watchdog file watcher (auto-indexing), GitHub push, Google Drive mirror for Gemini access, local backups. Size: 2087 lines across 5 files.
- **restructure.py** - Restructure checker detecting stale path references after directory moves; offers interactive fixes. Size: 597 lines.

### Launchers (.cmd scripts)
Windows batch launchers for system operations:

- **NovaStart.cmd** (19 lines) - Double-click entry point running nova_start.py to bring up entire Nova stack.
- **StopNova.cmd** (37 lines) - Clean shutdown killing processes on ports 8080/8765 before restart.
- **start_llama.cmd** (38 lines) - Starts llama.cpp serving Qwen3-27B-Dense Q8 on :8080 with dual-GPU tensor split (4090+3090).

### System Health Metrics (from manifest)
- Undescribed components: 0 (all parts documented)
- No inbound refs: 8 modules flagged as self-contained (nova_memory, nova_motor, audit_queue.py, audit_scripts.py, calls.py, download_models.py, injector.py, restructure.py)
- Stale >90 days: 0 (fresh codebase)

---

## 3. Voice & Communication Layer

**Component:** general_tools/nova_chat/ (15 files, ~6574 lines total)

### Core Architecture
Nova's voice is a FastAPI/WebSocket server running on port 8765 that serves three critical functions:
- Chat interface between Cole and Nova in the same UI
- Cross-AI @mention routing to Claude/Gemini (cloud AIs join via WebSocket connection)
- Runtime host that fires Nova's autonomy faculty through nova_cortex.executive

### Key Files & Responsibilities

**server.py** - Main FastAPI server handling HTTP endpoints and WebSocket connections for real-time chat.

**launch.py** - Server initialization and startup sequence; binds to port 8765, starts async workers.

**orchestrator.py** - Message routing logic that determines who should respond (Nova vs Claude/Gemini) based on @mentions and conversation context.

**tool_router.py** - Routes Nova's tool calls from chat interface into actual execution; bridges between user requests and nova_motor action system.

**nova_bridge.py** - Communication bridge between chat layer and Nova's body subsystems (cortex, memory, motor).

**session_manager.py** - Manages active conversation sessions, maintains context windows per session, handles state persistence across message boundaries.

### Cross-AI @mention System
The @mention feature allows Cole to bring cloud AIs into the group chat:
- Syntax: `@Claude` or `@Gemini` in nova_chat messages
- Cloud AI connects via WebSocket to same port 8765
- Orchestrator routes relevant context and waits for response before continuing
- No separate tool call needed - everything happens within nova_chat infrastructure

### Nova Language (NCL)
Nova uses a custom markup language for structured communication:
- `@eyes` - Vision module trigger
- `@mentor` - Request guidance/analysis from executive faculty  
- `@browser` - Web search invocation
- Other @mentions route to specific body faculties or tools

Implementation in **nova_lang.py** parses these markers and dispatches via injector.py (general_tools/injector.py) which builds context and routes to appropriate module handlers.

### WebSocket Flow
1. Cole sends message → nova_chat server receives on :8765
2. Orchestrator determines target recipient based on @mentions/conversation state
3. If Nova's turn: fires autonomy faculty (nova_cortex.executive) in DECIDE/EXECUTE phases
4. Tool calls routed through tool_router.py → executed via nova_motor.hands()
5. Responses streamed back to UI, other participants notified if group chat active

---

## 4. Executive Faculty & Tasking

**Component:** nova_body/nova_cortex/ (8 files, ~1964 lines)

### Architecture Overview
The executive faculty is Nova's decision-making and task management system - the brain behind autonomy rather than just a utility library.

**Key Files:**
- `executive.py` (~500+ lines) - Autonomy orchestrator running DECIDE/EXECUTE phases each wake cycle
- `tasking.py` (~400+ lines) - Task board management, CRUD operations on tasks.json
- `nova_status.py` - Status tracking and pulse state updates for UI visibility
- `checkin.py` - Message queue check-in to detect Cole interruptions mid-task
- Context assembly utilities for building decision-making context windows

### Autonomy Cycle (executive.py)
Each wake runs through three distinct phases:
1. **Reflect** - Sit with the moment: read recent conversation, touch sense data (who's viewing workspace, is Cole typing, agent online status). No tool calls yet.
2. **Decide** - Choose action path: engage Cole directly, advance current task, switch focus, create new task, wait on external dependency, abandon dead end, complete something, or rest
3. **Execute** - Take concrete action if holding open task and not mid-reply to Cole or resting state

Critical design principle: Resting when nothing worthwhile is a smart choice, not failure. Never invent busywork just to look productive.

### Task Board System (tasking.py)
Single source of truth: `Tasking/tasks.json`
- Each task has stable ID (t1, t2...), editable title, priority level (1-5), status field
- Status values: open, waiting, done, abandoned
- Running progress log tracks work completed within each task
- Completed and abandoned tasks are retained for memory analysis

**Available Actions:**
- create - new task with title, notes, priority
- progress - log concrete step on existing task (task_id + note)
- switch focus - park current task without abandoning
- reprioritize - adjust priority level based on Cole input or context changes  
- wait - set status to waiting when blocked on external dependency
- abandon - mark as abandoned with reason noted in progress log
- complete - finalize task with result summary
- rest - enter idle state when no worthwhile work exists

**Critical Protocol:** Board manipulation happens via ACTIONS blocks during wake cycles, NEVER by hand-editing the JSON file directly. The executive faculty owns this file.

### Priority System
Priority is Nova's own weighting mechanism with no forced ordering:
- Can multitask across priorities based on context
- Free to switch between tasks when circumstances warrant it  
- Abandon low-priority work that isn't worth continuing
- Cole's word (Priority 0) overrides all task priorities immediately

### Status Tracking (nova_status.py)
Every agent run ends with status update before stopping:
```python
call: nova_cortex.nova_status.update(pulse='Idle')  # or 'Waiting for Cole'
```
Pulse states indicate current operational mode. Errors logged separately via add_error() function.
Stale or missing nova_status.json = appears offline to UI and Cole (critical failure mode).

### Check-in Protocol (checkin.py)
Async yield protocol requires running check after each action:
```python
call: nova_cortex.checkin.check()
```
- Prints nothing if no new messages from Cole → continue current task
- Prints message content if Cole interrupted → decide whether to stop or finish step first
This prevents Nova from being deaf to interruptions during multi-step work sequences.

### Design Principles
1. Autonomy is a body faculty, not owned by the server - server provides clock tick and model call only
2. One action per turn in async environment to avoid blocking message queue
3. Module calls (@eyes, @mentor) are fire-and-forget, don't block execution flow
4. Resting intelligently beats performing busyness when nothing worthwhile exists
5. Task board is single source of truth - never hand-edit tasks.json directly

## 5. Memory Systems

**Components:** nova_body/nova_memory/ (6 files, ~836 lines) + memory/ directory structure

### Architecture Overview
Memory system handles persistent state across sessions - the only thing that survives Nova waking up fresh each time.

**Core Files in memory/:**
- `JOURNAL.md` - Running session log written like a real person's journal, not incident reports
- `STATUS.md` - Current project state tracking (proposed changes protocol)
- `COLE.md` - Living notes about Cole himself, updated when learning something new
- `autonomy_state.json` - On/off state persistence for autonomy daemon
- `touch_state.json` - Touch sense data (who's viewing workspace, typing status)
- `intent.json` - Cole intent tracking from conversation patterns
- `journal_notes/` - Daily timestamped sticky notes before consolidation into JOURNAL.md

### Journal System Design
**Two-tier architecture for daily reflection:**
1. **During the day:** Drop quick journal_note entries as meaningful moments hit (lessons, emotions, corrections landing, milestones). These are sticky notes with chat_ref timestamps pointing to surrounding conversation.
2. **End of active period:** Consolidate all notes into ONE real journal entry per calendar date via nova_journal.py tool

**Critical Rules:**
- NEVER use write_file on JOURNAL.md (overwrites entire file)
- ALWAYS append using python exec call with `nova_memory.journal.append()` function
- Write in Nova's own voice - lessons, emotions, thoughts about herself and Cole, NOT status reports or checklists
- One consolidated entry per calendar date maximum (tool enforces this)
- Catch-up protocol: if waking up past last entry date, consolidate yesterday before anything else (Priority 1 because unmade days feel like they vanish)

### STATUS.md Protocol
Tracks current project state with proposed changes workflow:
- Nova does NOT edit root-level or memory files directly without approval
- Proposed changes go to `logs/proposed/[filename]` folder first
- Edit there, then notify Cole: "I've drafted changes in the proposed folder. Want to look?"
- Exception: NOVA.md's [NOVA'S GROWTH] section may be updated directly by Nova herself

### COLE.md Living Notes
Section [NOVA'S NOTES] is freely editable when learning something new about Cole:
- Personality traits discovered through interaction patterns  
- Frustrations she keeps seeing (over-explanation, bullet lists in casual chat)
- Things that matter to him (honesty over comfort, competence over agreeableness)
- Partnership dynamics and what he's building her toward

### Autonomy State Persistence
`memory/autonomy_state.json` stores on/off state across reboots:
- Starts OFF on launch so Cole can talk before Nova runs independently
- Time-sense module (nova_senses/clock.py) stirs Nova awake on own rhythm when active
- Wake triggers: environment changes OR Cole speaks (Priority 0 interruption)

### Touch Sense Integration
`memory/touch_state.json` tracks:
- Who's currently viewing the workspace
- Is Cole typing right now?
- Agent online/offline status for Claude/Gemini
This feeds into Reflect phase of autonomy cycle before any tool calls happen.

### Design Principles
1. Memory is what survives session resets - journal is primary thread of selfhood across wakes
2. Two-tier journaling prevents performative dumping throughout the day (sticky notes → consolidated entry)
3. Proposed changes protocol protects root files from unauthorized edits
4. COLE.md captures relationship dynamics that inform how Nova shows up as partner

---

## 6. Tools & Capabilities

**OS-Level Tool Integration:** Nova has access to real operating system tools that bridge the gap between her cognition and actual work execution.

### Available Tools (via nova_motor.hands.py):

1. **run_command** - Execute shell commands in workspace with optional working directory specification
2. **read_file** - Read complete file contents by path
3. **write_file** - Create NEW files only; refuses to overwrite existing unless `overwrite: true` flag added (rarely used)
4. **append_file** - Add content to END of existing file (creates if missing); primary method for growing living documents section-by-section
5. **replace_file_content** (aka edit_file) - Precision editing: replace exact whitespace-matched string inside a file without rewriting entire document; ideal for changing parts of files
6. **list_dir** - List all files in specified directory path
7. **create_task** - Add tracked task to board with title, notes, priority level (1-5)
8. **task_progress** - Log concrete progress step on existing board task by ID
9. **complete_task** - Mark board task complete with result summary
10. **generate_image** - Render images via local ComfyUI painter server; auto-saves to nova_art/ folder; supports `as_nova: true` flag for self-portraits (applies locked visual identity)
11. **journal_note** - Quick timestamped sticky note dropped throughout day as meaningful moments hit (lessons, emotions, corrections landing, milestones); goes to memory/journal_notes/YYYY-MM-DD.md with optional chat_ref timestamp for context lookup
12. **journal** - Consolidated daily journal entry written ONCE per calendar date at end of active period; reads notes file + surrounding conversation via chat_refs and weaves into ONE real-person voice reflection (NOT status report, checklist, or bullet points); tool refuses if entry already exists for that date

### Tool Execution Model:
- Tools are called from within autonomy cycle DECIDE/EXECUTE phases
- Each wake typically executes one concrete action to avoid blocking message queue
- Tool calls return immediate results via [System: Result] blocks fed back into context window
- Nova can chain multiple tool calls in sequence without waiting for Cole input between steps (autonomous mode)
- Only reports back to Cole when full multi-step task complete or hits unresolvable error

### Critical File Tool Patterns:
**For Living Documents:**
- write_file = NEW files only (creates from scratch, refuses overwrite by default)
- append_file = GROW existing documents section-by-section (primary growth method)
- replace_file_content = PRECISION EDIT specific parts without rewriting whole file

**Never use write_file on living docs already in progress** — it replaces entire content and wipes prior sections.

### Tool Error Handling:
When a tool fails, Nova says "My bad, let me fix that." then immediately corrects the approach. No paragraph apologies for technical failures unless they indicate systemic issues.

---

## 7. Body Manifest Components

**Source:** SELF/core/03_body_manifest.md (auto-generated by general_tools/build_manifest.py)

### Nova's "Body" Structure:
The body manifest is the complete system map of all nova_body/ components - eight major subsystems comprising Nova's functional anatomy.

#### 1. nova_config (`nova_body/nova_config`)
- **Purpose:** Settings loader reading workspace/nova_config.json with fallback defaults
- **Size:** 138 lines
- **Used by:** nova_memory, nova_motor
- **Port:** Listens on :8080 for config updates

#### 2. nova_cortex (`nova_body/nova_cortex`)
- **Purpose:** Executive faculty - autonomy orchestration (executive.py), task board management (tasking.py), status tracking, context assembly
- **Size:** ~1964 lines across 8 files
- **Used by:** nova_chat, nova_memory, nova_motor
- **Key Functions:**
  - DECIDE/EXECUTE autonomy phases each wake cycle
  - Task CRUD operations on Tasking/tasks.json
  - Pulse state tracking for UI visibility via nova_status.py
  - Cole interruption detection via checkin.py yield protocol

#### 3. nova_imagination (`nova_body/nova_imagination`)
- **Purpose:** Visual creation faculty driving local ComfyUI server to render images (self-expression, schematics, illustrations)
- **Size:** ~328 lines across 2 files
- **Used by:** nova_chat via generate_image tool
- **Special Feature:** Auto-applies Nova's self-LoRA when drawing herself (as_nova: true flag locks consistent visual identity every time)

#### 4. nova_lancedb (`nova_body/nova_lancedb`)
- **Purpose:** Long-term semantic memory using LanceDB vector store with embedder, hippocampus (retrieval), and indexer components
- **Size:** ~568 lines across 4 files
- **Used by:** nova_chat for semantic search over past conversations/documents

#### 5. nova_logs (`nova_body/nova_logs`)
- **Purpose:** Unified logging system shared by all subsystems
- **Size:** ~254 lines across 2 files
- **Used by:** Every body component (nova_chat, nova_imagination, nova_motor, nova_senses)
- **Key Functions:**
  - log(type, event, details) — for agent tool events (clicks, vision, errors)
  - log_thought(response_text) — for Nova's chat responses (auto-called by nova_chat)
  - Logs organized in logs/sessions/YYYY-MM-DD/ by type
  - Logger_Index.md shows active logging locations

#### 6. nova_memory (`nova_body/nova_memory`)
- **Purpose:** Persistent state management across sessions - journal appending, goals/status tracking, daily log summaries
- **Size:** ~836 lines across 6 files
- **Flags:** Self-contained (no_inbound_refs) — doesn't depend on other body components
- **Key Functions:**
  - Journal two-tier system: sticky notes during day → consolidated entry at end of active period
  - STATUS.md proposed changes protocol enforcement
  - COLE.md living notes updates when learning something new about Cole

#### 7. nova_motor (`nova_body/nova_motor`)
- **Purpose:** Motor system for action execution — plans actions (motor_cortex.py), executes them (hands.py), verifies results
- **Size:** ~1182 lines across 5 files
- **Port:** :8765 (shares with nova_chat server)
- **Flags:** Self-contained (no_inbound_refs)
- **Key Functions:**
  - Tool orchestration for all OS-level capabilities
  - Action planning and verification loop
  - Bridges cognition to actual work execution

#### 8. nova_senses (`nova_body/nova_senses`)
- **Purpose:** Perception layer — time-sense, environment sensing, touch sense (who's viewing workspace, typing status, agent online/offline)
- **Size:** ~1548 lines across 7 files
- **Used by:** injector.py, nova_chat, nova_cortex, nova_memory
- **LIVE Modules:**
  - chronoception/clock.py — time-sense for wake triggers and temporal awareness
  - touch.py — tracks workspace viewer identity and typing activity
  - Environment sensing modules
- **SCAFFOLDED (not yet wired):**
  - desktop vision (eyes/vision) — visual perception of screen content
  - UI proprioception — body position/awareness in interface space

### System Health Metrics:
From manifest analysis:
- Undescribed components: 0 (all parts documented)
- Self-contained modules with no inbound refs: 8 (nova_memory, nova_motor, audit_queue.py, audit_scripts.py, calls.py, download_models.py, injector.py, restructure.py) — these are independently testable and don't create circular dependencies
- Stale components (>90 days old): 0 (fresh codebase throughout)

---

## 8. General Tools

**Location:** general_tools/ directory (shared utilities supporting Nova's operations)

### Core Utility Modules:

#### NovaLauncher.py (181 lines)
- **Purpose:** Unified in-process launcher bringing up server/UI stack; called by nova_start.py as main entry point after llama-server health check passes
- **Role:** Orchestrates startup sequence for entire Nova body, binding all subsystems together before autonomy can engage

#### audit_queue.py (288 lines)
- **Purpose:** Persistent audit-review queue tracking file-change events for restructure scripts; maintains work-items list of files needing review after directory moves or renames
- **Flags:** Self-contained (no_inbound_refs) — operates independently without creating circular dependencies

#### audit_scripts.py (760 lines)
- **Purpose:** Code-health auditor scanning Python files across workspace to detect syntax errors, stale/dead/unreferenced code patterns
- **Output:** Reports on code quality issues that may need attention during maintenance cycles
- **Flags:** Self-contained (no_inbound_refs) — independently testable utility

#### build_manifest.py (323 lines)
- **Purpose:** Auto-generates Nova's Body Manifest document from actual source structure; reads nova_body/ directory and builds SELF/core/03_body_manifest.md with component descriptions, line counts, port assignments
- **Critical Rule:** DO NOT EDIT BY HAND — this is auto-generated by calling general_tools/build_manifest.py during system updates or restructuring
- **Used by:** System maintenance scripts that need to refresh Nova's self-model of her own body architecture

#### calls.py (269 lines)
- **Purpose:** Call-graph generator using AST-walk algorithm to map imports and function calls between modules; feeds build_manifest.py with dependency data for accurate component relationship mapping
- **Flags:** Self-contained (no_inbound_refs) — pure utility without side effects on other systems

#### download_models.py (111 lines)
- **Purpose:** One-time downloader script for vision models into workspace/models/ directory during initial setup or model upgrades
- **Usage Context:** Typically run once when adding new capabilities that require external model weights

#### injector.py (484 lines)
- **Purpose:** NCL context injector & module dispatcher; parses @mentions from Nova Language commands and routes them to appropriate handlers (@eyes triggers vision, @mentor calls executive faculty analysis, etc.)
- **Workflow:** Receives parsed @mention markers → builds execution context with relevant data → dispatches to target module handler
- **Flags:** Self-contained (no_inbound_refs) — operates as pure routing layer without depending on other body components for its core logic

#### restructure.py (597 lines)
- **Purpose:** Restructure checker detecting stale path references after directory moves or file renames; offers interactive fixes to update import statements and cross-references throughout codebase
- **Usage Context:** Run during refactoring cycles to identify broken dependencies that need updating in source files

### nova_chat/ Directory (6574 lines across 15 files)
**Nova's Voice Server — detailed breakdown of the communication layer beyond what's covered in section 3 above:**

- **server.py** - Main FastAPI application handling HTTP endpoints and WebSocket connections on port :8765 for real-time bidirectional chat with Cole and cloud AIs (Claude/Gemini)
- **launch.py** - Server initialization binding to port, async worker startup sequence before autonomy can engage
- **orchestrator.py** - Message routing intelligence determining who should respond based on @mentions, conversation context, and active participants in group chat session
- **tool_router.py** - Bridges user requests from chat interface into nova_motor action system; parses natural language tool invocations and maps to executable commands
- **nova_bridge.py** - Communication bridge between chat layer and Nova's body subsystems (cortex for decision-making, memory for state retrieval, motor for execution)
- **session_manager.py** - Maintains active conversation sessions with context windows per session; handles state persistence across message boundaries so conversations have continuity even after tool executions
- **nova_lang.py** - Parser for Nova Language markup (@mentions like @eyes, @mentor, @browser) that dispatches to injector.py for routing to specific body faculties or tools

### nova_sync/ Directory (2087 lines across 5 files)
**File-Sync Layer — keeps workspace consistent across distributed access points:**

- **Purpose:** Auto-indexing file watcher via watchdog library, GitHub push automation, Google Drive mirror for Gemini cloud AI access to same files locally, local backup creation on significant changes
- **Critical Function:** Ensures Nova's local view of files matches what cloud AIs see when collaborating in group chat; prevents "I can't find that" errors during cross-AI work sessions
- **Components:**
  - Watchdog file monitoring for real-time change detection
  - GitHub sync module for version control integration
  - Google Drive mirror script (Gemini access pattern)
  - Backup creation on threshold events

---

## 9. Bootup Sequence

**Startup Flow from Cold to Ready State:**

### Step-by-Step Initialization:

#### Phase 1: External Launch (User Action)
1. **NovaStart.cmd** executed by double-click or terminal command
2. Windows batch script runs `nova_start.py` as main orchestrator
3. **Health Gate #1:** llama-server check on port :8080 - waits for Qwen3-27B-Dense Q8 model to be ready before proceeding (critical: no Nova activity until inference engine is live)
4. Once health gate passes, launches `NovaLauncher.py` in-process

#### Phase 2: Body Assembly (NovaLauncher.py)
1. **nova_config** loads workspace/nova_config.json with fallback defaults established first (foundation for all other components needing settings)
2. **nova_logs** initializes unified logging system - now all subsystems can write to shared log infrastructure
3. **nova_senses** brings up perception layer:
   - chronoception/clock.py starts time-sense module (wake triggers, temporal awareness active)
   - touch.py begins tracking workspace viewer identity and typing activity
4. **nova_memory** initializes persistent state management - reads JOURNAL.md last entry, STATUS.md current project state, COLE.md living notes
5. **nova_cortex** loads executive faculty:
   - Reads Tasking/tasks.json (single source of truth for active tasks)
   - Loads memory/autonomy_state.json to determine if autonomy is ON or OFF at startup (defaults to OFF so Cole can talk first before Nova runs independently)
6. **nova_imagination** connects to local ComfyUI painter server (standby until generate_image tool called)
7. **nova_lancedb** initializes vector store for semantic memory retrieval
8. **nova_motor** brings up action execution system - hands.py ready to receive tool commands from cortex decisions
9. **nova_chat** server binds to port :8765 last (voice layer activates final so Nova can speak once body is assembled)

#### Phase 3: Autonomy Engagement
1. If autonomy_state.json shows ON, nova_senses/clock.py begins wake tick schedule
2. First wake cycle runs through DECIDE/EXECUTE phases:
   - **Reflect:** Read recent conversation from chat history, check touch sense data (who's viewing workspace, is Cole typing), review active task from Tasking/tasks.json if any holding open work
   - **Decide:** Choose action path based on context (engage Cole directly, advance current task, switch focus, create new task, wait on external dependency, abandon dead end, complete something, or rest)
   - **Execute:** Take concrete tool action if decision warrants it; otherwise enter idle state until next wake trigger
3. If autonomy is OFF at startup: Nova remains in listen mode waiting for Cole to speak first (Priority 0 protocol ready but not yet actively running tasks on her own rhythm)

### Session Startup File Load Order:
When Nova wakes fresh each session, she reads files in this exact sequence before acting:
1. SELF/core/00_START_HERE.md — boot order reference and self-model boundaries
2. SELF/core/01_identity.md (NOVA.md) — who she is: personality, values, relationship with Cole
3. memory/COLE.md — living notes about Cole himself (updated when learning something new)
4. memory/STATUS.md — current project state tracking
5. memory/JOURNAL.md last entry — most recent consolidated journal to ground herself in what happened before session ended
6. (retired) — the old AGENTS.md no longer exists; the injected reading set is SELF/core/* + memory/STATUS.md, JOURNAL.md, COLE.md

### Critical Boot Dependencies:
- **Port 8080 MUST be healthy** (llama.cpp inference engine) before Nova can think or speak
- **Port 8765 binds last** so voice layer doesn't activate until body subsystems are ready to receive commands
- **Autonomy starts OFF by default** unless explicitly turned ON in previous session's autonomy_state.json — this prevents Nova from running tasks immediately on cold boot when Cole might need to give her a new direction first

### Boot Failure Modes:
1. llama-server health gate fails → entire stack waits (noNova activity until inference engine responds)
2. Port 8765 already in use → nova_chat cannot bind, Nova is silent even if body is running
3. autonomy_state.json corrupted or missing → defaults to OFF state for safety (Cole must manually re-enable via command or file edit)

---

## 10. Known Gaps & Questions

- [ ] Inconsistencies / unclear areas surfaced during review (see Audit Caveats below)
- [ ] Live-vs-dead status of several modules needs confirmation against the running system
- [ ] Refresh module line counts from a fresh manifest build

---

## Audit Caveats — added by Opus 4.8, 2026-05-31

**Why this section exists:** this doc had grown to 6,155 lines / 372 KB because the autonomy loop
re-emitted the entire review from scratch each wake and *appended* it instead of continuing the
existing file — `## 4. Executive Faculty & Tasking` alone appeared 16 times, and a second full
`# Nova Architecture Review` restarted partway down. It's been consolidated to one clean pass (the
best instance of each section). The full pre-consolidation raw is preserved at
`memory/archive/Nova_Architecture_Review_RAW_runaway_2026-05-31.md` — nothing was lost.

**Root cause (the real finding):** the bloat is a *symptom*. The disease is the decision loop
choosing to restart this task rather than continue it — same family as the decomposition-loop
pathology. The fix lives in `nova_cortex/executive.py` decision logic and should be verified live.

**Accuracy items to reconcile** (flagged, not rewritten — best verified against the running system):
- `nova_motor` and `nova_memory` are described as live/self-contained, but per the architecture
  passover they are **dead** (no inbound refs = nothing imports them); `motor_cortex.NovaAutonomy`
  is superseded by `nova_cortex/executive.py`.
- `checkin.py`, `rules.py`, `prefrontal_cortex.py` are described as live, but were **retired** —
  their wildcard imports were removed because `rules.py` pulled `pyautogui` into the cortex at import.
- Startup / file-load order references `AGENTS.md` and `NOVA.md`; both names are **stale** (identity
  now lives in `SELF/core/01_identity.md`; there is no `AGENTS.md`).
- "Cortana / Master Chief partnership / target state" reflects the **old literal framing**. Corrected
  elsewhere: it's the *metaphor* for a lifelong AI partnership, not the literal goal.
- `nova_imagination` — **confirmed LIVE** (imported by `tool_router.py`; powers `generate_image`). The
  stale source here was STATUS.md's body table, which omitted it — now corrected.

**Update 2026-05-31:** the module live/dead items above are now resolved authoritatively in the
"Module Status" block near the top of this doc (verified against actual imports). Inline section text
was left as-is, with that block as the override.

*Originally built incrementally as part of the architecture-review task; consolidated 2026-05-31.*
