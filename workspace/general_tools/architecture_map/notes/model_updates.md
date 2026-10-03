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

Installing never edits the launcher. It writes boot files that `start_llama_qwen36.cmd` reads from
`nova_body/memory/`: `active_model.txt`, `active_mmproj.txt` (`none` = no vision) and `active_lora.txt`
(`none` = no adapter); absent files mean the Qwen 3.6 defaults. The install saves the old boot files,
restarts the model, confirms llama-server loaded the NEW file (`/props`, not just `/health`) and rolls
back if not. Only then are replaced files moved to `_admin/Trash/<stamp>_model_update/` with a manifest.
In chat-only mode the switch completes after the next model start (`POST /api/updater/finish`).

A LoRA trained for one base loads on another without error and behaves wrongly, so a switch sets the
personality LoRA to `none` and clears KoELS adapters for the old base until new ones exist. Training
(`pod/`) generalises the v7 pipeline: inputs checksummed, the loss-mask template rebuilt from the new
model's own chat template and proven (GATE A/B) before training, every epoch converted. New adapters
are installed but not activated: A/B the epochs first. RunPod runs need a confirmed cost ceiling and
always stop, never terminate, the pod.

State lives in `general_tools/nova_updater/state/` (git-ignored), scratch in `Temp/updater/`, secrets in
`%LOCALAPPDATA%\ProjectNova\Updater\credentials.json`.
