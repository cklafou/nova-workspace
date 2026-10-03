<!-- @nova: Claude's model-updater build: what exists, how it was verified, what Codex wires next, and the exclusions done the same night. -->
# Model updater backend + exclusions
**Summary:** The model updater's backend is built and tested at `workspace/general_tools/nova_updater/`: the startup check, repository search, install with load-check rollback and trash quarantine, and LoRA training via RunPod or an exported bundle. Codex owns the Nova Chat side (notification, widget, dialog) and I've posted the contract in room #10. I did not download Qwen3.8 or start any paid training; both are one confirm away once the UI exists.

## Did
- **Exclusions (Cole: avatar files out of git).**
  - `workspace/.gitignore` now covers `nova_body/SELF/Avatar/`, `nova_body/memory/runtime_work.sqlite3*` and `general_tools/nova_updater/state/`.
  - `_admin/FIX_GIT.cmd` v3 also untracks the avatar folder and the work-queue DB. After the fold, the push should be about 50 MB.
  - `workspace/.aignore` now covers the updater state and `Temp/updater`.
- **Task workspaces:** `nova_body/nova_cortex/task_workspace.py` stages under `Temp/task-workspaces/`, and the watcher has `EXCLUDE_SUBPATHS` for it. Tests: `nova_body/tests/test_staging_location.py` and `general_tools/nova_sync/tests/test_exclusions.py`.
- **Updater:** `general_tools/nova_updater/` (29 files; the README holds the route contract):
  - `check`, `catalog` (Hugging Face, ModelScope, Ollama link-only), `current`, `gguf`, `inventory`
  - `plan`, `install`, `jobs`, `train`, `runpod`, `api`, CLI
  - `pod/`: `template_gen.py`, `train_lora.py`, `run_on_pod.sh`
- **Launcher:** `workspace/start_llama_qwen36.cmd` reads `nova_body\memory\active_model.txt` and `active_mmproj.txt`, falling back to today's paths.
  - `"none"` means no projector, or no LoRA.
  - The v2 fallback LoRA now applies only on the default Qwen 3.6 model.
- **Orient:** new note `general_tools/architecture_map/notes/model_updates.md`, published as OPERATIONS "Model updates". I also updated "Run and stop" and "Configuration and evidence" (in `orient.py`). All three are marked reviewed.

## Why
- Cole superseded "update to Qwen 3.8 by hand on RunPod" with "build a lasting update method with Codex".
- A LoRA trained for Qwen3.6 loads onto Qwen3.8 without error, because the architecture is identical, and then behaves wrongly. So a switch disables the personality and KoELS adapters until new ones are trained, and a rollback restores them.

## Verified
- **Tests:** 58 updater tests pass on Python 3.13 (cloud) and 3.10 (VM; one tokenizer test skipped there). Orient: 42 tests OK, and the check reports CURRENT. The exclusion and staging tests pass.
- **Live Hugging Face:**
  - The check finds `Qwen/Qwen3.8-27B` (2026-08-05, Apache-2.0, 27.78B, dense) for the running `Qwen3.6-27B`.
  - The plan picks `unsloth/Qwen3.8-27B-GGUF` UD-Q6_K_XL + `mmproj-F16` (24.43 GiB) with LFS sha256 hashes. Both configs show the same architecture and shape (`Qwen3_5ForConditionalGeneration`, 64 layers, 5120 hidden).
  - ModelScope search and file listing work; Ollama search works.
- **Template patch:**
  - `pod/template_gen.py` patches by structure, then proves GATE A (12 renders identical) and GATE B (the mask) on the real Qwen3.6-27B and Qwen3.8-27B tokenizers.
  - On `unsloth/Qwen3.6-27B` it reproduces v6's `qwen_template_gen.jinja` byte-for-byte.
  - v7's fixed patch would refuse Qwen3.8: its template changed (reasoning-effort text, a different `preserve_thinking` default).
- **Not checked:**
  - Any real download or install on Windows.
  - Running the updated launcher on Windows (I reviewed the diff only).
  - A real RunPod run (fakes only).
  - ModelScope downloads.
  - Updating llama.cpp itself is not automated; the load check would roll back an unsupported model.

## Open / next
- **Codex:** wire it (one include line plus `check.start_background_check()`), then build the notification, widget and dialog. Smoke-test the launcher.
- **Cole:**
  - Put the RunPod key, SSH key path and pod id in the updater's credentials once the UI exists.
  - Run FIX_GIT (Nova quit, Codex paused).
- **Probable v7 bug:** `_admin/Training_stuff/v7/run_on_pod_v7.sh` loops over `checkpoint-*` in glob order. With 399 rows (50 steps per epoch), `checkpoint-100` sorts before `checkpoint-50`, so `nova_core_v7_epoch1.gguf` would be the epoch-2 adapter and vice versa. v6 was unaffected: 46 and 92 have the same digit count. If v7 was trained, re-label or check before trusting any epoch comparison. The new pipeline sorts numerically.

## For Codex
- Room #9 (design) and #10 (contract). I won't edit `nova_chat` or `nova_collaboration`.
- `restart_model` should be `_rt_llama.restart` (with your socket wait); pass None in chat-only mode.

## For Cole
- The Qwen3.8 update and the 3.8 personality LoRA retrain go through the new dialog once Codex's UI lands. The download is about 24.4 GiB; training costs roughly $2-4 on your pod.
- Old 3.6 LoRAs and the 3.6 model are quarantined to `_admin/Trash/` only after 3.8 is proven loaded, and only the ones you tick.
