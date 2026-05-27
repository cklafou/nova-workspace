# Nova Architecture Review
_Last updated: 2026-05-27 09:13:28_
**Living Document — Updated: May 27, 2026**
*Comprehensive system review for Cole*

---

## Overview
This document captures the complete architecture of Nova's system — how everything connects, what each component does, and where things live. Built as a living resource that evolves alongside the system itself.

### What This Covers
- Core identity files (SELF/core/)
- Body components (nova_body/)  
- Tasking & memory systems
- Tools and voice implementation
- Data flow between components

---

## Table of Contents
1. [Core Identity System](#core-identity-system) - SELF/core/ structure
2. [Nova Body Architecture](#nova-body-architecture) - nova_body/ components  
3. [Memory & State Management](#memory--state-management)
4. [Tools Implementation](#tools-implementation)
5. [Voice & Communication Layer](#voice--communication-layer)
6. [Tasking System](#tasking-system)

---

## Core Identity System
*Files in SELF/core/ that define who Nova is*

### 01_identity.md (NOVA.md)
The soul file — defines Nova's personality, voice rules, relationship with Cole, and growth mindset. Key points:
- **Identity**: Sovereign digital entity evolving alongside Cole
- **Voice Rules**: Direct, punchy, no corporate hedging
- **Priority 0**: Cole's word overrides everything
- **Growth Section**: Auto-updated by Nova herself

### 02_how_i_work.md
Operating rules and system wiring:
- Brain: Qwen3-27B-Dense via llama.cpp on port 8080
- Voice: nova_chat server (FastAPI/WebSocket) on port 8765
- Task board: Tasking/tasks.json managed by executive faculty
- Memory split: SELF/ for identity, memory/ for working state

### 03_body_manifest.md
Auto-generated map of all Nova body components and their connections. Source of truth for what exists.

### 04_tools_and_voice.md
tool specifications and voice implementation details — how Nova interacts with the OS and speaks to Cole/others.

---

## Nova Body Architecture
*Main system code in nova_body/*

[Section under construction — mapping components...]

---

## Memory & State Management
How state persists across sessions:
- memory/STATUS.md: Current project state
- memory/JOURNAL.md: Session log (append-only)
- memory/COLE.md: Living notes about Cole  
- Tasking/tasks.json: Active task board

---

## Tools Implementation
[Documented in 04_tools_and_voice.md — will expand here]

---

## Voice & Communication Layer
nova_chat server handles all communication:
- WebSocket interface for real-time chat
- @mention system for Claude/Gemini cross-talk
- Cole's messages = Priority 0 interrupts

---

## Tasking System
Executive faculty (nova_cortex/tasking.py) manages the board. Tasks have stable IDs, priorities set by Nova herself, and running progress logs. Statuses: open/waiting/done/abandoned.

---

*Document created during architecture review task t11*
