<!-- @nova: Record the LoRA installer repair, training file organization and approved RunPod preparation in progress. -->
# LoRA training preparation (work in progress)
**Summary:** The user's Qwen 3.8 install downloaded its model/projector but used Keep, so no LoRA training occurred. A cross-base Qwen 3.6 adapter remained selected. This has been repaired through the updater APIs; real training is being prepared.

## Did
- User clarified full targeted access to models and related folders. Updated root AGENTS.md and the Orient generator wording; large binaries remain excluded from broad documentation scans for efficiency.
- Finished adapters belong beside the model; training datasets/recipes/scripts belong under models/Training Files/<friendly model>/<run>.
- Copied finalized historical Qwen 3.6 v6/v7 training inputs with matching hashes; original historical sources remain.
- Fixed stale configured-model status, incompatible Keep selection and pending/quarantine protections. Added persistent training input packaging and clearer UI outcomes.
- Added RunPod credit checks, recharge link and Japan AP-JP-1 preference. Google browser login alone did not configure API access.
- Created the user-approved Nova Updater API key through the signed-in RunPod UI and saved it through Nova Chat Settings outside the repository. Broad GraphQL management permission, no serverless inference permission; no secrets recorded here.
- User explicitly approved existing laptop SSH key use and up to $15 for this training attempt. No automatic recharge.
- Supported rollback of pending plan 82bf6e38c8f76912, then clean no-adapter plan 865a676140713031 with replace=[]; install job 3c2dfe8f8989 reused and verified both downloaded files. No old adapters quarantined. Clean Qwen 3.8 boot configuration awaits model start; Nova remains off.

## Verified
- New live funding endpoint returned $63.11 available; API read listed no existing pods. Local SSH key path exists.
- Clean installer job succeeded, with runtime verification explicitly false because Nova is off. Active adapter list is empty.
- Agent backend/launcher/UI tests passed; final integrated tests remain after pipeline fixes.

## Open / next
- No paid pod has been created yet. Browser deployment form is only a prepared candidate.
- routing_audit owns pod template compatibility: real Qwen 3.8 config is Qwen3_5ForConditionalGeneration; current old CausalLM loader and converter flags need correction before paid work.
- bridge_research owns runpod.py repair: persistent training package names broke hard-coded remote /bundle paths. Complete and test before use.
- Root will regenerate/review Orient, restart chat-only controller with final code, export the finalized Qwen 3.8 package, train on Japan H200, retrieve/check adapters, stop the pod and record results.

## For Claude
Please leave updater source, its state, boot selections and training packages alone while this run is active. Do not start full Nova with old adapter settings. The user-approved budget and credential setup should not be asked again.

**Correction (2026-10-04 1205):** Cole explicitly superseded the $15 per-run budget. Use wallet credit only, with no custom spending cutoff or automatic recharge. Show live cost/credit warnings and final summaries. Code and tests now implement that.

Cole is gaming: do not control/focus the desktop. RunPod work is in background browser/terminal. The native controller at :8765 is intentionally not restarted again; a temporary host at :8877 uses the exact updated updater widget/API, PID 41736, source Temp/updater/live_training_host/host.py. It has normal live job/cancellation handling and persists finished jobs to updater history. Avoid starting updater work in the older :8765 process while this worker is active.

Actual first training job b7d307cb4c4f created Japan H200 pod ezt73ef3tpulbw at $4.59/h GPU ($4.64/h including selected storage in console). It failed at Ubuntu24 PEP668 dependency installation, before model weights/training, and stopped after ~76.5s / ~$0.10 GPU. Provider API confirmed EXITED. Existing pod ID saved in updater settings for reuse. routing_audit is fixing isolated venv bootstrapping. Frozen first package remains under Training Files/Qwen 3.8 27B Dense/nova_core_v7_qwen38; use fresh output name for corrected scripts.

Validation so far: updater suite 150 tests passed (1 optional tiny-ML test skipped in ordinary suite); actual optional CPU tiny Qwen conditional model SFT/checkpoint/GGUF proof passed separately. All 399 real rows passed tokenization/mask checks: max1517 tokens, zero truncation,40955 assistant tokens. Live insufficient-estimate warning also confirmed advisory: wallet63.11, estimate100, providerminimum4.61 returns sufficient-start with warning.
