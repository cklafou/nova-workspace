<!-- @nova: Claude's folder cleanup (the second Nova_Created) and the orphaned June-July memory store it uncovered; also the pending VNC password tool. -->
# Folder cleanup and an orphaned memory store
**Summary:** Cole asked why there were two `Nova_Created` folders. The workspace-level one was an empty shell
left behind when Nova's files moved into `nova_body/Nova_Created` on 2026-09-30. I moved it and other
leftovers to the Trash and deleted nothing. That surfaced a real problem: 1,092 of Nova's memories from
2026-05-31 to 2026-08-03 sit in `nova_body/Nova_Created/nova_memory_db`, outside her live memory store. They
are left in place for Cole to decide.

## Did
- Moved 57 items to `_admin/Trash/2026-10-04_FolderCleanup/`. `manifest.json` records each from/to path and
  sha256; `WHY.md` explains the move.
  - The empty `workspace/Nova_Created` tree (0 files).
  - 3 unreferenced backups from 2026-09-02 in `nova_body/nova_computer` (`*.opus_bak`, `*.pluck_bak`).
  - 3 one-off July scratch scripts in `nova_body/Nova_Created` (`_tmp_*.py`, `check_reach.py`).
  - 50 empty date folders in `nova_body/logs/screenshots`.
- `_admin/nightwatch.py` counted pictures in the old empty folder, so it always reported 0. It now counts
  `nova_body/Nova_Created/art` (31 pictures).
- Not touched: `Temp/`, `_admin/Training_stuff`, `_build/NovaController` (the controller exe in use),
  `_admin/Temp` (restart scratch by design), Orient, updater, UI. Room #43 told Codex the scope.

## Found (counts only; contents not read)
- Orphaned store `nova_body/Nova_Created/nova_memory_db`:
  - `nova_text`: 1,092 rows. By month: June 375, July 590, August 122. By category: general 519, personal 318,
    technical 161, project 85.
  - `nova_visual`: 2 rows.
- Live store `nova_body/nova_memory_db`: 134 text rows (March 95, September 20, October 19). It shares no
  `content_hash` with the orphaned store, so she cannot recall June-July.
- Both stores use the same vector sizes (text 384, visual 512), so appending the rows is feasible: back up
  the live store first, then append and keep the vectors. It is her state, so this waits for Cole's
  decision. Nothing records memories between 08-03 and 09-30.
- `_admin/Trash` is tracked by git and mirrored to Drive. Only non-secret items belong there.

## Open / next
- Cole: decide whether to merge the orphaned memories.
- Cole: double-click `nova_body/nova_computer/SET_VNC_PASSWORD.cmd`. It applies the password in the private
  `desktop_secret.json`, which git and Drive skip, and proves the login. Then read
  `provision/set_vnc_password.log`.
- Still offered to Cole from his YouTube test: the computer_exec `DISPLAY=:1` fix, a Windows-reach tool
  description and per-tool Pipeline events. Also Codex's witness false-PASS finding (note 1435).
