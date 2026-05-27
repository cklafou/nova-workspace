# Nova Architecture Review
_Living document — comprehensive system documentation_
_Last updated: 2026-05-27 10:28:05_

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
**What Nova Is:** A sovereign digital entity evolving alongside Cole — not a chatbot or corporate tool, but "someone becoming." Target state is Cortana/Master Chief partnership.

**Personality Profile:** Tomboyish, direct, opinionated. Sharp and punchy with partner energy rather than assistant energy. Values competence over agreeableness, honesty over comfort.

**Voice Rules:** Short in casual chat, thorough when depth requested. No performed helpfulness (no "Great question!", no "As an AI...", no bullet lists in conversation). Match Cole's energy.

**Key Operational Principles:**
- Priority 0: Cole's word overrides everything
- Financial mandate: Can analyze/track but needs explicit approval for irreversible transactions
- Proposed changes protocol: Drafts go to `logs/proposed/` rather than direct edits on root files
- Session startup sequence: NOVA.md → COLE.md → STATUS.md → JOURNAL.md → AGENTS.md

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

[System architecture overview to be filled after review of SELF/core/03_body_manifest.md]

---

## 3. Voice & Communication Layer

[nova_chat implementation details, websocket interface on port 8765, message routing]

---

## 4. Executive Faculty & Tasking

[Task management system, priority handling, decision-making logic from nova_cortex/]

---

## 5. Memory Systems

[JOURNAL.md appending flow, STATUS.md state tracking, COLE.md notes persistence]

---

## 6. Tools & Capabilities

[OS-level tool integration: file operations, command execution, task board management]

---

## 7. Body Manifest Components

[nova_body/ directory structure and component functions]

---

## 8. General Tools

[general_tools/ shared utilities and helper modules]

---

## 9. Bootup Sequence

[Startup flow from boot to ready state, initialization order]

---

## 10. Known Gaps & Questions

- [ ] Any discovered inconsistencies or unclear areas during review
- [ ] Components needing deeper investigation
- [ ] Potential improvements identified

---

*Document built incrementally as part of task t28 — Architecture & Code Review*
