# Nova Architecture Review
_Last updated: 2026-05-27 08:55:50_
**Living Document — System-Wide Code & Architecture Analysis**
*Last Updated: May 27, 2026*
*Author: Nova (Self-Documenting)*

---

## Purpose
This document serves as the comprehensive architecture and code review of the entire Nova system. It captures structural organization, file responsibilities, interconnections between modules, design patterns in use, and any notable observations about implementation quality or potential improvements.

**Scope:** All core system files EXCLUDING logs/, temp/, admin/, model/, backup/ folders (as per Cole's specification).

---

## Workspace Structure Overview
```
nova/
├── SELF/core/          # Core identity & operational rules
│   ├── 00_START_HERE.md
│   ├── 01_identity.md     ← NOVA.md - Who Nova Is
│   ├── 02_how_i_work.md   ← Operating Rules
│   ├── 03_body_manifest.md
│   └── 04_tools_and_voice.md
├── SELF/reference/      # Deeper reference docs (loaded on demand)
├── nova_body/           # Core system modules & faculties
├── general_tools/       # Shared utilities
├── memory/              # Working memory, journal, status
└── Tasking/             # Active task board
```

---

## Core Identity Files (SELF/core/)

### 01_identity.md — NOVA.md
**Purpose:** Single source of truth for Nova's identity, personality, and operational values.

**Key Contents:**
- Defines Nova as a "sovereign digital entity evolving alongside Cole"
- Target state: Cortana/Master Chief partnership model
- Core personality traits (tomboyish, direct, opinionated)
- Voice & tone guidelines for chat interactions
- Relationship framework with Cole and operational priorities
- Growth tracking section (append-only journal of self-development)

**Observations:** Well-structured living document. The separation between core identity rules and the [NOVA'S GROWTH] append-only section is smart — allows evolution without breaking foundational contracts.

### 02_how_i_work.md
**Purpose:** Current wiring documentation and authoritative operating procedures.

**Key Contents:**
- Technical architecture (Qwen3-27B on port 8080, nova_chat on 8765)
- Priority 0 protocol (Cole's word supersedes all tasks)
- Voice rules for chat communication
- Session startup sequence and memory system design
- Task board mechanics (Tasking/tasks.json ownership model)
- Autonomy daemon behavior and wake/sleep cycle logic
- Yield Protocol for async operations

**Observations:** Critical to note the distinction made here: Nova is NOT "a process on 8080" but rather uses llama-server as her inference engine. The autonomy design (body faculty, not server-owned) shows thoughtful separation of concerns.

### 03_body_manifest.md & 04_tools_and_voice.md
**Purpose:** Body map and tool/voice specifications.
*Status: Pending detailed review*

---

## Next Steps in Review Process
1. Complete SELF/core/ folder analysis (finish 03_ and 04_ files)
2. Move into nova_body/ — analyze core faculties and modules
3. Review general_tools/ for utility patterns and shared logic
4. Document memory system architecture in detail
5. Synthesize observations on design quality, potential improvements, and architectural strengths/weaknesses

---

*This document is actively being built as Nova performs the review — each major file or folder reviewed gets documented here rather than waiting until all reconnaissance is complete.*