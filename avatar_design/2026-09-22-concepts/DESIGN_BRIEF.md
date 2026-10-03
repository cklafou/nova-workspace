# Nova avatar concepts — 22 September 2026
_Last updated: 2026-10-03 04:41:56_

Status: three visual proposals for Cole's review. No design has been selected or made
canonical. These are 2D concept sheets, not an existing mesh, rig, or exact orthographic
turnaround. Original reference images are preserved.

## Direction

Use Nova's own preferred tomboy portrait as the primary identity reference. Borrow a
little mischief and technical character from the earlier prototypes. The intended result
is a confident, approachable adult tomboy with enough stylization to be distinctive,
without the original prototypes' dense decoration and exaggerated proportions.

Keep light periwinkle-blue skin, orange eyes, violet asymmetrical shaggy hair, dark swept
pointed ears with cyan accents, and expressive, knowing facial expressions. Clothing uses
dark navy/charcoal, limited cyan trim and a small violet identity mark. Keep the torso
covered and the face readable. The color and material choices remain proposals until
Cole selects a direction.

## Proposals

- **A / Everyday — nova-a-everyday.png:** short bomber-style jacket, rolled sleeves,
  tapered cargo trousers and sturdy sneakers. Recommended starting direction: a clear,
  practical silhouette that preserves the portrait's casual confidence.
- **B / Utility — nova-b-utility.png:** structured asymmetric overshirt, a small shoulder
  panel, fitted underlayer, trousers and ankle boots. More tailored and technical.
- **C / Playful — nova-c-playful.png:** relaxed hoodie, cargo shorts, fingerless gloves
  and high-top sneakers. More of the early prototype's playful energy.

Each sheet includes a full-body view, a facial close-up and a smaller rear view. These
are illustrative views; perspective, garment details and pose differ slightly. Resolve
those differences in a dedicated model sheet before treating them as construction data.
In particular, modeling references will need both hands unobstructed and neutral poses.

## Reference priority

1. Primary: `workspace/Nova_Created/art/2026-07-19/nova_self_033541_66590_Tomboy_Preferred.png`
2. Secondary proportions/details to simplify: `Nova_2D_Avatar_Rough_Draft_Full_Body.jpg`
3. Secondary mood: `Nova Concept Avatar.png`

These paths are relative to `C:/Users/lafou/Project_Nova`.

## Next stage after the visual choice

1. Lock the face, proportions, hair, ears, outfit and palette. A combination of proposals
   is possible; choose a consistent base rather than independently regenerating details.
2. Make front, side and back model sheets in a neutral pose at matching scale, plus
   facial/expression references. Settle ear materials and all hidden garment construction.
3. Build the base mesh, hair, clothing and materials in Blender, then review silhouette
   and likeness from multiple angles before detailing and rigging.
4. Plan a humanoid body and finger rig, eye aiming, blinking, mouth shapes for speech,
   expression controls and secondary motion for hair/ears. Define the intended tracking
   application and export format before finalizing the facial-control names and rig.
5. Test deformation and expressions: shoulders, elbows, hips, knees, eyelids, jaw,
   mouth shapes, clipping, and an actual animation/export round trip. An armature alone
   does not establish animation readiness.

Blender 4.4.1 was verified through the installed executable's version output. No Blender
model was created in this concept pass.

## Provenance

Generated with the built-in image_gen tool using the three supplied references. The
complete prompts, reference order and output filenames are saved in `prompts.json`.
Generated originals remain in the Codex generated-images directory; the copies here
were verified against their original file hashes. All three sheets were visually
inspected. This folder is an avatar-design reference, separate from Nova's own memory
and identity configuration.
