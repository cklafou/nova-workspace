_Last updated: 2026-10-06 03:19:21_
<!-- @nova: Orient note: how Nova's model updater checks, installs, rolls back and trains LoRAs, published in OPERATIONS.md. -->
---
doc: OPERATIONS.md
order: 45
---
<!-- @nova: Orient note: how Nova's model updater checks, installs, rolls back and trains LoRAs, published in OPERATIONS.md. -->
## Model updates

`general_tools/nova_updater/` is a general tool; its README has the full route contract. At each Nova
Chat start one cached catalog query looks for a newer dense Qwen of 27-32B with a permissive license,
and Nova Chat offers Update / Decline / "Remember my decision". The manual widget searches Hugging Face
and ModelScope (installable) and the Ollama library (link only).

Open **Widgets → Model updates** for Updates, Find models, Train adapters and Settings. The
notification's Update action opens the same installation review. Select a build, quantization,
projector and optional replacements, build a dry-run plan, review its disk/compatibility warnings,
then explicitly confirm it. Projector choices resolve an exact catalog path first, or a unique
filename; unknown or ambiguous choices fail. Changing choices discards the previous review. Jobs displays progress,
cancellation and separate recovery outcomes. Startup/status read configuration and catalog metadata;
installed-file inventory is requested only when entering an install or adapter workflow.

The router is attached in normal and chat-only launches. Its catalog check runs after a cancellable
three-second startup delay, outside the event loop; a catalog failure cannot block startup. Shutdown
cancels the task, while any already-running network request finishes under the catalog timeout.
Chat-only installs prepare the next model start and never invoke a model restart callback.
Nova start/stop transitions share the updater's exclusive-operation guard; updater writes return 409
until the launcher resolves the switch, including when a replacement worker inherits that switch.
When a displayed job finishes, the widget refreshes status once so completed work cannot leave a
stale busy flag disabling recovery controls.

Status reads the current boot selection on every request; a cached catalog result keeps its own
checked selection and is marked stale when those differ. Neither is proof that llama-server is running.

Training starts from a stored preview. Its `review_id` binds the start request to the reviewed
parameters and dataset checksums; changed input files require a new preview (HTTP 409).
Export creates training inputs only; it does not produce a finished adapter. Keeping an adapter means
no copy, conversion or retraining. A known cross-base adapter cannot be kept, and selected adapters
cannot also be quarantined. The installer rechecks those conditions before writing boot settings
and before finishing a pending switch. A second activation cannot overwrite a pending rollback snapshot.
RunPod requires explicit consent to the reviewed paid run (`paid: true`), with no per-run spending cutoff. Credentials are entered in Settings; blank fields leave saved values unchanged and
explicit clear checkboxes remove them. Secret values are not returned or saved in browser storage.

Installing never edits the launcher. It writes boot files that `start_llama_qwen36.cmd` reads from
`nova_body/memory/`: `active_model.txt`, `active_mmproj.txt` (`none` = no vision) and `active_lora.txt`
(`none` = no adapter); absent files mean the Qwen 3.6 defaults. The exact old boot files are saved to
the updater state BEFORE the first write, so a crash mid-switch is undone with `POST /api/updater/rollback`
(`/finish` refuses an interrupted switch). The install restarts the model and confirms llama-server
loaded the NEW file (`/props`, not just `/health`). If the restart fails, the file never loads, or the
user cancels while it loads, it restores the old boot files and restarts the previous model. The job
result keeps three facts apart: boot files restored, restart accepted, and the previous model confirmed
running again at `/props`. Only after a verified load are replaced files moved to
`_admin/Trash/<stamp>_model_update/` with a manifest. In chat-only mode the switch completes after the
next model start (`POST /api/updater/finish`). Finish and rollback take the same exclusive job
slot as installation and training; either returns HTTP 409 while another job holds it.

