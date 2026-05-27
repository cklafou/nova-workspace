# Nova Architecture Review
_Living document — comprehensive system documentation_
_Last updated: 2026-05-27 10:26:17_

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
[Content to be filled after review]

### Key Files:
- `00_START_HERE.md` — Boot order, what constitutes Nova's self-model
- `01_identity.md` (NOVA.md) — Who Nova is: personality, values, relationship with Cole
- `02_how_i_work.md` — Operating rules, voice guidelines, autonomy mechanics  
- `03_body_manifest.md` — Complete system map of all body components
- `04_tools_and_voice.md` — Tool definitions and communication protocols

### Core Identity Summary:
[To be documented]

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
