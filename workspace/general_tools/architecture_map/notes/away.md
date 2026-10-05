<!-- @nova: Explain the remote reading copy and its exclusions. -->
_Last updated: 2026-10-03 11:23:52_
---
doc: OPERATIONS.md
order: 40
---
<!-- @nova: Orient note: how Cole reads and writes Nova from a PC that only reaches Google Drive, published in OPERATIONS.md. -->
## Working away from this PC

Google Drive for Desktop must sync `Project_Nova/Nova_Drive/` only, never the repository: it cannot
skip subfolders, so syncing the repository uploaded `.git`, large model weights and token files, and
its temp folder stopped autosave (lesson 7 above).

- `Nova_Drive/read/` holds the text files of the last commit under `workspace/`, plus `AGENTS.md`:
  code, docs, Orient, configs and notes. Git already leaves out secrets, weights and logs; the copy
  also skips binaries, `node_modules`, `.venv`, `venv`, files over 5 MB and
  `workspace/Temp/collaboration` (even if a dependency or transport artifact were accidentally tracked). The private Collaboration room is not
  part of this remote reading copy. The watcher refreshes it after every
  autosave (`general_tools/nova_sync/drive_copy.py`). It is a copy, so edits made there are
  overwritten.
- `Nova_Drive/inbox/` is where Cole puts anything he writes away from this PC. Nothing modifies or
  deletes it automatically; agents read it when he mentions it.

`Nova_Drive/` is ignored by git and by the watcher, and Orient does not index it.
