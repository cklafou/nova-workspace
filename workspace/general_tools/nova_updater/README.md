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
   new adapter for the new base. The same tab trains LoRAs for models already installed, with
   no download (e.g. KoELS specialists).

## Safety rules (built in, tested)

- Routes follow the same rules as the Collaboration routes:
  - the caller is on loopback, and the Host names this computer with a port (blocks DNS rebinding);
  - proxy headers are refused, so a local tunnel cannot make remote callers look local;
  - a browser Origin must be exactly this server, because another local port is another site;
  - Fetch Metadata must say same-origin or none;
  - every POST must be JSON (415 otherwise), so a plain form cannot start a download.
- Downloads need `confirm: true`; paid GPU time needs a cost ceiling at least as large as the
  estimate the user saw. The pod is **stopped** in a `finally` block on success, failure,
  cancel or ceiling, and is **never terminated** (Terminate wipes `/workspace`).
- Downloads resume, then are checked against size and the published sha256. A mismatch is set
  aside as `.part.bad`, not installed.
- Switching models saves the exact old boot files first. After a restart it confirms that
  llama-server **loaded the new file** (`/props`), not merely that `/health` answers. If not,
  it restores the old boot files and restarts again.
- Quarantine moves files to `_admin/Trash/<stamp>_model_update/` with a `manifest.json`
  saying how to put them back.
- A LoRA trained for another base model loads without error and behaves wrongly. So after a
  switch the personality LoRA is set to `none` until one trained for the new base is
  installed. KoELS adapters for the old base are cleared too; both are restored on rollback.
- New adapters are installed but **not activated** by default: A/B both epochs first (the
  v6/v7 discipline). Activating one is a separate action.
- `models/` is read only when the user opens the dialog (GGUF headers only). The startup
  check reads boot files and the launcher, never model files.
- Secrets (RunPod key, optional HF token) live in
  `%LOCALAPPDATA%\ProjectNova\Updater\credentials.json`, outside the project. The UI shows
  only whether each is set.

## Boot files the launcher reads (`nova_body/memory/`)

| File | Content | Absent |
|---|---|---|
| `active_model.txt` | `models\qwen3.8\Qwen3.8-27B-UD-Q6_K_XL.gguf` | Qwen 3.6 default |
| `active_mmproj.txt` | projector path, or `none` | Qwen 3.6 projector |
| `active_lora.txt` | `--lora-scaled <path>:<scale>`, or `none` | v2 fallback, only on the 3.6 default model |
| `koels_lora_args.txt` | KoELS adapters (written by KoELS) | none |

## Nova Chat contract (Codex owns the UI)

```python
from nova_updater.api import create_router as create_updater_router
from nova_updater import check as updater_check
app.include_router(create_updater_router(restart_model=_rt_llama.restart))   # None in chat-only mode
# in startup_event(), both modes:
updater_check.start_background_check()
```

All routes are under `/api/updater`. Errors come back as `{"ok": false, "error": "..."}` with
status 400 for a bad request, 403 from the guard, 409 when another job is running, 415 for a non-JSON POST,
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
| `POST /plan {source, model_id, gguf_repo?, quant?, mmproj?, activate?, replace[], lora:{mode: none\|keep\|train, train:{...}}}` | Dry run: downloads, disk, compatibility, `invalidated` LoRAs, `warnings`, `blocking`, training estimate. Returns `id` |
| `POST /install {plan_id, confirm: true, train_confirm?: {max_cost_usd}}` | Starts the job and returns it |
| `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel` | Progress: `{state, step, done, total, percent, log[]}` |
| `POST /finish` | After a chat-only install: confirm the new model loaded, then quarantine |
| `POST /rollback` | Undo a switch that has not been verified |
| `POST /train/preview {spec}` | Validates the spec and returns the estimate (and cost for RunPod) |
| `POST /train {spec, confirm}` | `spec = {base_model_id, data_files[], preset: personality\|specialist, params?, output_name?, runner: export\|runpod}` |
| `POST /train/install {spec, folder}` | Install adapters from a manually run bundle (checks SHA256SUMS.txt) |
| `POST /lora/activate {path, scale, restart?}` | Equip an adapter |
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

`python -m unittest discover -s general_tools/nova_updater/tests -v` runs 61 tests. They
build a throwaway workspace and use fake catalogs; no network, no real models and no money.

## Not yet proven

- Windows end-to-end with real downloads.
- A supervised first RunPod run. The SSH flow is tested with fakes only.
- ModelScope downloads.
- Updating llama.cpp itself: not automated; the install's load check catches an
  unsupported architecture and rolls back.
