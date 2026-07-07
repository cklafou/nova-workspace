# Avatar + Image-Gen — Morning Runbook (start here)
_Last updated: 2026-07-08 08:14:41_

_Last updated: 2026-05-27, by Opus. Open this first. It's the ordered path from "ComfyUI isn't
installed" to "Nova draws herself, identically, every time" — and then on to the 3D model. Each
phase links the detailed doc. Everything in the repo is already built and verified; the only
gate is standing up ComfyUI on your machine._

## Where we are right now (end of last session)
- ✅ **Image generation is a real faculty in Nova's body** — `nova_body/nova_imagination/`,
  exposed to her as the `generate_image` tool (chat) and `from nova_imagination import generate_image`
  (code). Verified: builds correct ComfyUI workflows, splices her self-LoRA only when drawing
  herself, degrades gracefully when ComfyUI is off. Registered in her body manifest + tools doc.
- ✅ **All the planning docs are written** (consistency protocol, prompt kit, setup checklist,
  LoRA plan, the existing Design Bible + pipeline doc).
- ⛔ **The one gate:** ComfyUI isn't installed yet, and her look isn't locked. That's today.
- 🟡 **Waiting on you:** approve/tweak the proposed design locks (B1–B6) so the Design Bible is
  complete (see Phase 3 / `avatar_consistency_protocol.md` Part B).

## The path, in order

### Phase 0 — (5 min) Approve the design locks
Skim Part B of `avatar_consistency_protocol.md` and give me yes/tweak/no on the six open choices
(eyes, lower body, back, hands, pose, patches). I fold the approved ones into the Design Bible so
there are no undefined parts when we start generating. _Can happen in parallel with Phase 1._

### Phase 1 — (30–60 min, mostly download time) Stand up ComfyUI  →  `comfyui_setup_checklist.md`
Install the ComfyUI portable build OUTSIDE the workspace, grab one stylized SDXL checkpoint, set
`NOVA_COMFY_CHECKPOINT`, launch, and confirm the API answers on :8188. Watch for the VRAM note
(pin to the 3090 with `CUDA_VISIBLE_DEVICES=1` if you OOM against the LLM).
**Done when:** `python -c "from nova_imagination import comfy_status; print(comfy_status())"`
returns `{'ok': True, ...}`. Ping me here.

### Phase 2 — (a session) Lock the canonical 2D Nova  →  `avatar_consistency_protocol.md` + `prompt_kit.md`
With ComfyUI live, we generate Nova from the prompt kit, cull to the ONE image that best matches
the Bible, sample its real palette into the Bible, and save it as the canonical reference. This
is rung 2 of the consistency ladder — everything downstream conditions on it.

### Phase 3 — (a session, runs on the 3090) Train her self-LoRA  →  `nova_lora_training_plan.md`
Bootstrap a 20–40 image dataset from the canonical look, caption it, train LoRA v1 (iterate to v2
if needed), drop it in `ComfyUI\models\loras\`, set `NOVA_SELF_LORA`. **Now `as_nova: true` is a
hard lock** — her self-portraits are deterministic. This is the "100% consistent 2D" milestone.

### Phase 4 — (later) 2D → 3D  →  `avatar_pipeline_tools.md`
Use the locked Nova to produce a clean orthographic turnaround → image-to-3D (Rodin/Meshy or
local TRELLIS.2/Hunyuan3D on the 3090) → Blender + Mixamo. The resulting `.blend` becomes the
ultimate source of truth (rung 1 — exact by construction). After that, every image of her is a
render or a LoRA-locked generation, and drift is gone for good.

## The document map (what's where)
- **`Nova_Avatar_Design_Bible.md`** — the written source of truth (look, palette, rules). §7 has
  the open choices Phase 0 closes.
- **`reports/avatar_consistency_protocol.md`** — HOW we hit 100% consistency (authority ladder,
  reference-conditioning, drift gate) + the proposed design locks (Part B).
- **`avatar/prompt_kit.md`** — the verbatim identity + negative prompt, seed discipline, winning-seed log.
- **`reports/comfyui_setup_checklist.md`** — Phase 1, on your machine.
- **`reports/nova_lora_training_plan.md`** — Phase 3, the self-LoRA.
- **`reports/avatar_pipeline_tools.md`** — Phase 4, the 2D→3D tool path.
- **Faculty code:** `nova_body/nova_imagination/` · **tool wiring:** `general_tools/nova_chat/tool_router.py`
  + `clients/nova.py` · **output gallery:** `nova_art/`.

## First thing to say to me tomorrow
Either "ComfyUI's up, comfy_status is green" (→ we jump to Phase 2), or "here are my B1–B6 calls"
(→ I lock the Bible), or both. From there we hit the ground running.
