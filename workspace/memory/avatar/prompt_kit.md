# Nova — Locked Prompt + Seed Kit
_Last updated: 2026-07-08 08:14:41_

_Last updated: 2026-05-27, by Opus. The reusable text every Nova generation starts from, so
wording never drifts session to session. Referenced by `avatar_consistency_protocol.md` (rung 4
of the authority ladder). Mirrors the constants baked into `nova_body/nova_imagination/imagination.py`
(`NOVA_IDENTITY_PROMPT` / `NOVA_NEGATIVE`) — keep the two in sync; if you tune one, tune both._

> Status: v0 working draft. The identity string below reflects the Design Bible's LOCKED items
> plus my proposed §7 locks (eyes, lower body, etc.) — tighten it once Cole approves those and
> once we've sampled the real palette off the canonical reference image.

---

## 1. Identity string (positive prompt — paste verbatim, don't reword per generation)
Use this as the leading block whenever Nova herself is in frame. Append the scene/pose after it.

```
nova, a stylized non-human cyber-elf data-sprite, cool blue-grey luminous skin,
long pointed swept-back ears with small cyan-lit cybernetic cuffs,
voluminous magenta-to-purple swept-up hair with undercut sides,
large almond amber eyes with cyan rim-glow, calm knowing half-smirk,
dark near-black techwear bomber jacket, high collar, thin cyan circuit-trace glow on the seams,
OCULINK shoulder patch, slim athletic build, confident posture
```

Append the moment after it, e.g.:
`..., standing on a rain-wet rooftop at dusk, neon reflections, cinematic lighting`

## 2. Negative prompt (the drift-killers — paste verbatim)
These are the failures tools repeatedly introduce; forbidding them up front saves regenerations.

```
human skin tone, peach skin, round human ears, recolored teal-green glow, blue glow on skin,
heterochromia, mismatched eyes, extra logos, extra patches, garbled text, cluttered background,
photorealistic face, deformed hands, extra fingers, lowres, watermark, signature
```

## 3. Seed discipline
- When a generation comes out RIGHT, **write the seed down** (the faculty returns it in every
  result, and it's encoded in the saved filename: `nova_self_HHMMSS_<seed%100000>.png`).
- Re-using the same seed + identical prompt + same checkpoint reproduces (near-)identically — the
  closest txt2img gets to determinism. Log winning seeds in §6 below.
- For variations on a winning look, hold the seed and change one thing at a time (pose OR
  lighting OR camera), so you can tell what moved.

## 4. Tool settings that worked (fill in as we tune)
| Setting | Value | Notes |
|---|---|---|
| Base checkpoint | _(set NOVA_COMFY_CHECKPOINT)_ | the stylized SDXL model chosen at setup |
| Resolution | 1024 x 1024 | SDXL-native; faculty default |
| Steps | 30 | faculty default; raise to ~40 for hero art |
| CFG | 6.5 | faculty default; lower = looser, higher = more literal |
| Sampler / scheduler | euler / normal | faculty default; try dpmpp_2m / karras for detail |
| Self-LoRA strength | 0.85 | `NOVA_SELF_LORA_STRENGTH`; tune 0.7–1.0 once trained |

## 5. The accept/reject gate (run before keeping any image)
Quick version of the drift checklist (full list in `avatar_consistency_protocol.md` §A5):
blue-grey skin · magenta→purple swept-up hair · long pointed cyan-cuffed ears · locked cyan
(`#29E0E6`) on tech only · ONE eye rule · OCULINK patch present + spelled right · no invented
extras · neutral background. Any miss → reject, regenerate.

## 6. Winning seeds log (append as we find keepers)
_None yet — fill in once ComfyUI is up and we start the canonical-lock pass._
| Date | Seed | Prompt note | File | Use |
|---|---|---|---|---|
| | | | | |
