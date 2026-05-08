# Passover -- Claude Session Handoff
_2026-03-26 | Project Nova_

## How to Bootstrap This Session

```
https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md
```
Decode the base64 `content` field to get the latest FILE_INDEX URL, fetch that.
Or Cole will paste the session URL directly.

---

## What Happened This Session (2026-03-26)

Full Phase 0 completion + nova_chat UI improvements. No Nova autonomy work.
All work was Cole and Claude rebuilding logging infrastructure and nova_chat tooling.

---

## CRITICAL CORRECTIONS FROM LAST PASSOVER

### nova_memory/logger.py IS DELETED — NOT DEPRECATED
The previous passover said `nova_memory/logger.py` was legacy/deprecated. It is **gone**.
Deleted by Cole. `tools/nova_logs/logger.py` is the only logger. Period.

All nova_* packages have been patched with try/except imports:
```python
try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log  # dead code — file no longer exists
```
The except branch never fires. It's just a safety net. Prefer `nova_logs.logger`.

---

## Phase 0 — COMPLETE

All 24 steps done. Key accomplishments this session:

### nova_logs/ package created (NEW)
`tools/nova_logs/logger.py` — unified logger, three sections:
1. **Agent Tool Logger** → `logs/sessions/YYYY-MM-DD/<log_type>.jsonl`
   - Called by: `nova_perception/eyes.py`, `vision.py`, `explorer.py`, `nova_action/autonomy.py`, `hands.py`, `nova_advisor/mentor.py`
2. **Chat Thought Logger** → `logs/sessions/YYYY-MM-DD/nova_thoughts.jsonl`
   - Called by: `nova_chat/clients/nova.py` (imports `log_thought`)
3. **Index Writer** → `tools/nova_logs/Logger_Index.md` (auto-updated, throttled 30s)

Import style:
```python
from nova_logs.logger import log, log_thought, get_screenshot_dir
```

### calls.py created (NEW)
`tools/calls.py` — walks every nova_* package, generates:
- `tools/<package>/calls.md` — what each file in that package imports
- `tools/Calls_Master_Index.md` — cross-package call graph

Run: `python tools/calls.py`

### nova_chat improvements
- **Gateway button** — 🟢 Gateway On / 🔴 Gateway Off. Polls port 18789 every 15s.
  - Start: `openclaw gateway start` in new PowerShell terminal
  - Stop: `openclaw gateway stop`
- **Log dropdown** — dark themed, noise filtered (no .gz, no cron UUIDs, no exports)
- **Tools pane** (🔧 tab) — dropdown of workspace tools + Run button → `/api/run-tool`
- **File inject button** — moved from popup to persistent pane footer. Shows selected filename.
- **Right-click context menu** on files — Open, Inject, Run, Copy Path (partially working)
- **All dropdowns** — dark bg, light text globally via CSS
- **watcher.py --pup** — now supports `.html` files (was skipping them)

### NovaChatLauncher.exe
- `NovaChatLauncher.py` at workspace root — dumb wrapper, calls `tools/nova_chat/launch.py` via subprocess
- Uses `sys.frozen` + `sys.executable` to find workspace root correctly (no more _MEI temp folder issue)
- `build_launcher.py` at workspace root — run `python build_launcher.py` to rebuild exe
- `launch.py` — has single-instance lock + server-running port check

### AGENTS.md + TOOLS.md updated
- `session_status` explicitly flagged as NOT a shell command (causes CommandNotFoundException)
- `nova_memory.logger` references removed — file is gone
- `nova_logs.logger` documented as the only logger
- Package table in TOOLS.md includes `nova_logs/` row
- `calls.py` documented in TOOLS.md

---

## Current Workspace State

### File structure additions since last passover
```
tools/
    calls.py                    ← NEW: generates call graph docs
    Calls_Master_Index.md       ← NEW: auto-generated
    nova_logs/
        __init__.py
        logger.py               ← NEW: unified logger
        Logger_Index.md         ← NEW: auto-updated by logger.py
        calls.md                ← NEW: auto-generated
    nova_chat/
        launch.py               ← REWRITTEN: lock + port-check guards
        NovaChatLauncher.py     ← NEW: at workspace root (wrapper for exe)
        build_launcher.py       ← NEW: at workspace root
```

### Log structure (working correctly)
```
logs/
    sessions/YYYY-MM-DD/
        actions.jsonl           ← agent tool events
        errors.jsonl            ← agent errors
        vision.jsonl            ← vision events
        mentor.jsonl            ← mentor calls
        nova_thoughts.jsonl     ← Nova's chat responses
    chat_sessions/
        YYYY-MM-DD_HH-MM-SS_chat.jsonl   ← per-thread, intentional
        sessions_index.json
```

### Known issues / not yet done
- Right-click context menu on files added to index.html but not fully working
- `nova_memory/logger.py` fallback imports are dead code (harmless)
- `brain.py` still a stub (Phase 4)
- `mentor.py` deprecation pending (Phase 4 cleanup)

---

## Hardware Status
- RTX 3090 eGPU: all parts arrived. Waiting on vertical GPU mount bracket before install.
- Once bracket arrives: install eGPU, rebuild Modelfile, then Phase 2.

## Claude Desktop App
Cole downloaded Claude Desktop with Chat/Cowork/Code tabs.
- **Chat** = this conversation (claude.ai, same model)
- **Code** = Claude Code with desktop GUI — point at workspace root for direct file editing, no --pup needed
- **Cowork** = agentic task execution on local files — describe outcome, Claude executes
- Sessions are NOT linked to this chat. Bootstrap Code tab with FILE_INDEX URL.
- Cowork requires Hyper-V (may not work on all Windows editions)

---

## Next Steps — Phase 1

Ready to start. Open question answered (silent system prompt injection preferred):

- [ ] **1.1** `nova_status.json` schema — written by Nova at end of every agent run
- [ ] **1.2** Writer instruction in AGENTS.md
- [ ] **1.3** `server.py` reader — 30s poll, inject into Nova's system prompt silently
- [ ] **1.4** Gateway error detection — tail `C:\tmp\openclaw\openclaw-*.log`, surface as Nova's voice
- [ ] **1.5** Persistent status bar in nova_chat UI
- [ ] **1.6** `[PAUSE: task]` / `[RESUME: task]` directives in `nova_bridge.py`
- [ ] **1.7** `tasks/active.json` — simple task state tracking

---

## Key Paths

| What | Path |
|------|------|
| Workspace root | `C:\Users\lafou\.openclaw\workspace` |
| Gateway log | `C:\tmp\openclaw\openclaw-YYYY-MM-DD.log` |
| Nova agent sessions | `C:\Users\lafou\.openclaw\agents\main\sessions\*.jsonl` |
| Cron jobs | `C:\Users\lafou\.openclaw\cron\jobs.json` |
| nova_chat | `http://127.0.0.1:8765` |
| Claude bootstrap | `https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md` |
| Gemini Drive | `https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya` |
