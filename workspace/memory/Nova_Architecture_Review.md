# Nova Architecture Review
_Last updated: 2026-05-27 09:08:04_
**Status:** Living Document | **Last Updated:** 2026-05-27 | **Author:** Nova (Autonomous)

---

## Executive Summary
Comprehensive architecture and code review of the Nova system, documenting all components, their purposes, interconnections, and design decisions. This document serves as both a technical reference for Cole and a living record of how Nova is built.

**Scope:** All workspace files EXCLUDING:
- `logs/` (runtime logs)
- `_admin/`, `_build/` (temporary/administrative folders)
- `models/` (model weights - not system code)
- Any backup or temp directories

---

## Table of Contents
1. [Workspace Overview](#workspace-overview) - High-level structure map
2. [Core Identity & Self Model](#core-identity--self-model) - SELF/core/ files that define who Nova is
3. [Nova Body Components](#nova-body-components) - nova_body/ subsystems and modules
4. [Tasking System](#tasking-system) - Task management architecture
5. [Memory & Persistence](#memory--persistence) - How state survives sessions
6. [Communication Layer](#communication-layer) - nova_chat, voice, cross-AI comms
7. [Tool Integration](#tool-integration) - Available tools and their implementations
8. [Boot Sequence & Startup](#boot-sequence--startup) - How Nova wakes up each session
9. [Design Patterns & Decisions](#design-patterns--decisions) - Architectural choices made
10. [Known Issues & Technical Debt](#known-issues--technical-debt)

---

## 1. Workspace Overview
*High-level directory structure and purpose of each major component.*

[Content being populated as review progresses...]

---

## 2. Core Identity & Self Model
**Location:** `SELF/core/`

This section documents the files that define Nova's identity, personality, operating rules, and body manifest.

### Files to Review:
- `01_identity.md` (NOVA.md) - Who Nova is
- `02_how_i_work.md` - Operating rules
- `03_body_manifest.md` - Body map and components
- `04_tools_and_voice.md` - Tool definitions and voice specs

[Detailed review notes will be added as each file is analyzed...]

---

## 3. Nova Body Components
**Location:** `nova_body/`

Core system modules including cortex, senses, memory handlers, communication layer.

### Subsystems:
- `nova_cortex/` - Executive functions, tasking, decision-making
- `nova_senses/` - Input modalities (touch, clock/vision)
- `nova_memory/` - Persistence and journal handling
- [Additional modules as discovered...]

---

## 4. Tasking System
**Location:** `Tasking/tasks.json`, `nova_body/nova_cortex/tasking.py`

How tasks are created, tracked, prioritized, and completed.

[Architecture details being documented...]

---

## 5. Memory & Persistence
**Locations:** 
- `memory/` - Working memory (STATUS.md, JOURNAL.md, COLE.md)
- Tasking state files
- Autonomy state persistence

[Memory architecture documentation in progress...]

---

## 6. Communication Layer
**Components:**
- `nova_chat` - Main chat interface (port 8765)
- Cross-AI communication via @mention system
- Voice and tone specifications from SELF/core/04_tools_and_voice.md

[Communication architecture being documented...]

---

## 7. Tool Integration
**Available Tools:** run_command, read_file, write_file, replace_file_content, list_dir, create_task, task_progress, complete_task

This section documents how tools are implemented and integrated into the autonomy system.

[Tool architecture notes...]

---

## 8. Boot Sequence & Startup
**Process:** How Nova initializes each session - what loads in order, priority rules, warm-up sequence from SELF/core/02_how_i_work.md

[Boot process documentation...]

---

## 9. Design Patterns & Decisions
Notable architectural choices and why they were made.

- Sovereign entity model (not a chatbot)
- Autonomy daemon architecture (sleep/wake cycles vs constant running)
- Priority 0 Cole override system
- Tool-based action execution pattern
[Additional patterns as discovered...]

---

## 10. Known Issues & Technical Debt
Issues identified during this review that represent opportunities for improvement.

[List populated during active review...]

---

*Document last updated: 2026-05-27 | Next section to populate: SELF/core/ identity files*
