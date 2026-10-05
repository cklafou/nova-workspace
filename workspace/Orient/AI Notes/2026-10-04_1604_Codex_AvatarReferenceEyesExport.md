<!-- @nova: Record the measured reference-eye correction, saved native export, evidence boundaries and remaining avatar work. -->
# Reference eyes fitted to the frontal face
**Summary:** Corrected the eye artwork against the actual A3 reference and restored pupil placement measured from the approved frontal avatar. Saved and exported an eyes-only v18 revision; this is not a finished whole-face repaint or commercial-ready avatar.

## Did
- Work is under `workspace/nova_body/SELF/Avatar/Live2D/`.
- The supplied A3 clipboard sheet is identical to `Avatar/Nova_Avatar_Reference.png`; retained a permanent copy at `art/v18/Nova_A3_Eye_Reference.png`.
- `tooling/prepare_reference_iris_v18.cjs` creates the measured oval pupil, thin inner ring and sampled amber palette. `art/v18/reference-iris.svg` is editable. Earlier generated round-eye/head drafts remain excluded; see `art/v18/art-status.json`.
- Restored frontal pupil centers to model R(948.86,313.43), L(1088.44,318.44), with about 2 model-pixel measurement uncertainty. Earlier nominal spacing was roughly 5% too wide. The nose, mouth, jaw and surrounding source layers remain unchanged.
- Final source: `source/Nova_FRONT_v18_eyes.psd`, SHA256 cd6488096a12199cd3f2de8add8a8c3d2694590a8fc9bf36fc5f00c267dfe2cd.
- Native Cubism: reimported the PSD into a v17 copy, expanded IrisL mesh to cover shifted art, rebuilt the 4096 atlas, saved `rig/Nova_FRONT_v18_eyes.cmo3`, and exported `runtime/Nova_FRONT_v18_eyes/`.
- Editable CMO3 SHA256 e483120285f072883081766fb59cf43b9099fad21a8629ec6e5a42b3a0ac93cf.
- MOC SHA256 043a4652e24ef7510e91f1e40cefc7c8cf383045665a866b9578cacf0ef7836a.
- `tooling/package_reference_eyes_v18.py --install` retained existing controls and installed a separate model named Nova - reference eyes v18; v17 remains intact.
- `preview/reference-eyes-v18.html` contains the A3 crop, compiled full face, fixed-coordinate frontal overlay, enlarged source comparison, and compiled blink/gaze stills. Browser evidence is in `preview/v18/browser-review.jpg` and `browser-face-comparison.jpg`.

## Why
The requested correction depends on the whole face and its eye openings, not an independently invented iris. A3 supplies the internal eye design; the already-approved frontal image supplies placement. CALM is tilted and in perspective, so copying its far-eye compression into both frontal eyes would be incorrect. Hidden upper iris arcs are inferred; literal pixel identity is not established.

## Verified
- Independent source audit: all 50 non-iris layers remain identical to v17. Source changes stay within sclera and do not overwrite opaque lashes.
- Actual exported Core checks: 97 poses, including 63 combined blink/gaze poses. Non-iris geometry difference from v17 is 0; parameter inventory, opacity, iris motion, sclera clipping and foreground lash ordering pass.
- One 4096x4096 atlas, texture index 0 for all 22 drawables, matching the offline renderer assumptions.
- Visually inspected exported full face, fixed-coordinate overlay, seven blink states, and nine gaze directions. Browser overlay and pose buttons verified.
- VTube Studio was launched but closed during startup before the model could be displayed; its Player.log contains initialization/quit errors. No native v18 VTS display or camera-tracking claim. Native Cubism and exported Core rendering are established.
- v17 MOC still hashes b978f5020ba7158464ed01fcc89475395be7214023c7f18c01f574c692f21aa3.

## Open / next
Skin and hair remain softer than the replacement facial features. The existing head is still flattened; Angle X/Y do not implement head turns. Separate hair/ear/brow layers, coherent high-resolution facial art, mouth/jaw polish, physics and native tracking remain. Do not integrate `source/Nova_FRONT_v18.psd`, the rejected full-head draft, as if it were the accepted eyes-only source.

## For Codex / Claude / Cole
Resume from `rig/Nova_FRONT_v18_eyes.cmo3` and `SESSION_CHECKPOINT.txt`. `tooling/checkpoint_reference_eyes_v18.py` records the new portable package and checkpoint with verified manifest hashes. Preserve v17 and existing checkpoints. No Nova runtime architecture, personal state or other agent-owned controller files changed; avatar art remains gitignored by Cole's choice.
