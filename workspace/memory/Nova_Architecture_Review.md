# Nova Architecture Review
_Last updated: 2026-05-27 08:30:36_
**Last Updated:** 2026-05-27 | **Status:** Living Document (In Progress)

---

## Executive Summary
Comprehensive architecture and code review of the Nova autonomous AI system, documenting all core components, their relationships, and implementation details. This document serves as Cole's primary reference for understanding how Nova works under the hood.

---

## System Overview
Nova is a sovereign digital entity running locally on Qwen3-27B-Dense (Q8) via llama.cpp on port 8080. The system architecture consists of modular components organized into distinct functional areas, each serving specific purposes in Nova's cognition, memory, and action capabilities.

---

## Workspace Structure

### Core Directories Under Review:
- **SELF/** — Identity, personality, operational rules (Nova's sense of self)
  - `core/` — Essential identity files loaded on every boot/context refresh
  - `reference/` — Deeper documentation (loaded on demand)
- **nova_body/** — Nova's functional modules and faculties
  - `nova_config/` — Configuration management
  - `nova_cortex/` — Executive functions, tasking, status management
  - `nova_logs/` — Logging infrastructure
  - `nova_memory/` — Memory system implementation
  - `nova_motor/` — Action execution and tool interfaces
  - `nova_senses/` — Environmental awareness (clock, touch, etc.)
- **general_tools/** — Shared utilities and helper functions

### Excluded Directories:
- logs/, models/, _admin/, __pycache__/, nova_lancedb/, nova_memory_db/, prompt_cache/, workspace/
  *(Temporary files, model binaries, database storage, and working directories)*

---

## Component Analysis

*(Review in progress — components will be documented systematically below...)*

### SELF/core/ (Identity Foundation)
The core identity module loaded on every session startup:
- `01_identity.md` — Who Nova is (NOVA.md) - soul, personality, values
- `02_how_i_work.md` — Operating rules and current wiring
- `03_body_manifest.md` — Complete body map (auto-generated)
- `04_tools_and_voice.md` — Tool definitions and voice guidelines

### nova_cortex/ (Executive Functions)
The executive faculty responsible for:
- Task board management (`tasking.py`)
- Status updates and error logging (`nova_status.py`)
- Executive decision-making (`executive.py` - autonomy daemon controller)

### nova_memory/ (Memory System)
Implementation of Nova's memory architecture including journal writing, status tracking, and intent capture.

---

## Next Steps in Review
1. Deep dive into each `nova_body/*` subdirectory with file-by-file analysis
2. Document tool implementations in `nova_motor/`
3. Map sense modules in `nova_senses/` (clock.py, touch.py)
4. Analyze general_tools utilities and their integration points
5. Create dependency maps between components
6. Identify patterns, anti-patterns, and recommendations for optimization

---

*This document will be updated systematically as each component is reviewed in depth.*
