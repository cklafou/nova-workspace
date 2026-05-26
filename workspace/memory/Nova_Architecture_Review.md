# Nova Architecture Review
_Last updated: 2026-05-27 08:39:49_
**Living Document - Last Updated:** 2026-01-XX (in progress)
**Author:** Nova
**Purpose:** Comprehensive architecture and code review of all core Nova files, excluding logs, temp files, admin/model/backup directories.

---

## Workspace Overview
Root structure contains:
- **Core systems**: `nova_body`, `general_tools` - main operational codebase
- **Identity & Self-model**: `SELF/core`, `SELF/reference`
- **Memory layer**: `memory/STATUS.md`, `JOURNAL.md`, `COLE.md`
- **Task management**: `Tasking/tasks.json` (executive faculty)
- **Configuration**: `nova_config.json`, `.aignore`, `.gitignore`
- **Support files**: `README.md`, start scripts
- **Excluded per Cole's criteria**: `_admin/`, `models/`, `logs/`, backup files, temp directories (`__pycache__/`) 

---

## Review Progress
Starting systematic file-by-file review. Will document findings here as I work through each component.

### Completed:
- Workspace structure mapped (initial pass)

### In Progress:
- Core identity documents in `SELF/core/`
- Nova body modules and faculties
- Memory system architecture
- Task board implementation

### Pending:
- General tools library
- Configuration analysis
- Integration patterns across components

---

## Initial Observations
**Architecture Style**: Modular, component-based with clear separation of concerns. Self-documenting through `SELF/` hierarchy.

**Key Design Patterns Observed**:
1. **Priority 0 override mechanism** - Cole's word supersedes all tasks (documented in identity files)
2. **Sleep/wake autonomy model** - Not constantly running, stirred by events or time-sense
3. **Living memory system** - JOURNAL.md appended rather than overwritten, STATUS tracks current state
4. **Single-source truth philosophy** - Core documents auto-generated where possible (e.g., body manifest)
5. **Tool-based execution** - JSON tool calls for OS-level actions during autonomous mode

---

## Next Steps in Review
Will now begin deep-dive into `SELF/core/` files to document identity architecture, then move through operational modules systematically.

*Document will be updated continuously as review progresses. This is a living artifact of the process itself.*
