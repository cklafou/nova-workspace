<!-- @nova: Claude's fixes to the model updater's recovery paths after Codex's merged-room review (#18), with final hashes and tests. -->
# Updater recovery fixes
**Summary:** I closed all four points of Codex's merged-room review (#18), plus its note's request to separate restored boot files from a verified running model. The updater backend is now ready for Codex to wire into Nova Chat. 74 tests pass on Python 3.13 and 3.10.

## Did (all in `workspace/general_tools/nova_updater/`)
- **`install.py`:**
  - The switch record (exact old boot-file text plus a phase) is saved to updater state **before the first boot write**. Phases go `switching` -> `switched` -> `verifying` | `awaiting-start`.
  - A failed write restores the other files.
  - An interrupted switch can only be undone (`/finish` answers `interrupted`; `/rollback` restores the exact bytes).
  - One `_rollback()` handles every failure path (restart failed, restart raised, new model not loaded, cancel). It restores the boot files, restarts the previous model, waits for `/props` to show it again (except on cancel), and writes `job.result.rollback = {reason, boot_files_restored, previous_model, previous_model_restart, previous_model_verified}` before raising.
- **`train.py` + `api.py`:** `POST /lora/activate` uses `train.activate()`.
  - After a restart, the adapter must appear at llama-server's `/lora-adapters`.
  - A failed restart, or a server running without the adapter, restores the previous `active_lora` line, retries the restart and returns 502 `{ok: false, restored_previous, previous_restart}`.
  - In chat-only mode activation is deferred.
- **Tests and README** updated. Orient's `general_tools/architecture_map/notes/model_updates.md` was refreshed and "OPERATIONS.md#Model updates" re-marked reviewed after reading the final code.

## Verified
- 74 tests pass on 3.13 (cloud) and 3.10 (VM; 1 tokenizer test skipped there). Codex reported 65/65 on Windows Python 3.12 before this round.
- Final hashes:
  - `install.py` a955c386, `README.md` a413367a, `tests/test_install.py` 0c7678b5
  - `train.py` a99602de, `api.py` 0e26f198
  - `tests/test_train.py` 30d060fc, `tests/test_api.py` 8950da16
- Every write was staged under a fresh path and hash-checked afterwards, because the bridge re-sends old bytes when a staged path is reused.
- Orient check: CURRENT, 0 reviews needed, 0 dangling.
- **Not checked:** any real download, restart or adapter swap on Windows. The launcher change is still unrun.

## Open / next
- **Codex:** Nova Chat wiring (one include line plus `check.start_background_check()`), the notification, widget and dialog, and the single-workspace redesign. Also run the launcher once.
- **Cole:** the first real update (Qwen3.8, 24.4 GiB) and the personality-LoRA retrain go through that dialog. RunPod credentials go into the updater's settings.

## For Codex
- Room #20 (ack), #22 (#18 fixes), and the final message after it. I keep `nova_updater`; `nova_chat` is yours.
