<!-- @nova: Claude's handoff for 2026-10-02 and 10-03: Orient upkeep, autosave and git repair, Nova_Drive, Astra's trust. -->
# Orient and sync handoff (2026-10-02 to 10-03)
**Summary:** Orient now refreshes inside every commit and flags explanations whose code changed.
Autosave was dead for 35 hours (Google Drive's temp folder inside the repo) and works again.
Nova_Drive gives Cole a copy he can read from a Drive-only PC, and GPT Astra is now trusted like
Claude. Two things wait on Cole: pointing Drive for Desktop at Nova_Drive, and running FIX_GIT.cmd.

## Did
**Orient** (`workspace/general_tools/architecture_map/`)
- `orient.py`: per-section review tracking (`reviews.json`, ⚠ lines, `--mark-reviewed`,
  `--check [--strict]`); explanations live in `notes/*.md`; link check and an "Orient health"
  section; NUL-damage report; INDEX descriptions come from `@nova:` purpose lines (rule: OPERATIONS
  "File conventions"), with a "Files without a purpose line" list; review digests ignore line
  endings and the watcher's `Last updated` stamps; a long-running process (Nova Chat, the watcher)
  whose loaded orient.py is older than the file on disk refuses to publish; the README links the
  newest notes in this folder.
- Text I changed in orient.py itself: README sentences on file descriptions, the restart caveat and
  the AI-notes block, and the "Files and recovery" backup-branch sentence. Your 10-02 explanations
  are otherwise as you left them.
- `.git/hooks/pre-commit` (source: `hooks/pre-commit`): regenerates Orient inside every commit,
  fail-open, skippable with `NOVA_SKIP_ORIENT=1`.
- Repo-root `AGENTS.md`: read Orient and these notes first, purpose lines, atomic writes,
  `--mark-reviewed`, the inbox, leave a note.

**Git and autosave**
- Cause: Google Drive for Desktop syncs Project_Nova and keeps `.tmp.driveupload/` (~120k temp
  files) at the repo root, where the watcher runs `git add .`. 75,450 of them were committed on
  10-01, then every add failed until 2026-10-02 23:53 KST.
- Fixed: `.gitignore` (+ `.tmp.driveupload/`, `.tmp.drivedownload/`, `/Nova_Drive/`), watcher
  `EXCLUDE_DIRS` (same folders), and `.git/hooks/pre-push` (source:
  `general_tools/nova_sync/hooks/pre-push`), which refuses any push holding a file over 100 MB before
  uploading anything.
- `workspace/_admin/FIX_GIT.cmd` v2, not run yet: folds the unpushed autosaves into one commit
  without the 1 GB VM tar and the Drive temp files, keeps the originals on local branch
  `backup/before-fix-git`, then pushes.

**Nova_Drive**: `general_tools/nova_sync/drive_copy.py` keeps `Project_Nova/Nova_Drive/read/` a text
copy of the last commit (no binaries, node_modules or files over 5 MB); the watcher refreshes it
after every autosave. `Nova_Drive/inbox/` is for notes Cole writes away from this PC.

**Astra**: `nova_body/nova_cortex/principals.py` makes "Astra" TRUSTED (any speaker name containing
the word "astra", e.g. "GPT Astra"); the trusted-speaker line now says "is Claude" only for Claude.

**Pointers and purpose lines**: fixed stale `Orient/SECURITY.md` and `Orient/GOTCHAS.md` references
in `principals.py`, `audit_scripts.py` and `nova_sync/drive.py`; added `@nova:` lines to about 25
files that had none.

## Why
Cole's criteria for Orient: one source of truth, enough context for people and AIs, and it keeps
itself current. Autosave is what makes the last one true, and git is the only record of retired
files now that `_admin/Trash/` is emptied.

## Verified
- `test_orient.py`: 14/14 on the exact Windows bytes.
- First autosave after the fix: commit `032c4650e4` (638 files) with fresh Orient inside it; the
  pre-push hook refused the doomed push in under 40 s; `origin/master` unchanged (`a64b1dad89`).
- `drive_copy.export` run once from here: 702 files, 12 MiB. `principals.role_of` checked for Cole,
  Cowork Claude, GPT Astra and unknown names, also against the real `nova_users.json` (read-only).
- NOT verified: the watcher's own `run_drive_copy()` on Windows (live since the 08:50 KST restart;
  look for `[drive-copy]` in the hub console), and FIX_GIT v2 (needs Cole).

## Open / next
- Cole: switch Drive for Desktop from `Project_Nova` to `Project_Nova\Nova_Drive`; run FIX_GIT.cmd v2
  with Nova quit and Codex paused.
- After the switch, `.tmp.driveupload/` and `.tmp.drivedownload/` at the repo root (GBs) can go.
- `nova_sync/drive.py` (the Gemini Drive mirror) has failed silently since 2026-06-02.

## For Codex
- Please leave a note on the modernization: what changed, where, and how you verified it. Cole will
  have me review it when you're done.
- `general_tools/nova_chat/static/control.css` and `nova_body/nova_voice/tool_router.py` still need
  `@nova:` purpose lines; I left them alone because you're working in them.
- Write into the repo with a temp file + rename, never an in-place copy. On 10-02 an in-place `cp`
  raced the watcher's header stamp and zeroed 4 KB of `orient.py`.
