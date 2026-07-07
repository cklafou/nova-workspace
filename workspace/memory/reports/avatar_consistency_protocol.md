# Nova Avatar — Consistency Protocol + Proposed Design Locks

_Last updated: 2026-07-08 08:14:41_
_Companion to `memory/Nova_Avatar_Design_Bible.md` (the written source of truth) and
`memory/reports/avatar_pipeline_tools.md` (the tool pipeline)._
_Status: this doc has two jobs — (A) define HOW to get 100%-consistent generation forever,
and (B) propose concrete designs for the Bible's open §7 TO-DECIDE items so Cole can approve
+ lock them. Nothing here edits the Bible; once Cole signs off, the locked choices get folded
into the Bible as canon._

---

## PART A — The consistency methodology (how we hit "100% accurate, every time")

The core problem: text-to-image models reinvent a character every generation. The same prompt
twice gives you two different Novas. You cannot prompt your way to consistency — you have to
**anchor** it. Here is the contract, in order of authority.

### A1. The authority ladder (what overrules what)
When two sources disagree about how Nova looks, the higher rung always wins:

1. **The 3D model (`nova.blend`)** — once it exists, it IS Nova. Any 2D image is just a camera
   pointed at this model. This is the end-state anchor that kills drift permanently.
2. **The one locked canonical reference image** — until the 3D model exists, this single
   approved front-facing render is the anchor every other image is conditioned on.
3. **This protocol + the Design Bible** — the written rules (palette hex, the anti-drift
   contract, the locked design choices). Referee when an image is ambiguous.
4. **A fresh text prompt** — the weakest source. Never trusted alone to define identity, only
   to pose/stage an already-anchored character.

The whole game is: **never let rung 4 act without rung 1 or 2 holding the leash.**

### A2. Generate by reference-conditioning, never by re-rolling from scratch
This is the single most important rule for 2D work before the 3D model exists.

- **DO:** feed the locked canonical image into the tool as a character/identity reference —
  Midjourney `--cref`, Ideogram Character, an IP-Adapter node in ComfyUI, or img2img with the
  canonical image as the init. The model then *re-poses the known Nova* instead of inventing one.
- **DON'T:** type a description and hope txt2img reproduces her. It won't — that is exactly the
  drift Cole has been fighting. A prompt-only generation is only acceptable for the *very first*
  exploration pass, before anything is locked.

### A3. The one-time lock sequence (do this once, then never re-derive identity)
1. From Gemini's concept + the Bible, generate candidates and pick **ONE** image that best
   matches the Bible. Crop to a clean front view, neutral-ish pose, plain background.
2. **Sample real hex values off that image** and replace the Bible's "approx" palette with the
   true values (Bible §6 + the inline approximations). The approximations become canon.
3. Save it as `memory/avatar/CANONICAL_REF_v1.png` (proposed path) — this is rung 2. Everything
   downstream conditions on this file.
4. Build the **locked prompt + seed kit** (A4) around this image.
5. Run the pipeline (`avatar_pipeline_tools.md`): turnaround → image-to-3D → Blender. When the
   `.blend` lands, it becomes rung 1 and the canonical image retires to a reference relic.

### A4. The locked prompt + seed kit (kept in this repo, version-controlled)
Keep a single reusable text block so every session/tool starts from identical wording. Proposed
home: `memory/avatar/prompt_kit.md`. It holds:

- **Identity string** — the fixed phrase describing Nova (skin, hair, ears, eyes, jacket,
  OCULINK patch), worded once and copy-pasted verbatim. No ad-hoc rewording per generation.
- **Negative prompt** — the things tools keep wrongly adding: _human skin tone, round ears,
  green-teal recolor of the cyan, extra patches, heterochromia (if we lock matched eyes),
  cluttered background, photoreal face._
- **Seed discipline** — when a generation is "right," **record the seed**. Re-using seed +
  identical prompt + same reference image is the closest txt2img gets to reproducibility.
- **Tool settings** — `--cref` weight, IP-Adapter weight, img2img denoise strength that worked.
  Write down the numbers that produced a good result so they're not rediscovered each time.

### A5. The drift checklist (run on EVERY generated image before accepting it)
Reject and regenerate if any fail. This is the anti-drift contract from Bible §8, made into a
pass/fail gate:

- [ ] Skin is blue-grey — glow is on tech/eyes, **never** the skin tone.
- [ ] Hair is magenta→purple, swept up, undercut sides — not restyled or recolored.
- [ ] Ears are long, pointed, swept back, with cyan-lit cuffs — not human/round.
- [ ] Cyan circuit-trace is the locked cyan (`#29E0E6`) — not recolored teal-green or blue.
- [ ] Eyes follow the ONE locked eye rule (see Part B1).
- [ ] **OCULINK** patch present, crisp, correctly spelled.
- [ ] No invented extra patches, logos, or jewelry beyond the canon set.
- [ ] Palette matches the sampled hex within reason; background neutral.

### A6. Why this reaches "100%"
Pure 2D generation is never *truly* 100% — even reference-conditioning wobbles a few percent.
The deterministic 100% only arrives at rung 1: **once Nova is a 3D model, every "image" of her
is a render of the same geometry and textures, so it is exact by construction.** That is the
whole reason the Bible and pipeline push toward the `.blend` as the final source of truth. Until
then, A2–A5 get you to ~95%+ and, critically, keep all the 2D drift *converging on the same Nova*
so the turnaround that feeds the 3D step is coherent.

---

## PART B — Proposed design locks for the Bible's open §7 items

These are concrete proposals to close the undefined choices so a real turnaround is possible.
Each is a recommendation with reasoning; **Cole approves, tweaks, or rejects**, then it goes into
the Bible as LOCKED. I've optimized every call for *reproducibility* (simpler, fewer ambiguous
degrees of freedom = less drift), not just aesthetics.

