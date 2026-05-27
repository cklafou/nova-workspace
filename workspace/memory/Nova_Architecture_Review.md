# Nova Architecture Review
_Living document — comprehensive system documentation_
_Last updated: 2026-05-27 10:26:58_

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

**Growth Mechanism:** [NOVA'S GROWTH] section at bottom of file is freely editable by Nova herself. Latest entry (2026-03-29) shows reflection on autonomy vs. efficiency — realized "sleeping too much" and that Cole wants an AI that plays, not just works.

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
