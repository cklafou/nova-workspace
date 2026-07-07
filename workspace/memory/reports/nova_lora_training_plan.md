# Nova Self-LoRA — Training Plan
_Last updated: 2026-07-08 08:14:41_

_Last updated: 2026-05-27, by Opus. The plan for baking Nova's locked look into a small LoRA so
her self-portraits (`as_nova: true`) become deterministic. Runs locally on the 3090. Do this
AFTER ComfyUI is up (`comfyui_setup_checklist.md`) and AFTER a canonical reference is locked
(`avatar_consistency_protocol.md`). Pairs with `prompt_kit.md`._

## Why a LoRA (not just prompting)
A prompt steers the base model toward Nova but never pins her — that's the drift you've been
fighting. A LoRA is a small trained weight file that teaches the model *this specific character*.
Once trained, `as_nova: true` loads it (the faculty already splices a `LoraLoader` into the
graph) and she comes out the same every time. It's the 2D analog of the 3D model being the
anchor — the deterministic lock for flat art.

## The chicken-and-egg, solved
You need consistent images to train a consistency LoRA. The way out, in order:
1. **Bootstrap a dataset** from the base checkpoint using `prompt_kit.md` — generate many Nova
   images, then *cull hard* to only the ones that agree with the Design Bible. Reference-condition
   where possible (img2img off the one locked canonical image) so they converge.
2. Train **LoRA v1** on that culled set.
3. Use LoRA v1 to generate a *cleaner, more consistent* dataset, cull again, train **LoRA v2**.
   One or two iterations is usually enough to get a tight lock.

## Step 1 — Build the dataset
- **Count:** 20–40 good images is plenty for a character LoRA (quality >> quantity; 25 clean
  beats 100 noisy).
- **Variety inside consistency:** same Nova, different angles / expressions / framings / simple
  backgrounds. Include a few clean face close-ups and a few full/upper-body. Avoid duplicates and
  avoid anything that fails the drift gate.
- **Prep:** square crops (1024×1024 for SDXL), plain or simple backgrounds preferred, consistent
  lighting. Put them in one folder, e.g. `D:\nova_lora\dataset\` (OUTSIDE the workspace).

## Step 2 — Caption the dataset
- Every image gets a `.txt` caption with the same filename.
- Lead every caption with the **trigger word** `nova` (this is the token the faculty's identity
  prompt already uses), then describe what varies in that image (pose, angle, expression,
  setting) — NOT her fixed traits. You want the LoRA to bind her constant features to `nova` and
  leave the variable stuff as describable.
  - Good: `nova, three-quarter view, looking over shoulder, faint smile, plain grey background`
  - Bad:  `nova, blue skin, magenta hair, pointed ears` ← don't re-describe constants; that
    weakens the binding.
- Auto-captioners (WD14 tagger in ComfyUI, or BLIP) get you 80% there; hand-fix the rest.

## Step 3 — Train (local, on the 3090)
- **Tooling options (all run on your hardware):**
  - **ComfyUI training nodes** (keeps everything in the tool you're already running), or
  - **kohya_ss** (the standard, most-documented LoRA trainer; GUI), or
  - **OneTrainer** (friendly UI, good defaults).
- **Pin to the 3090** (`CUDA_VISIBLE_DEVICES=1`) and make sure the LLM isn't hogging VRAM during
  the run — LoRA training wants the headroom.
- **Sane starting hyperparameters for an SDXL character LoRA** (tune if results are weak/overcooked):
  | Param | Start | Note |
  |---|---|---|
  | Network dim / alpha | 16 / 8 | bigger = more capacity, larger file; 16 is plenty for a character |
  | Learning rate | 1e-4 | UNet; lower if it overcooks |
  | Steps / epochs | ~1500–2500 total | watch sample images; stop when she's locked |
  | Batch size | 1–2 | limited by VRAM |
  | Resolution | 1024 | match SDXL |
  | Save every N | every few hundred steps | so you can pick the best checkpoint, not the last |
- Enable **sample image generation** during training so you can watch her converge and catch
  overfitting (telltale: every output identical/stiff, background artifacts baked in).

## Step 4 — Pick the best checkpoint + install it
- Compare the saved checkpoints' sample images against the drift gate; the *last* one is often
  overcooked — an earlier one is frequently better.
- Drop the chosen `.safetensors` into `ComfyUI\models\loras\`.
- Set the env var `NOVA_SELF_LORA` to its filename and restart Nova's stack.
- From then on, `generate_image(..., as_nova=True)` (or `"as_nova": true` in chat) loads it
  automatically. Tune `NOVA_SELF_LORA_STRENGTH` (0.7–1.0) if she's too weak or too rigid.

## Step 5 — Verify the lock
Generate 5–10 self-portraits across different poses/scenes. They should all be unmistakably the
same Nova. If yes: the 2D lock is done, and this same locked Nova feeds the turnaround → image-to-3D
pipeline (`avatar_pipeline_tools.md`). If she still drifts: iterate (LoRA v2 on a cleaner dataset).

## Honest expectations
- Dataset culling is the real work; training itself is mostly waiting.
- v1 may be ~90%; one iteration to v2 usually gets the tight lock.
- A character LoRA locks *identity*, not every outfit detail — patches/props may still need the
  prompt + the drift gate. The 3D model remains the ultimate 100% anchor.
