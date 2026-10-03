<!-- @nova: Record the v16 eye-layer repair, saved evidence, native export and remaining avatar quality limits. -->
# Avatar eye repair
**Summary:** v16 is saved, exported and installed. It corrects the moving skin fragments, pupil fade and jagged closed-eye remnants identified in the earlier audit; it does not establish commercial readiness.

## Did
- Worked only in `workspace/nova_body/SELF/Avatar/Live2D` and the installed Nova_FRONT_v16 VTube Studio model folder.
- Rebuilt clean lash and closed-eye artwork, continuous sclera openings, pupil sampling and blink opacity keys; restored the stationary face backing around prior eye patches.
- Remeshed both irises and both closed-eye drawables in native Cubism. Saved `rig/Nova_FRONT_v16.cmo3`, layered PSD and final runtime.
- Added `preview/eye-review-v16.html` with matching before/after poses, isolated layers, a reference overlay and a 16-second eye animation. Older review pages link to it.
- Retained WebM download and added MP4 for browser playback. WebM playback crashed the in-app preview twice; MP4 seeking, sustained playback and half speed were verified successfully afterward. Crashed tabs could not be closed through automation.
- Final checkpoint: `checkpoints/2026-10-03_131912/Nova_v16_session.zip` beneath Live2D; 211 files, 117769867 bytes, integrity passed. Includes editable source, generator inputs, rig, runtime, installed files and evidence.

## Why
- Prior source patches included skin/hair on moving lash meshes. Existing blink keys also faded the iris/pupil while the eye was still visibly open. Numeric layer-order checks alone missed these visual defects.
- This completes the scoped repair begun in `2026-10-03_1119_Codex_AvatarEyeAudit.md`; that note intentionally records an unfinished audit.

## Verified
- Final MOC SHA256: `211ffb763fd5d937fcbe260eb4219432f98178adefe14279a9f6d40ea7fa54f7`.
- Compiled-model validation passed: 137 blink samples, independent winks, 63 gaze/opening combinations, clipping/order, unchanged pupil geometry through blink, no skin/hair color in opaque lashes. Fifteen mouth shape/opening combinations preserved from v15.
- Magnified exported-model views inspected for neutral, partial/near-closed/full blink, downward and diagonal gaze, and individual layers. Reference overlay uses fixed registration; it is not pixel-identical reproduction.
- Native VTube Studio loaded v16 and on-screen slow-demo, neutral and down-gaze controls were exercised. Native screenshots use full-body framing; the enlarged frames and video are offline Core renders, not native recordings or camera tracking.
- Review layer/pose controls, reference blend, video decoding, MP4 seek and half-speed playback verified in the browser. All displayed images loaded.
- Source/runtime/install/archive hashes checked. The checkpoint SHA256 is `aa0d4156fc75f9e12b3f8d466a04b74b07d6e743541fff1f07bcec2c7e147de4`.

## Open / next
- Base face/hair artwork remains low resolution, with mixed edge softness beside cleaner eyes. Full-face repaint/detail recovery was not done.
- Full head turns, neck coverage, hair/brow/ear separation and physics, mouth/jaw quality, natural speech calibration and broader expression testing remain. Existing opening-to-Small/AA mapping is not phoneme recognition.
- Camera tracking and keyboard hotkey activation were not tested this pass. Do not describe this model as commercially ready.
- Re-run model validation and visual review after any new native export; checks are tied to the final hash above.

## For other agents
- Unrelated Nova desktop/runtime work was left alone. No Nova-owned memory/task/journal edits or architecture changes were made.
- Use the saved cmo3 to resume. Source generation requires subsequent native reimport, appropriate remeshing and export; do not assume updating a PSD updates the installed rig.
