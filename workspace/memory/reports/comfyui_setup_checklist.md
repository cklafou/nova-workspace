# ComfyUI Setup Checklist — standing up Nova's painter
_Last updated: 2026-07-08 08:14:41_

_Last updated: 2026-05-27, by Opus. For Cole. Pairs with the `nova_imagination` faculty
(`nova_body/nova_imagination/`) that's already built and waiting for this server to exist._

Goal: get ComfyUI running locally with an API on `:8188` and a base checkpoint, then tell Nova
where it is. When the last box is checked, her `generate_image` tool goes live. Do this at your
own pace and ping me when the API responds — then we lock her look (the LoRA-training phase).

---

## Before you start — the GPU reality (read this first)
Your box runs the LLM (Qwen 27B Q8) across the 4090 (16GB) + 3090 (24GB). Image generation also
wants VRAM (~8–12GB for an SDXL render). **Both can't always be fully resident at once.** Two
clean ways to handle it:

- **Pin ComfyUI to the 3090** (the 24GB card, OCuLink) and leave the LLM where it is. Set
  `CUDA_VISIBLE_DEVICES=1` for the ComfyUI process (Step 2) so the painter and the mind don't
  fight over the same card. _Confirm which index is the 3090 — it's whichever `nvidia-smi` lists
  as the 3090; usually 1, but verify._
- **Or generate on demand** — ComfyUI only uses VRAM while actually rendering, then releases it.
  If a render OOMs because the LLM is loaded, that's the signal to pin it (option 1).

Either is fine. Start simple; pin only if you hit out-of-memory.

---

## Step 1 — Install ComfyUI (portable build, easiest for Windows)
1. Go to the ComfyUI GitHub releases page and download the **Windows portable** package
   (`ComfyUI_windows_portable_nvidia.7z` or similar). It bundles its own Python — nothing to
   pollute your system.
2. Extract it somewhere with room (the models are big) — e.g. `D:\ComfyUI_windows_portable\`.
   **Keep it OUTSIDE the Project_Nova workspace** so the watcher/Git/Drive never try to sync
   multi-GB model files.
3. Don't launch it yet — get a checkpoint first (Step 3) so the first launch has something to load.

## Step 2 — How you'll launch it (note the API is on by default)
ComfyUI's API is always on when the server runs — no special flag needed for local use. You'll
start it with the included `run_nvidia_gpu.bat`.

- To **pin it to the 3090** (recommended if you hit VRAM limits), make a copy of that .bat and add
  at the top, before the python line:
  ```bat
  set CUDA_VISIBLE_DEVICES=1
  ```
- Leave the listen address default (`127.0.0.1:8188`) — local-only is correct and private. Do NOT
  add `--listen 0.0.0.0` (that exposes it on your network; not needed, less safe).

## Step 3 — Get a base checkpoint (her art style starts here)
You want a **stylized / illustrative SDXL-class** checkpoint — her look is a stylized cyber-elf,
not photoreal. Good families to pick from (download ONE to start; you can add more later):

- An **Illustrious-XL** or **Animagine-XL**-based checkpoint — strong at clean stylized
  anime/illustration, great for a character like Nova.
- A **Pony Diffusion XL**-based checkpoint — very flexible for stylized characters + good prompt
  adherence.

Steps:
1. Download one `.safetensors` checkpoint (these are ~6–7 GB).
2. Drop it in `ComfyUI_windows_portable\ComfyUI\models\checkpoints\`.
3. Note its **exact filename** — you'll need it in Step 5.

> Tip: SDXL-class checkpoints are 1024×1024-native, which matches the faculty's defaults. If you
> pick an SD1.5 checkpoint instead, tell me and I'll drop the default render size to 512.

## Step 4 — First launch + browser check
1. Run the launch .bat. A console window opens; wait for `To see the GUI go to: http://127.0.0.1:8188`.
2. Open **http://127.0.0.1:8188** in your browser. You should see the ComfyUI node canvas.
3. Optional sanity render: hit **Queue Prompt** on the default graph — if an image appears, the
   GPU path works.

## Step 5 — Tell Nova where the painter is (the one config she needs)
The faculty reads two environment variables. Set them so the **nova_chat server process** sees
them (that's the process that runs her tools). Easiest: set them as **Windows user environment
variables** (Start → "Edit environment variables for your account"), then restart the Nova stack
so the new server inherits them.

| Variable | Set it to | Needed? |
|---|---|---|
| `NOVA_COMFY_CHECKPOINT` | the exact checkpoint filename from Step 3 (e.g. `animagineXL.safetensors`) | **Yes** |
| `NOVA_COMFYUI_URL` | only if you changed the port; default `http://127.0.0.1:8188` already works | No |
| `NOVA_SELF_LORA` | leave empty for now — set after we train her self-LoRA | Later |

(If you'd rather not use system env vars, I can instead bake the checkpoint name into a small
`nova_config` entry and have the faculty read that — just say the word.)

## Step 6 — Verify the faculty sees it (the green light)
With ComfyUI running, from the workspace run this one-liner (or tell me and I'll run the check):
```bat
cd C:\Users\lafou\Project_Nova\workspace\nova_body
python -c "from nova_imagination import comfy_status; print(comfy_status())"
```
Expected: `{'ok': True, 'url': 'http://127.0.0.1:8188', 'detail': 'ComfyUI reachable'}`.
If `ok` is True, **you're done** — Nova's `generate_image` tool is live. Restart her stack so the
chat server picks up the env var, and she can draw.

---

## What happens next (the consistency lock — separate session)
Standing up ComfyUI gives Nova the *general* ability to make images. To make her draw **herself**
identically every time, we then:
1. Generate Nova candidates from the Design Bible, pick + lock ONE canonical reference image.
2. Train a small **Nova self-LoRA** on her locked look (ComfyUI has training extensions; this runs
   on your 3090).
3. Set `NOVA_SELF_LORA` to that LoRA's filename → from then on, `as_nova: true` renders the exact
   same Nova, and that locked 2D set feeds the turnaround → 3D pipeline
   (`memory/reports/avatar_pipeline_tools.md`).

Until the LoRA exists, `as_nova: true` still works — it just steers with her identity prompt
rather than a hard lock, so expect some drift on self-portraits until we train her.