A LoRA trained for another base may fail to load or behave incorrectly. Choose no adapter or retrain
for the new base; the updater clears incompatible old KoELS selections. Keep is permitted only when
no known incompatibility or replacement conflict exists. Training
(`pod/`) generalises the v7 pipeline: inputs checksummed, the loss-mask template rebuilt from the new
model's own chat template and proven (GATE A/B) before training, every epoch converted. New adapters
are installed but not activated: A/B the epochs first. Activation with a restart is proven at
llama-server's `/lora-adapters`; running without the adapter counts as failure and restores the previous
adapter line (HTTP 502). RunPod runs first request a pod stop after completion, failure or cancellation.
Once all expected epoch adapters and complete runtime details have been verified and saved locally,
successful runs delete the pod and confirm it is gone. Its attached pod storage is released; a matching
saved pod ID is cleared so the next run creates a fresh pod. Unverified downloads, failed training and
cancellations retain the stopped pod for recovery and explicitly warn that storage can keep billing.
Delete failures retry a stop and report unresolved cleanup. Independent network volumes are never
deleted automatically. A killed updater process or unreachable provider can prevent cleanup; check
RunPod when the reported outcome is unconfirmed.

Final training inputs live in `models/Training Files/<friendly base-model name>/<training name>/`: a
frozen dataset, recipe, scripts, checksums and short README. Completed runs also retain checksummed
`Run Details/<job id>/` receipts for the exact base revision, tokenizer loss-mask audit, model config
and Python environment. Finished GGUF adapters live beside the base model, outside Training Files.
New pod packages isolate dependencies in a per-job virtual environment on container-local storage
while reusing the image's CUDA Torch; the Hugging Face weight cache also stays on local disk.
The durable input package, checkpoints and recovery outputs remain on the `/workspace` volume. Temporary ZIP exports, downloaded outputs and logs use
`Temp/updater/`; exporting is not training. Existing v6/v7 inputs are copied with matching hashes;
the historical originals are preserved in the dated script-retirement archive. Do not select both a complete corpus and its additive subset.
Frozen Training Files are excluded from the sync watcher's timestamp and PUP replacement writes;
change detection and backup queues still work. The eight restored October 4 inputs/receipts are also read-only
along with nineteen unchanged manifest entries, to protect their exact checksums from the older watcher until its next normal restart. Reproduce a
changed recipe in a new package rather than altering the checksummed originals.

The RunPod Settings credit check and paid-run preview query prepaid credit. New starts must meet
RunPod's one-hour minimum; a smaller balance than the estimated whole run produces a warning.
The prepaid wallet is the funding limit. Nova never adds funds automatically and has no separate
per-run spending cutoff. During training, the app refreshes wallet credit and shows the actual
pod hourly rate, elapsed time and estimated GPU spend; a manual top-up appears on a later refresh.
Low-credit warnings do not themselves stop an active run. Provider-enforced credit exhaustion is
separate from Nova's controls. Completed, failed and cancelled jobs retain their cost summary and
pod cleanup outcome: deleted, retained for recovery, or cleanup failed. Estimated GPU spend excludes
storage and is not a provider invoice. A stopped pod still incurs attached-storage charges; confirmed
pod deletion removes that pod's storage. Separate network-volume charges require separate cleanup.
Google browser sign-in does not configure the updater API key. New pods default to Japan
(`AP-JP-1`) near Korea; unavailability does not silently select a distant datacenter.

State lives in `general_tools/nova_updater/state/` (git-ignored), scratch in `Temp/updater/`, secrets in
`%USERPROFILE%\ProjectNovaData\Updater\credentials.json` beside the collaboration room's data. Not in
AppData: each MSIX-packaged launcher gets its own private AppData, which once split the room in two.

The launcher quotes the model and projector paths, so spaces work there. Boot-file paths must be plain
ASCII without cmd's special characters. Adapter paths with spaces are supported by quoting the
complete `path:scale` token; unsupported shell characters are refused. On Windows the
updater tests run the real launcher with llama-server replaced by an argument recorder.
