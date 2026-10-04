<!-- @nova: How Nova's model updater works: startup check, manual search, install with rollback and quarantine, LoRA training, and the Nova Chat contract. -->
# Nova model updater (`general_tools/nova_updater`)

A general tool, not a body part. It answers three questions for Cole:

1. **Is there a better model?** At every Nova Chat start, one lightweight query (cached 12 h,
   background thread, never blocks or raises) looks for a newer **dense** Qwen in Nova's size
   class (27–32B), permissively licensed (Apache-2.0/MIT: the licensing rule for Nova's weights).
   If one exists, Nova Chat shows a notification: **Update / Decline**, plus **Remember my
   decision** for each version.
2. **Install it safely.** The notification and the manual widget open one dialog. It shows
   which build and quant to use (like-for-like with today by default) and which installed
   models/LoRAs to replace (optional). Replaced files go to trash quarantine, never deleted,
   and only after the new model is proven loaded.
3. **Train a LoRA for it.** Optional training data (e.g. the v7 personality corpus) trains a
   new adapter for the new base. The same tab trains LoRAs for models already installed,
   without replacing the local inference model (e.g. KoELS specialists).

## Safety rules (built in, tested)

- Routes follow the same rules as the Collaboration routes:
  - the caller is on loopback, and the Host names this computer with a port (blocks DNS rebinding);
  - proxy headers are refused, so a local tunnel cannot make remote callers look local;
  - a browser Origin must be exactly this server, because another local port is another site;
  - Fetch Metadata must say same-origin or none;
  - every POST must be JSON (415 otherwise), so a plain form cannot start a download.
- Downloads need `confirm: true`; paid GPU time needs `confirm: {paid: true}` for the reviewed run.
  RunPod wallet credit is the funding limit. There is no per-run spending cutoff and Nova never
  recharges credit. Low credit produces a warning and billing link while the run continues.
  The runner requests a pod stop in a `finally` block on success, failure or cancellation.
  After a successful run's expected epoch adapters and complete provenance are verified and saved
  locally, it deletes the training pod and confirms removal, releasing the attached pod storage.
  It clears a matching saved pod ID so the next run creates a fresh nearby pod. Download/validation
  failures and cancellations retain recovery data with an explicit ongoing-storage warning.
  Failed deletion is reported and a stop is retried; never confuse an accepted stop with deletion.
  Separately attached network volumes are not deleted. Process death or an unavailable provider
  can prevent automatic cleanup; job messages identify unconfirmed cleanup for action in RunPod.
- Downloads resume, then are checked against size and the published sha256. A mismatch is set
  aside as `.part.bad`, not installed.
- Switching models saves the exact old boot files to the updater state **before the first
  write**, so a crash or power cut mid-switch stays recoverable (`POST /rollback`; `/finish`
  refuses an interrupted switch). After a restart it confirms that llama-server **loaded the new
  file** (`/props`), not merely that `/health` answers. If the restart fails, the new model never
  loads, or the user cancels while it loads, it restores the old boot files and restarts the
  previous model. The job's result, not just its log, records three separate facts: boot files
  restored, the restart accepted (`rollback.previous_model_restart`: `ok`, `failed` or
  `not attempted`), and the previous model confirmed running again at `/props`
  (`rollback.previous_model_verified`).
- Quarantine moves files to `_admin/Trash/<stamp>_model_update/` with a `manifest.json`
  saying how to put them back.
- A LoRA trained for another base model can fail to load or behave incorrectly. So after a
  switch the personality LoRA is set to `none` until one trained for the new base is
  installed. KoELS adapters for the old base are cleared too; both are restored on rollback.
- New adapters are installed but **not activated** by default: A/B both epochs first (the
  v6/v7 discipline). Activating one is a separate action. With `restart: true` it is proven
  at llama-server's `/lora-adapters`; "running bare" counts as failure. On failure the previous
  adapter line is restored and the answer is HTTP 502 with `ok: false`.
- Installed-file inventory reads GGUF headers when requested and skips the `Training Files`
  input-package subtree. Install, training and import actions write their explicitly selected
  artifacts. The startup check reads boot files and the launcher, never model weights.
- Secrets (RunPod key, optional HF token) live in
  `%USERPROFILE%\ProjectNovaData\Updater\credentials.json`, beside the collaboration room's data
  and outside the project. Not in AppData: Windows gives each MSIX-packaged launcher its own private
  AppData, so a key saved from one launcher would be missing in another. The UI shows only whether
  each is set.

## Boot files the launcher reads (`nova_body/memory/`)

| File | Content | Absent |
|---|---|---|
| `active_model.txt` | `models\qwen3.8\Qwen3.8-27B-UD-Q6_K_XL.gguf` | Qwen 3.6 default |
| `active_mmproj.txt` | projector path, or `none` | Qwen 3.6 projector |
| `active_lora.txt` | `--lora-scaled "<path>:<scale>"`, or `none` | v2 fallback, only on the 3.6 default model |
| `koels_lora_args.txt` | KoELS adapters (written by KoELS) | none |

The launcher quotes the model and projector paths, so spaces are fine there (a stray quote inside a
boot file is dropped). Every path must be plain ASCII without `" % ! ^ & | < > ( )`, because cmd
reads boot files in the console code page and echoes them unquoted. Adapter paths support spaces:
the writer quotes the **entire** `path:scale` value as one command argument, and active-adapter
discovery parses that quoted form. Paths still cannot contain `:` or `,` (llama-server reads
`--lora-scaled` as `FNAME:SCALE,...`), so adapter paths are workspace-relative. For example:
`--lora-scaled "models\Qwen 3.8 27B Dense\Nova Personality Epoch 2.gguf:0.6"`.
The Windows launcher fixture verifies that the whole value reaches the process as one argument.

## Nova Chat contract (Codex owns the UI)

```python
from nova_updater.api import create_router as create_updater_router
from nova_updater import check as updater_check
app.include_router(create_updater_router(restart_model=_rt_llama.restart))   # None in chat-only mode
# in startup_event(), both modes:
updater_check.start_background_check()
```

All routes are under `/api/updater`. Errors come back as `{"ok": false, "error": "..."}` with
status 400 for a bad request, 403 from the guard, 409 when another job is running or training data
changed since its preview, 415 for a non-JSON POST,
and 502 when a catalog is down.

| Route | Purpose |
|---|---|
| `GET /status` | `{state, checked_at, current, candidates[{id, version, size_b, params_b, created, license, url, remembered}], notify, pending[], pending_install, busy, sources, settings, credentials}` |
| `POST /check {force}` | Re-run the check now |
| `POST /decision {ids[], decision: "update"\|"decline", remember}` | Notification buttons. `remember` silences those versions; a plain decline lasts until the next Nova Chat start |
| `POST /forget {id}` | Undo a remembered decision |
| `POST /settings {...}` | `enabled`, `ttl_hours`, `min_b`, `max_b`, `licenses`, `source`, `authors` |
| `GET /search ?source&q&author&min_b&max_b&dense&license&format&pipeline&include_quantized&sort&limit&newer` | Manual search. `source` is `huggingface`, `modelscope` or `ollama` (Ollama is link-only). `sort` is `created`, `modified`, `downloads`, `likes` or `params` |
| `GET /candidate ?id&source&gguf_repo` | GGUF builds of one model: quants with sizes and files, projectors, and the `suggested` like-for-like choice |
| `GET /inventory` | Installed models, projectors and LoRAs: kind, size, `bound_to` base family, `active` |
| `POST /plan {source, model_id, gguf_repo?, quant?, mmproj?, activate?, replace[], lora:{mode: none\|keep\|train, train:{...}}}` | Dry run: downloads, disk, compatibility, `invalidated` LoRAs, `warnings`, `blocking`, training estimate. Returns `id`. `mmproj`: a projector `path` from `/candidate`, used exactly (400 if the build has no such file); `false` = no vision; omitted = like today |
| `POST /install {plan_id, confirm: true, train_confirm?: {paid: true}}` | Starts the job and returns it |
| `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel` | Progress: `{state, step, done, total, percent, log[]}` |
| `POST /finish` | After a chat-only install: confirm the new model loaded, then quarantine. 409 while any install or training job runs |
| `POST /rollback` | Undo a switch that has not been verified. 409 while any install or training job runs |
| `POST /train/preview {spec}` | `spec = {base_model_id, data_files[], preset: personality\|specialist, params?, output_name?, runner: export\|runpod, base_model_path?, output_directory?, data_center_ids?}`. Validates and remembers it (24 h); returns the prepared spec with data `sha256`s, separate `training_directory`/`output_directory`, the estimate, `cost` for RunPod, and `review_id` |
| `POST /train {review_id, confirm}` | Starts exactly the reviewed run. 409 if a data file changed since the preview (preview again); 400 without a valid `review_id`. RunPod: `confirm = {paid: true}`; uses prepaid wallet credit without a custom spending cutoff |
| `POST /train/install {spec, folder}` | Install adapters from a manually run bundle (checks SHA256SUMS.txt) |
| `POST /lora/activate {path, scale, restart?}` | Equip an adapter. With `restart`, it is verified at `/lora-adapters`; failure gives 502 and the previous line is restored |
| `GET`/`POST /credentials` | RunPod key, `ssh_key_path`, `pod_id`, HF token. Write-only: GET returns only whether each is set |

The dialog needs these choices: build, quant, projector, replace checkboxes (pre-tick the
`invalidated` LoRAs when the user chooses "replace old LoRAs"), activate, and LoRA mode.
Training adds data files, preset, runner and advanced params. Show the plan's `warnings`
and `blocking` before the confirm button.

## Training (`pod/`)

`run_on_pod.sh` is the v7 pipeline, generalised. It verifies inputs (sha256 and row counts),
builds and proves the loss-mask template, trains, converts **every** epoch to GGUF (sorted
numerically) and writes `SHA256SUMS.txt`. `template_gen.py` patches the base model's own chat
template by structure rather than by exact text, then proves it:

- **GATE A:** 12 renders byte-identical to the official template.
- **GATE B:** the loss falls on assistant text only.

On `unsloth/Qwen3.6-27B` it reproduces v6's hand-made `qwen_template_gen.jinja`
byte-for-byte, and it passes on Qwen3.8-27B, whose template changed (v7's fixed patch refuses
it).

## Where training files and finished adapters go

The two locations serve different purposes:

```text
models/
  qwen3.8/
    Qwen3.8-27B-UD-Q6_K_XL.gguf       # the inference model
    nova_personality_v8_epoch1.gguf  # finished adapter, beside its base model
    nova_personality_v8_epoch2.gguf
  Training Files/
    Qwen 3.8 27B Dense/
      README.md
      nova_personality_v8/
        README.md
        Nova Personality.jsonl     # original reviewed dataset filename
        job.json                   # base repo, dataset hashes and parameters
        train_lora.py
        template_gen.py
        run_on_pod.sh
        inputs.sha256
        outputs.json               # added after verified adapter import
```

Preparing a preview does not create these folders. Export, confirmed training and importing
completed outputs preserve the reviewed inputs in the friendly base-model folder. Each run
name gets a complete package, published atomically. Repeating the same recipe reuses its
unchanged package; changed inputs or a different recipe require a new run name. The short
READMEs explain each file and how to run the package. Existing adapter locations remain valid;
this code does not migrate old files on startup.

Finished adapters keep their generated epoch filenames and go to `output_directory`, outside
`Training Files`. An install plan supplies the selected model's destination automatically.
Standalone training can supply `base_model_path` to use that installed GGUF's directory, or
`output_directory` explicitly; otherwise the default is `models/<base_family>/`. The preview
shows both destinations. Imported GGUFs must match the supplied `SHA256SUMS.txt`; existing
adapter files are never overwritten. The package's `outputs.json` records verified transfer
hashes and locations; it does not claim those hashes prove which training procedure ran.

Temporary downloads, scratch and logs stay under `Temp/updater`. Export produces a convenient
ZIP there while its source input package remains under `Training Files`. Exporting does not
train a LoRA, spend GPU time or activate an adapter. Running training or importing completed
outputs also does not activate them; activation is separate.

The saved recipe names the exact model repository and retains dataset/script checksums. The
template generator fetches the base tokenizer at execution time, and the pod setup installs
current dependencies; these packages do not pin remote model revisions or promise bit-identical
retraining. New-pod location preferences are part of the reviewed spec: `data_center_ids`
defaults to `AP-JP-1` (Japan), with explicitly selected alternatives preserved.

## Command line

```
python -m nova_updater check --force
python -m nova_updater candidate Qwen/Qwen3.8-27B
python -m nova_updater plan Qwen/Qwen3.8-27B --replace models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf
python -m nova_updater install <plan_id> --yes
python -m nova_updater train-bundle --base unsloth/Qwen3.8-27B --data _admin/Training_stuff/v7/nova_core_v7.jsonl
```

Run these from `workspace/general_tools`.

## Tests

`python -m unittest discover -s general_tools/nova_updater/tests -v` runs the updater suite. Tests
build a throwaway workspace and use fake catalogs; no network, no real models and no money.
Six launcher cases run only on Windows: they start the real launcher in a temporary folder with llama-server
replaced by an argument recorder, and check what it would receive.

## Not yet proven

- Windows end-to-end with real downloads.
- A supervised first RunPod run. The SSH flow is tested with fakes only.
- ModelScope downloads.
- Updating llama.cpp itself: not automated; the install's load check catches an
  unsupported architecture and rolls back.