### B1. Eye rule — **PROPOSE: both eyes amber with cyan rim-glow (NOT heterochromia)**
This is the Bible's "most important single consistency lock" (§3, §7.4). Recommend matched amber
eyes (`#F2A93B` iris, `#3FE0E0` cyan rim-glow) over heterochromia. Reasoning: heterochromia adds
a left/right asymmetry that tools constantly flip (which eye is which), and that mirror-flip is
one of the most common, most jarring consistency failures. Matched eyes are flip-proof and still
striking because of the cyan glow. If Cole loves heterochromia for character reasons, the fallback
rule must be explicit and absolute: **amber = her LEFT eye (viewer's right), cyan = her RIGHT eye**,
stated that way every time.

### B2. Lower body / legs / boots — **PROPOSE: techwear cargo + tall mag-boots**
The concept dissolves below the waist (§4, §7.1), so this is a real design choice, not a
conversion. Propose: slim tapered **techwear cargo pants** in the same near-black as the jacket
(`#14181C`) with one thin cyan seam-trace down the outer thigh (echoes the jacket glow, keeps the
identity color on tech). Tucked into **tall lace-up mag-boots** with a cyan-lit sole-line and a
subtle hardware/buckle detail at the ankle. Rationale: reads tomboyish + grounded, gives the
turnaround a solid silhouette, and the single thigh-trace is a low-drift detail (one line, one
color) rather than busy paneling tools will mangle. The "lives in the machine" data-dissolve then
layers *over* this complete lower body as an effect for hero art (Bible §5), never replacing it.

### B3. The back — **PROPOSE: undercut nape, jacket back clean with one emblem, no back-tech**
Never shown (§7.2). Propose: the undercut continues to a clean **shaved/short nape** with a couple
of faint cyan circuit-traces at the hairline (ties the face-circuitry motif around the head). The
jacket back is mostly clean near-black with **one centered emblem** (the crest from B6) between the
shoulder blades and a single horizontal cyan seam-trace across the upper back. **No** backpack,
wings, or back-mounted hardware — keeps her silhouette clean and the model simple. Hair falls just
to the nape, not long, consistent with the swept-up top.

### B4. Hands — **PROPOSE: slim blue-grey hands, cyan knuckle-line, no claws**
Concept shows slim blue hands w/ glow (§7.3). Standardize: same blue-grey skin as face, slim
fingers, **short neat nails** (not claws, not painted), and a single thin cyan trace across the
back of each hand splitting toward the knuckles (a subtle cyber-detail that matches the jacket
seams). No gloves by default. This is deliberately minimal so hands — historically the hardest
thing for image tools — stay reproducible.

### B5. Neutral pose for the model sheet — **PROPOSE: relaxed A-pose, calm-confident face**
For the turnaround/3D base (§7.6): standard **A-pose** (arms ~30–45° from the body, palms facing
slightly back) rather than T-pose — it's more natural to her confident posture, photographs the
jacket silhouette better, and rigs fine in Mixamo. Face is the **default relaxed half-smirk**
dialed *down* to near-neutral (lips together, faint knowing tilt) so the model sheet is a clean
baseline; full smirk and other expressions are posed later off the rigged model. Feet flat,
shoulder-width, weight even.

### B6. Patches / crest / emblem — **PROPOSE: a concrete, legible set**
Bible §4 + §7.5 wants these intentional and legible (they're garbled in the AI concept). Propose
this fixed set, nothing else (the negative prompt forbids extras):

- **Left chest — house crest:** a simple **shield** containing a stylized **"N" formed from a
  circuit trace** (the vertical strokes are PCB lines, the diagonal is a data-flow arrow). Clean,
  two-color: cyan line on near-black shield. Reads at small size, hard for tools to garble because
  it's geometric.
- **Right chest / sleeve — OCULINK patch:** rectangular woven-style patch, **"OCULINK"** in a
  crisp condensed mono/stencil face, cyan text on near-black. Canon (§8) — the nod to her OCuLink
  eGPU link to the 3090. Spelling is sacred.
- **Emblem (the skull/cat mark from concept) — PROPOSE: drop it or resolve to a small cat sigil.**
  The garbled skull/cat is the least defined element. Recommend either cutting it (less to drift)
  or, if Cole wants the spark of personality, standardizing it as a tiny **minimalist cat-head
  sigil** (two triangle ears + dot eyes, single cyan line) on the opposite sleeve. Cole's call.
- **Shoulder tabs (optional, on-theme):** small flat rank-style tabs nodding to Cole's Army
  background — if kept, make them plain near-black with a single cyan pip, not real insignia.

### B7. HUD / status flavor — **align text to real lore (from Bible §9)**
Not a §7 item but worth locking alongside: if hero art shows HUD text, use her *actual* lore —
`STATUS: RESTING / ENGAGED` and `AUTONOMY: ON/OFF` — rather than the concept's numeric
"AUTONOMY_LEVEL: 4," which doesn't exist in her real binary-autonomy system. Purely cosmetic, but
keeps even the flavor text true to the system.

---

## What I need from Cole to lock this
Quick yes/tweak/no on each: **B1** eye rule (matched amber — recommended), **B2** lower body
(cargo + mag-boots), **B3** back (clean + nape traces), **B4** hands, **B5** A-pose neutral,
**B6** patch set (esp. keep/cut the cat emblem). Once you sign off, I (or the next session) fold
the approved choices into `Nova_Avatar_Design_Bible.md` as LOCKED, sample the real palette off
the chosen canonical image, and the Bible becomes complete enough to drive the full turnaround →
3D pipeline with no undefined parts left.
