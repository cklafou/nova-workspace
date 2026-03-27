# Passover -- Claude Session Handoff
_2026-03-21 | Project Nova_

## How to Bootstrap This Session

Fetch the live workspace index using the permanent API link:
```
https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md
```
Decode the base64 `content` field to get the latest commit-hash FILE_INDEX URL, then fetch that.
Or Cole will paste the session URL directly -- use whichever is available.

---

## What Happened This Session (2026-03-21)

This was a major infrastructure session. No Nova autonomy work was done -- this was entirely
Cole and Claude rebuilding the tooling foundation from scratch.

### Package Restructure -- COMPLETE
All flat tools/ files migrated into Python packages:

| Package | Modules |
|---|---|
| nova_sync/ | watcher.py, drive.py, backup.py, dir_patch.py |
| nova_memory/ | logger.py, journal.py, log_reader.py, status.py, state.py |
| nova_advisor/ | mentor.py |
| nova_action/ | hands.py, autonomy.py, verify.py |
| nova_perception/ | eyes.py, explorer.py, vision.py, vision_backup.py |
| nova_core/ | rules.py, brain.py, checkin.py |

Old flat files deleted. Import style: `from nova_memory.logger import log` (new preferred).
nova_patch.py confirms all 9 hard tests pass + all soft tests pass (circular imports resolved).

### Sync Infrastructure -- COMPLETE
All sync files moved to `tools/nova_sync/`:
- `FILE_INDEX.md` -- live workspace map for Claude (was in memory/)
- `FILE_INDEX_LINK.md` -- permanent bootstrap pointer (was in memory/)
- `GEMINI_INDEX.md` -- new manifest table for Gemini with deterministic search keys
- `dir_patch.py` -- new tool: audits .py AND .md files for stale import/path references
- `watcher.py` -- updated with --push, --pup, --full, --push modes + clipboard copy

New permanent bootstrap URL (updated from old memory/ path):
```
https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md
```

### watcher.py Modes
```powershell
python tools/nova_sync/watcher.py           # continuous watch mode
python tools/nova_sync/watcher.py --push    # one-shot push, copy URL to clipboard, exit
python tools/nova_sync/watcher.py --pup     # patch staged files from workspace root, push, exit
python tools/nova_sync/watcher.py --full    # interactive dir_patch audit, then push, exit
```

### --pup Mode
Drop updated files into workspace/ root (not in subdirectories).
Run --pup. It finds the correct subdirectory target by Jaccard similarity of class/function names,
replaces the file, deletes the staged copy, pushes, copies session URL to clipboard.

### dir_patch.py
```powershell
python tools/nova_sync/dir_patch.py            # interactive y/n per file
python tools/nova_sync/dir_patch.py --report   # findings only
python tools/nova_sync/dir_patch.py --auto     # apply all fixes without prompting
```
Scans both .py and .md files. Checks: stale flat imports (nova_logger -> nova_memory.logger)
and stale Path() references (workspace/"nova_eyes.py" -> workspace/"nova_perception"/"eyes.py").
Ground truth loaded from FILE_INDEX.md -- always reflects actual repo state.

### Gemini Drive Vision -- OPERATIONAL
Files now uploaded as native Google Docs format (mimeType: application/vnd.google-apps.document).
This makes them immediately visible to Gemini's Personal Context search tool.
GEMINI_INDEX.md provides deterministic search keys for every file.
Two-message boot protocol confirmed working -- see Gemini passover for details.

### Files Updated This Session
- tools/nova_sync/watcher.py -- full rewrite, all modes, clipboard, new FILE_INDEX path
- tools/nova_sync/drive.py -- Google Docs upload format, GEMINI_INDEX manifest, SYNC_CACHE moved
- tools/nova_sync/backup.py -- SESSION_SNAPSHOT_FILES updated to nova_sync/ paths
- tools/nova_sync/dir_patch.py -- NEW: import + path auditor, .py + .md scanning
- tools/nova_sync/GEMINI_INDEX.md -- NEW: manifest table with search keys
- tools/nova_sync/FILE_INDEX.md -- moved from memory/
- tools/nova_sync/FILE_INDEX_LINK.md -- moved from memory/
- tools/nova_advisor/mentor.py -- get_project_briefing() paths fixed to package paths
- tools/nova_core/rules.py -- REQUIRED_MODULES + directives updated to package paths
- tools/nova_stress_tester.py -- imports fixed to package paths
- tools/nova_action/autonomy.py -- docstring imports fixed
- BOOTSTRAP.md -- updated with new FILE_INDEX location + new bootstrap URL
- TOOLS.md -- fully rewritten: all exec commands use package paths, Drive section updated
- AGENTS.md -- exec commands fixed (dir_patch caught and fixed nova_journal -> nova_memory.journal)
- All __init__.py files -- wildcards removed, circular imports resolved

---

## Current Blockers (Unchanged from Before This Session)
- eGPU case not yet arrived -- RTX 3090 sitting idle
- Modelfile updated but model not rebuilt -- run: ollama create nova -f Modelfile
- nova_core/rules.py imports pyautogui at module level -- harmless but worth noting

## STATUS.md Note
STATUS.md on disk is dated 2026-03-20 and still shows old flat file names in the architecture
table. It needs a full update to reflect the package structure. Cole has not updated it yet --
do not trust the module names listed in STATUS.md until it is refreshed.

## Next Steps (Where We Left Off)
1. Update STATUS.md to reflect package restructure and new sync infrastructure
2. Run: ollama create nova -f Modelfile -- rebuild model
3. Install eGPU when case arrives
4. Wire brain (Qwen3/OpenClaw) to nova_perception.eyes + nova_action.autonomy as callable tools
5. ThinkOrSwim automation -- ONLY after stack proven solid
