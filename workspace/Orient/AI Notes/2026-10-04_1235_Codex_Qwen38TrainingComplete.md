<!-- @nova: Record completed Qwen 3.8 LoRA training, verified outputs, wallet-only funding and remaining activation checks. -->
# Qwen 3.8 LoRA training completed
**Summary:** Real RunPod job `7e4c3f79ab5b` succeeded, installing both verified epoch adapters beside the Qwen 3.8 base. Nova stayed off and the native controller was not restarted while Cole games.

## Did
- Corrected the initial incompatible keep/quarantine installation through supported rollback and re-install APIs. Boot selection now Qwen 3.8 + matching projector, no active LoRA; pending model-start verification remains recoverable.
- Finished adapters: `workspace/models/qwen3.8/nova_core_v7_qwen38_r2_epoch1.gguf` and `..._epoch2.gguf` (318,802,784 bytes each).
- Reproduction inputs: `workspace/models/Training Files/Qwen 3.8 27B Dense/nova_core_v7_qwen38_r2/`. Both model and training-model folders have concise READMEs. Legacy v6/v7 packages were copied/hash-verified; original historical files retained.
- Runtime details and completion proof: package `Run Details/7e4c3f79ab5b/`, including exact base revision, config, environment, template/mask audit, final trainer state and `completion-verification.json`.
- Fixed Qwen multimodal loader/assistant mask, language-only targets, pinned Python/converter dependencies, Ubuntu PEP668 virtual environment setup, SSH readiness/remote directory launch, RunPod wallet checks and actual-rate/cost reporting. Future venvs use container-local disk; frozen successful r2 package accurately preserves its earlier package-local venv.
- Funding policy supersedes the earlier $15 idea: explicit paid consent, RunPod wallet limit, no automatic recharge and NO custom per-run cutoff. Low-wallet warnings and live/final metrics appear in app, including failed attempts.
- Credentials remain outside repository in the existing ProjectNovaData updater store. Do not print them.

## Verified
- GPU: H200 SXM, Japan AP-JP-1, $4.59/hour GPU. Pod `ezt73ef3tpulbw` completed 100 optimizer steps/two epochs on all 399 corpus rows; no truncation, assistant loss present in every row.
- Real training runtime 643.6 seconds; aggregate training loss 1.589; recorded metrics finite. This is training evidence, not held-out behavioral quality.
- Both GGUFs SHA-256 matched remote manifests and installed receipts; headers show qwen35, LoRA, 512 tensors, alpha32, Qwen3.8-27B base URL and header-derived qwen3.8 binding.
- Frozen input and runtime-details checksums passed independently. GPU provider returned EXITED with no port mappings, stop timestamp 2026-10-04 12:31:08 KST. Console rate fell to retained-storage-only $0.04/hour.
- Successful attempt estimated GPU cost $1.907; first setup failure $0.0975. Provider invoices/storage differ; wallet billing updates lag. First attempt failed before training, was stopped, and its frozen package remains documented as failed.
- Updater unittest suite: 152 tests, 3 skipped (opt-in ML/Linux tests). Actual tiny model-to-GGUF and two real Linux venv tests were separately passed. Nova Chat integration tests passed earlier; durable Node UI tests pass. Real browser showed final adapter paths, training inputs/run details and both final cost reports without console errors.

## Open / next
- Adapters are installed INACTIVE. Actual llama-server load, A/B behavior and selection of default epoch remain untested. Do not equate `pick: epoch2` with evaluation or activation.
- The stopped pod retains a 150 GB recovery volume, approximately $0.04/hour in the console. Do not terminate it casually: checkpoints and remote logs remain there.
- Original native controller on 8765 still runs pre-update backend code. Paid work used hidden current-code updater host on 8877 to avoid focusing/reopening native windows. It must be retired after history is saved; native update loads on next normal app restart. No actual Nova/model start during the game.
- Automatic output verification checks transfer hashes; root additionally verified the actual two epoch headers/count for this run. Batch installation is atomic per file rather than across the entire set; a future failure should recover downloaded outputs, not retrain.
- User's next request: Start/Stop Nova button directly in Conversation tab. Frontend agent is implementing against existing lifecycle routes; backend audit underway. Also repairing stale recovery controls after a training job finishes.

## For Claude / Cole
- Use READMEs above for what to select. Do not re-run training: both adapters already exist.
- Nova Chat / desktop have been left available without controlling the user's desktop. Cole permits a gentle YouTube attention chime only when input is actually needed while gaming; no need to alert him for routine progress.
