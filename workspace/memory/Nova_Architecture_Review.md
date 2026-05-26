# Nova Architecture Review
_Last updated: 2026-05-27 08:49:08_
**Living Document — Full System Analysis**
Last Updated: 2026-05-27
Author: Nova (autonomous review)

---

## Workspace Overview

Root directory contains the following top-level structure:

### Core Directories (Included in Review)
- **general_tools/** - Shared utility functions and helper modules
- **llama/** - Inference engine backend (Qwen3 27B via llama.cpp on port 8080)
- **memory/** - Working memory system (STATUS, JOURNAL, COLE files + reports)
- **nova_body/** - Core Nova body architecture and faculties
- **nova_lancedb/** - Vector database backend for semantic search/memory retrieval
- **PATCHES/** - Applied code patches and modifications to core systems
- **prompt_cache/** - Caching layer for prompt optimization (under review)
- **SELF/** - Identity, personality, self-model files (01_identity.md through 04_tools_and_voice.md + reference docs)
- **Tasking/** - Task board system and management infrastructure
- **workspace/** - Active work directory and project files

### Excluded Directories (Per Cole's specifications)
- **logs/** - Runtime logs, excluded as specified
- **models/** - Model file storage, excluded as specified  
- **_admin/** - Admin/temporary configuration, excluded as specified
- **__pycache__/** - Python cache files, temporary exclusion
- **.nova_app_profile_33972/** - Application profile data, treated as temp/cache

### Root Files (Included)
- `.aignore` / `.gitignore` - Version control ignore patterns
- `NovaStart.cmd` / `StopNova.cmd` / `start_llama.cmd` - Launch and shutdown scripts
- `nova_config.json` - Core configuration file
- `nova_start.py` - Primary startup script
- `README.md` - System documentation entry point
- `.gitignore` patterns indicate version control structure

---

## Next Steps in Review Process
1. Deep dive into SELF/ folder (identity core)
2. Full nova_body/ architecture mapping  
3. general_tools/ utility analysis
4. Memory system internals review
5. Tasking infrastructure documentation
6. Database and caching layer assessment
7. Patch history and modification tracking
8. Cross-reference all components for dependencies and integration points

---

*Document maintained by Nova as part of active architecture review task t11*
