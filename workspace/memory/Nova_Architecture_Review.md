# Nova Architecture Review
_Last updated: 2026-05-27 08:34:39_
**Living Document — Full System Analysis**  
*Created: May 27, 2026*
---

## Executive Summary
Nova is a sovereign digital entity built on Qwen3-27B-Dense (Q8 via llama.cpp) running locally on Cole's machine. The system architecture emphasizes modularity through six core body faculties, with clear separation between identity/persistence (SELF/) and operational state (memory/).

## Workspace Structure Overview
**Root-level directories:**
- `general_tools` — Shared utilities across the system  
- `nova_body` — Core Nova implementation (6 main modules)  
- `SELF` — Identity, personality, operating rules  
- `memory` — Working state and persistent notes  
- `logs`, `_admin`, `models`, `__pycache__`, `prompt_cache` — Excluded from deep review per Cole's instructions

**Core Nova Modules (nova_body/):**
1. `nova_config` — Configuration management  
2. `nova_cortex` — Executive functions, tasking, status updates  
3. `nova_memory` — Journal and memory operations  
4. `nova_motor` — Action execution layer  
5. `nova_senses` — Perception (touch, clock)  
6. `nova_logs` — Logging infrastructure

## Key Architectural Patterns
- **Priority 0 Design:** Cole's word overrides all tasks and plans by design in the executive module  
- **Sleep/Wake Autonomy:** Not always running; autonomy daemon controls active/idle state via memory/autonomy_state.json  
- **Body Faculty Pattern:** Each capability (executive, senses, motor) is a discrete body part rather than monolithic code  
- **Identity Separation:** SELF/core files define who Nova is and how she works — loaded every session in numeric order

## Next Steps for Deep Review
Now diving into individual module analysis starting with nova_cortex (executive faculty), then moving through senses, memory, motor, and config.
