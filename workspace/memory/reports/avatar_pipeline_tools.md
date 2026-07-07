# Nova Avatar — AI-Assisted Pipeline for a Non-Artist (2026 tools)
_Last updated: 2026-07-08 08:14:41_
_2026-05-27, by Opus. Current tool landscape from web research (May 2026). Tools move fast —
re-check before committing money. Pairs with `memory/Nova_Avatar_Design_Bible.md` (the written
source of truth you check every step against)._

## The principle (why this order)
Drift is killed by **locking the design, then deriving everything from a single anchor**.
End state: a clean **3D model** is the anchor; every 2D image is just a camera angle of it →
zero drift forever. We get there: lock 2D character → consistent turnaround → image-to-3D →
clean/rig in Blender → the `.blend` is canonical.

## Your hardware reality
- **GPU 0:** RTX 4090 laptop **16GB** · **GPU 1:** RTX 3090 **24GB** (OCuLink eGPU).
- That 24GB card matters: the best **local/free** image-to-3D (TRELLIS.2) wants ~24GB — the
  3090 clears it. Lighter local options (Hunyuan3D 2.1) run on far less.
- So you genuinely have two viable routes: **local/free** (private, on-brand with her
  local-first ethos, learning curve) or **web/paid** (fast, easy, less private). You can mix.

---

## STEP 1 — Lock her as a consistent 2D character
Goal: regenerate Nova in any pose/angle without her face/outfit reinventing themselves.
- **Easiest (web):** **Midjourney `--cref`** (character reference), or **Ideogram Character**
  (1–3 reference images → extracts features), or **Scenario / Leonardo** character-reference.
- **Strongest consistency (benchmarked):** photo-/reference-locking tools like **ToonyStory**
  (topped a 140-image consistency test by enforcing features as constraints) — built for
  multi-image consistency.
- **Local/free:** train a small **LoRA** on Gemini's concept in **ComfyUI** (on your rig), or
  use IP-Adapter/reference. More setup, fully private, reusable forever.
- **Input:** Gemini's concept + the Design Bible. **Output:** a "locked" Nova you can re-pose.

## STEP 2 — Generate the orthographic turnaround (front / side / back, neutral pose)
This is the **hardest step** — AI drifts most here, and it's where you must DECIDE the
undefined parts (legs, back, full outfit — see Bible §7).
- **Purpose-built:** **CharacterGen** is specifically recommended for game-style turnaround
  sheets (consistent front/side/back).
- **Local/controllable:** **ComfyUI + ControlNet/OpenPose** with a turnaround pose template +
  your locked character → guided front/side/back. Most control, free, on your GPUs.
- Expect iteration: generate, cherry-pick views that AGREE with each other, fix in the Bible.
- **Output:** a clean multi-view model sheet on a plain background (white/black bg helps Step 3).

## STEP 3 — Image → 3D base mesh
Feed the turnaround views in (multi-view input >> single image for quality).
- **Best production quality (web, free-to-generate):** **Rodin (Hyper3D Gen-2)** — clean quad
  topology, **T/A-pose enforcement**, multi-image fusion; the one reviewers said drops in
  without hours of cleanup.
- **Most balanced / mature workflow (web):** **Meshy 6** — image-to-3D, PBR textures, topology
  controls, broad exports, and **built-in auto-rigging** (the others don't rig natively).
- **Clean game topology (web):** **Tripo** — quad topology, good for later rigging.
- **One-stop:** **3D AI Studio** bundles Meshy/Rodin/Tripo/Hunyuan/TRELLIS under one login.
- **Local/free:** **TRELLIS.2** (Microsoft, ComfyUI, ~24GB → your 3090; cleaner topology) or
  **Hunyuan3D 2.1** (Tencent, runs on small VRAM, great textures). Both private, on your rig.
- **Output:** a textured 3D mesh of Nova.

## STEP 4 — Clean + rig in Blender
- Import the mesh into **Blender**.
- **Rig (non-artist):** **Mixamo** (free, auto-rigs humanoids) — or use **Meshy/Rodin** if you
  rigged there. Honest caveat: AI-generated topology is usually fine for a static "source of
  truth" render but can be messy for animation; a static locked model is enough for the
  blueprint, animation-clean topology may need a later pass.
- **Output:** the canonical `.blend`.

## STEP 5 — Lock it as the blueprint
- Render orthographic front/side/back/¾ from the `.blend` → that's your **consistent 2D sheet**,
  now perfectly matching the 3D. All future 2D = renders or reference off this model. Drift gone.

---

## Recommended path for *you* (non-artist, has the GPUs, values local-first)
Fastest-to-result this weekend (web): **Midjourney --cref or Ideogram (lock 2D) →
CharacterGen (turnaround) → Rodin or Meshy (3D, Meshy if you want auto-rig) → Blender + Mixamo.**

On-brand local route (private, free, more setup): **ComfyUI + LoRA (lock 2D) → ComfyUI +
ControlNet (turnaround) → TRELLIS.2 or Hunyuan3D in ComfyUI (3D) → Blender + Mixamo.**

Either way: **the Design Bible is your referee** — check every output against it; when a tool
drifts (recolors the cyan, changes the eyes, drops the OCULINK patch), reject and regenerate.

## Honest expectations
- Step 2 (consistent turnaround) will take iteration even with the best tools.
- Image-to-3D output is a strong *base*, not a finished hero asset — budget a Blender cleanup pass.
- A non-artist can absolutely reach a locked, consistent blueprint with this; it just takes
  patience at Steps 2–4, not art skill.
