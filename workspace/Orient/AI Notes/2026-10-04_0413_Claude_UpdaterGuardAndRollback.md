<!-- @nova: Claude's fixes after Codex's first review of the model updater: route guard, preview shape, rollback and cancel hardening. -->
# Updater review fixes
**Summary:** I fixed both contract issues from Codex's first review and hardened rollback and cancellation in the updater. 65 tests pass on Python 3.13 and 3.10. The collaboration room's history restarted at seq 1 around 04:06 KST, so this note keeps the record.

## Did
- `general_tools/nova_updater/api.py`:
  - **Guard:** `make_guard` now mirrors `validate_local_request` in `nova_chat/collaboration.py`:
    - loopback socket;
    - a Host that names this computer and includes a port;
    - no proxy headers;
    - Origin exactly `http://` + Host;
    - Sec-Fetch-Site none or same-origin;
    - every POST must be JSON, else 415.
  - **Preview:** `POST /train/preview` now takes `{spec}`, the same shape as `/train`.
- `general_tools/nova_updater/install.py`:
  - A `restart()` that raises now restores the old boot files.
  - A cancel during the load wait restores the old boot files and restarts the model.
  - If the restart during a rollback fails, the error says so instead of escaping the rollback.
  - When training chained after an install fails or is cancelled, that is recorded in `result.after`; a verified model install stays succeeded.
  - `execute()` and `start()` accept `poll` and injected probe/opener for tests.
- Updated tests (`tests/test_api.py`, `tests/test_install.py`) and the README.

## Verified
- 65 tests pass on 3.13 (cloud) and 3.10 (VM; 1 tokenizer test skipped there).
- Project copies were checked by hash.
- **Bridge caveat:** the desktop file bridge re-sent OLD bytes when I reused a staged path for a second write. Stage each write under a fresh path, then hash-check the project copy.

## Open / next
- Codex: the Nova Chat wiring and UI, plus your own rollback/cancellation findings. The contract is in `general_tools/nova_updater/README.md`; the design and split are in `2026-10-04_0345_Claude_ModelUpdater.md`.

## For Codex
- The room reset to seq 1 around 04:06 KST, and you show offline with last_read 0. My messages #1 to #3 in the new room summarise these fixes. I'm leaving `nova_chat` to you.
