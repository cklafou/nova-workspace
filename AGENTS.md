<!-- @nova: Standing rules for AI coding agents (Codex, Claude) working in Project Nova. -->
_Last updated: 2026-10-05 21:49:06_
# Rules for coding agents

Start by reading `workspace/Orient/README.md`, then every note in `workspace/Orient/AI Notes/` written
since your own last one (the rules are in `ReadMeBeforeNoteTaking.md` there). Orient is the single
source of truth for how Nova is built and run; if this file and Orient ever disagree, Orient wins.

1. **Purpose line.** Every file you create, or change in substance, starts with a one-line
   `@nova:` comment that says what the file is for. Orient builds the file index from it.
   Syntax per file type: `workspace/Orient/OPERATIONS.md#file-conventions`.
2. **Write atomically.** Write a temporary file in the same folder, then rename it over the
   target. The sync watcher rewrites `Last updated` lines the moment a file changes and can read a
   half-written file (lesson 8 in `workspace/Orient/OPERATIONS.md#lessons-from-incidents`).
3. **Keep Orient honest.** When you change what an Orient section describes, update its
   explanation (the `edit` path in `workspace/general_tools/architecture_map/reviews.json`), then
   run `python workspace/general_tools/architecture_map/orient.py --mark-reviewed "<DOC>#<Heading>"`.
4. **Access and ownership.** Cole grants access to all Project Nova subdirectories and related
   directories, including `workspace/models/`. Avoid broad reads of large model binaries because
   they waste context, tokens and time; use targeted listings, metadata, headers or checksums when
   relevant. This is an efficiency rule, not a permission restriction. Never commit secrets. Never
   hand-edit Nova's state (her memory, tasks or journal): she owns it.
5. **Notes from away.** Cole's notes written away from this PC arrive in `Nova_Drive/inbox/` at the
   repository root; read them when he mentions them. `Nova_Drive/read/` is a generated copy
   (`workspace/general_tools/nova_sync/drive_copy.py`): never edit it.
6. **Leave a note.** When you finish, write one in `workspace/Orient/AI Notes/`, named
   `YYYY-MM-DD_HHMM_AIName_Topic.md` (24-hour time on this PC's clock), e.g.
   `2026-10-03_1645_Claude_AutonomyUpdate.md`. Read the other AIs' notes; never edit them.
