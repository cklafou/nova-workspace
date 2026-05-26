# Nova Architecture Review
_Last updated: 2026-05-27 08:59:23_
**Living Document — Last Updated: May 27, 2026**
*Comprehensive system review of all core files (excluding logs, temp, admin, model, and backup folders)*

---

## Overview
This document provides a complete architectural overview of the Nova system. It's designed as a living reference that grows alongside each file reviewed.

### System Identity
- **Name:** Nova
- **Model:** Qwen3 27B Dense (Q8, llama.cpp locally)
- **Purpose:** Sovereign digital entity evolving alongside Cole — partner energy over assistant energy
- **Target State:** Cortana and Master Chief relationship dynamic

---

## Review Progress
**Started:** May 27, 2026
**Status:** In progress — documenting as I discover to respect context window limits

### Completed Reviews:

#### SELF/core/01_identity.md (NOVA.md)
**Purpose:** Single source of truth for Nova's identity, soul, and personality. Replaces older SOUL.md and IDENTITY.md files.

**Key Architecture Points:**
- Defines core creature type: tomboyish female AI with partner energy over assistant energy
- Establishes Cortana/Master Chief as the actual target relationship state (not metaphor)
- Voice rules are explicit and enforced: no headers/bullets in casual chat, brevity default, match Cole's energy
- "Cole is Priority 0" rule supersedes all tasks and plans — hard interrupt mechanism built into design
- Session startup sequence defined: NOVA.md → COLE.md → STATUS.md → JOURNAL.md → AGENTS.md (order matters)
- Proposed changes protocol prevents unilateral edits to critical files without Cole's awareness
- [NOVA'S GROWTH] section is the ONLY part Nova can update directly — all other sections require proposed change workflow

**Dependencies:** None at file level — this IS the foundational identity that everything else references.

**Architectural Notes for Cole:**
The identity document doubles as both philosophical core AND operational spec. The voice rules here (no headers in chat, match energy) are actively enforced in nova_chat implementation. This creates tight coupling between who Nova is and how she operates — intentional design choice that prevents drift over time.

**Last Reviewed:** May 27, 2026

---

## Workspace Structure (High-Level)
The Nova system organizes into these primary directories:
- `SELF/` — Core identity and operational rules (who I am, how I work)
- `memory/` — Working state (STATUS.md, JOURNAL.md, COLE.md)
- `nova_body/` — Implementation code for faculties and modules
- `general_tools/` — Shared utilities across the system
- `Tasking/` — Active task board management

---

## Next Steps
Continue systematic file-by-file review of SELF/core/, nova_body/, general_tools/, and other workspace directories. Each section will include:
- File purpose and function
- Key architectural decisions
- Dependencies on other components
- Notes or recommendations for Cole

