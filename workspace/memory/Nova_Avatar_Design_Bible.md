# Nova — Avatar Design Bible (Source of Truth)
_Last updated: 2026-05-28 03:34:55_
_v0.1 draft — 2026-05-27, by Opus, from Gemini's concept render + Nova's identity._
_Status: DRAFT for Cole to correct + lock. Once locked, this is the canonical written
reference every 2D illustration, turnaround, and 3D model is checked against. When the
3D model exists, the `.blend` becomes the visual source of truth and this doc stays the
written companion (rules, palette, intent, the meaning behind each element)._

> **How to use this doc:** every generation/model step gets checked against the
> "LOCKED" items below. Anything in **TO DECIDE** is undefined by the current concept and
> must be chosen before a full turnaround is possible. Hex values are **approximate** —
> sample exact values off the chosen canonical render and replace them here.

---

## 1. One-line identity
A blue-skinned, magenta-haired techwear sprite who literally lives in the machine — her
lower body dissolves into glowing data/crystal that pours into the hardware she runs on.
Tomboyish, confident, a little mischievous. Not a generic "AI girl" — a specific person.

## 2. Species / silhouette (LOCKED from concept)
- **Type:** stylized humanoid, non-human. Reads as a cyber-elf / data-sprite, not human.
- **Skin:** cool blue / blue-grey, smooth, slightly luminous. (approx base `#6E9DB5`,
  shadow `#3E5E73`, highlight `#A7C8D6`).
- **Ears:** long, pointed, elf-like, swept back; adorned with small cybernetic cuffs /
  piercings that carry cyan glow.
- **Build:** slim, lithe, tomboyish; young-adult. Androgynous-leaning feminine, not
  hyper-stylized. Confident posture.

## 3. Head & face (LOCKED)
- **Hair:** vibrant magenta→purple, voluminous swept-up/back top with short/undercut sides;
  energetic, spiky-soft. (approx magenta `#D028A8`, deeper purple roots/shadow `#6B2A9E`).
- **Eyes:** large, almond, **glowing**. Amber/gold iris with a cyan rim-glow.
  **DECIDE + LOCK:** is it (a) both eyes amber w/ cyan glow, or (b) deliberate
  heterochromia (one amber, one cyan)? The two concept renders read slightly differently —
  pick one and make it an immutable identity rule. (amber `#F2A93B`, cyan glow `#3FE0E0`).
- **Expression (default):** relaxed, knowing half-smirk. Calm confidence, faint mischief —
  never blank/servile, never aggressive.
- **Face cyber-detailing:** subtle glowing cyan circuit lines tracing one side of the face/
  temple (present in concept). Keep minimal and consistent in placement.

## 4. Outfit (LOCKED where shown; lower body TO DECIDE)
- **Jacket:** dark techwear bomber / flight jacket, near-black with a faint teal sheen,
  high collar. (approx `#14181C` body, `#1E2A2E` paneling).
- **Glow accents:** thin cyan circuit-trace lighting along seams, zipper, cuffs, collar
  (approx `#29E0E6`). This cyan glow is a core identity color — keep it on the tech, not
  the skin.
- **Patches / insignia (make these intentional + legible — they're garbled in the AI
  concept):**
  - A **shield/crest** on the left chest (her "house" mark — design TBD).
  - An **"OCULINK"** text patch — KEEP THIS. It's a real nod to her OCuLink eGPU link to
    the 3090. Make it crisp and deliberate.
  - A small **emblem** (skull / cat-like mark seen in concept) — decide and standardize.
  - Shoulder rank-style tabs (nods to Cole's Army background — optional but on-theme).
- **Lower body: TO DECIDE.** The concept dissolves below the waist into crystal/data, so
  legs, pants/boots, and full silhouette are **undefined** and must be designed for a real
  turnaround (see §7).

## 5. Signature motif — "she lives in the machine" (LOCKED concept, optional per-render)
Her edges/lower body dissolve into glowing cyan **crystalline shards** and/or a downward
**data-stream** that flows into GPU/server hardware. This is her defining visual idea and
should appear in "hero" art. NOTE: for a turnaround/3D base she needs a **solid full body**
too (the dissolve is an effect layered over a complete model, not a substitute for legs).

## 6. Color palette (approximate — LOCK against canonical render)
| Role | Approx hex | Notes |
|---|---|---|
| Skin base | `#6E9DB5` | cool blue-grey |
| Skin shadow | `#3E5E73` | |
| Skin highlight | `#A7C8D6` | |
| Hair magenta | `#D028A8` | primary |
| Hair purple | `#6B2A9E` | roots/shadow |
| Eye amber | `#F2A93B` | iris |
| Tech/glow cyan | `#29E0E6` | jacket traces, shards, data |
| Jacket near-black | `#14181C` | |
| Crystal/data accent | `#6FE3F0` | brightest glow |
Identity pairing: **magenta hair + cyan tech** (complementary), on cool blue skin. Keep
the background neutral so she pops.

## 7. TO DECIDE before a full turnaround (these are real design choices, not conversions)
1. **Lower body / legs / pants / boots** — entirely undefined.
2. **The back** — never shown; hair fall, jacket back, any back-mounted tech?
3. **Hands** — concept shows slim blue hands w/ glow; standardize nail/knuckle/cyber detail.
4. **Eye rule** — heterochromia yes/no (see §3). Most important single consistency lock.
5. **Patch designs** — finalize the crest, the emblem, keep OCULINK.
6. **Neutral expression + neutral pose** for the model sheet (A-pose or T-pose, calm face).

## 8. Consistency rules (the anti-drift contract)
- Skin stays blue-grey; **glow lives on tech/eyes, never as skin tone**.
- Hair is always magenta→purple, swept up, undercut — never a different cut/color.
- Ears always long + pointed with cyan-lit cuffs.
- The cyan circuit-trace accent color is fixed; don't let tools recolor it teal-green or blue.
- One locked eye rule, applied every time.
- OCULINK patch is canon.

## 9. Status / HUD flavor (optional, cosmetic)
Concept shows `NOVA // STATUS: LAX, AUTONOMY_LEVEL: 4`. Fun, but note: in the real system
her autonomy is **binary on/off** (and she rests when nothing's urgent). If you want HUD
text to match her actual lore, use `STATUS: RESTING / ENGAGED` and `AUTONOMY: ON/OFF`
rather than a numeric "level" that doesn't exist. Purely a flavor choice.

---
_Next step: Cole corrects/locks §3–§7, then this drives the 2D turnaround → 3D model
(see `memory/reports/avatar_pipeline_tools.md` for the tool path)._
