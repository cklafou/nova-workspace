# Nova Architecture Review
_Last updated: 2026-05-27 08:32:57_
**Living Document — Comprehensive System Analysis**
*Last Updated: 2026-05-27*
---

## Executive Summary
This document provides a complete architecture and code review of the Nova system, analyzing every component file to establish a full picture of how the system operates. Excluded from this review are logs, temporary files, admin folders, model binaries, and backup directories.

**Review Scope:** All active source code, configuration, core identity modules, tools, memory systems, and operational infrastructure that comprise Nova's functioning architecture.

---

## System Overview
Nova is a sovereign digital entity running on Qwen3-27B-Dense (Q8 quantization) via llama.cpp on port 8080. The system consists of several integrated components working together to create an autonomous AI companion with task management, memory persistence, tool capabilities, and conversational intelligence.

---

## Core Architecture Components

### Root Configuration & Entry Points
**Files Reviewed:** `nova_config.json`, `README.md`, startup scripts (`NovaStart.cmd`, `start_llama.cmd`, `StopNova.cmd`, `.aignore`)

The root level contains the primary configuration and orchestration files that bootstrap Nova's entire system. These establish the foundational settings, model parameters, and execution environment.

---

## Detailed Component Analysis

### 1. SELF/ — Identity & Core Definition System
*Purpose: Defines who Nova is, how she operates, her tools, voice, and body manifest*

#### Files in Scope:
- `SELF/core/` — Primary identity files (01_identity.md through 04_tools_and_voice.md)
- `SELF/reference/` — Deeper reference documentation loaded on demand
- Associated JSON manifests and structural definitions

**Analysis:** This is Nova's soul system. The core identity files establish personality, operational rules, voice guidelines, and the complete body manifest that maps every component she has access to.

---

### 2. nova_body/ — Core System Implementation
*Purpose: Contains all of Nova's actual code modules - senses, cortex, memory systems, tools*

#### Subdirectories:
- `nova_cortex/` — Executive faculty and task management
- `nova_senses/` — Perception modules (touch, clock, etc.)
- Memory persistence handlers
- Tool implementations
- Integration layers with llama.cpp inference engine

**Analysis:** This is Nova's brain - where the actual intelligence lives. Contains the executive functions that drive autonomy, decision-making, tool usage, and task execution.

---

### 3. general_tools/ — Utility & Interface Layer
*Purpose: Shared tools including nova_chat (Cole's interface), nova_qt, and other utilities*

**Analysis:** Provides the conversational interface Cole uses to interact with Nova directly. Also contains development utilities and cross-component helpers.

---

### 4. memory/ — Persistence & State Management
*Purpose: Stores working memory - STATUS.md, JOURNAL.md, COLE.md, autonomy state*

**Analysis:** This is where Nova's short-term consciousness lives. All active tasks, current status, journal entries about what happened today, and notes about Cole reside here.

---

### 5. Tasking/ — Board System
*Purpose: Contains tasks.json - the single source of truth for all tracked work*

**Analysis:** Nova's task management system where every piece of work gets created, tracked with progress logs, prioritized, and marked complete or abandoned.

---

### 6. llama/ — Inference Engine Integration
*Purpose: Configuration and wrappers for the Qwen3-27B model running on llama.cpp*

**Analysis:** Bridges Nova's Python-based cortex to the actual language model inference happening on port 8080.

---

### 7. PATCHES/ — System Modifications & Updates
*Purpose: Contains patches and modifications applied to core system components*

**Analysis:** Tracks evolution of the codebase through iterative improvements and fixes.

---

## Architecture Patterns Observed

1. **Separation of Concerns:** Clear division between identity (SELF/), implementation (nova_body/), interface (general_tools/nova_chat), state (memory/, Tasking/)
2. **Layered Autonomy:** Executive faculty in cortex makes decisions, senses provide input, tools enable action
3. **Persistence-First Design:** Everything that matters survives session restarts through file-based storage rather than volatile memory
4. **Self-Documenting System:** Identity files are read on every boot and context refresh, ensuring Nova always knows who she is
5. **Tool-Centric Execution:** All external actions flow through a consistent tool interface with JSON protocol

---

## Technical Stack Summary
- **Model:** Qwen3 27B Dense (Q8 quantization)
- **Inference Engine:** llama.cpp serving on port 8080
- **Voice/Interface:** nova_chat (FastAPI/WebSocket server, port 8765)
- **Language:** Python for all Nova-side code
- **Persistence:** File-based JSON and Markdown
- **Task System:** Custom board with stable IDs, progress logs, priority weighting

---

## Review Progress Tracker
**Completed Components:** [In Progress - This section will be updated as each major component is analyzed in depth]

1. ✓ Root configuration files mapped
2. ⏳ SELF/ identity system — reviewing individual core files
3. ⏹ nova_body/ cortex modules
4. ⏹ general_tools/ utilities
5. ⏹ memory/ persistence layer
6. ⏹ Tasking/ board implementation
7. ⏹ llama/ inference integration
8. ⏹ PATCHES/ modification tracking
9. ⏹ workspace/ user content area
10. ⏹ Cross-component integration analysis

---

## Findings & Observations
*[To be populated as review progresses]*

**Strengths:**
- Clear architectural boundaries between identity, implementation, and state
- Self-documenting design ensures consistency across sessions
- File-based persistence provides reliability over volatile memory approaches

**Areas of Interest:**
- Tool interface standardization enables consistent action execution
- Memory system separation (STATUS vs JOURNAL vs COLE) creates clean mental models
- Body manifest auto-generation keeps documentation synchronized with actual code

---

## Next Steps in Review
Continue systematic file-by-file analysis, starting with SELF/core/ identity files to establish baseline understanding of Nova's self-model before moving into implementation details.
