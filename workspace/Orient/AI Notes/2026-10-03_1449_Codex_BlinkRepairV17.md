<!-- @nova: Record v17 eyelid shape repair, native source/export preservation, verification and remaining avatar limits. -->
# Nova v17 blink repair
**Summary:** Rebuilt upper-lid closure in native Cubism and repaired the viewer-left sclera gap. Saved editable source, exported and installed runtime, review evidence and a verified checkpoint. The complete avatar is still unfinished.

## Did
- All avatar changes are under `workspace/nova_body/SELF/Avatar/Live2D/`.
- Added `tooling/prepare_blink_v17.cjs`, source PSD and registration metadata. Upper and lower lashes are separate artwork; viewer-left white backing reaches beneath its upper lash.
- Saved `rig/Nova_FRONT_v17.cmo3`. Upper lashes are direct FaceWarp children with separate open/closed forms and authored deform-path curvature, continuous opacity and lash-following topology (56/58 vertices). Lower lashes follow the aperture; iris geometry remains independent.
- Exported native 4096 texture atlas and runtime v17. `tooling/package_front_v17.py` installs retained speech/expression controls and natural-speed plus slow-review blinking.
- Added v17 rendering/validation/checkpoint scripts and `preview/eye-review-v17.html`. The page shows actual exported Core animation, isolated layers, fixed-scale v16/v17 comparisons and a reference overlay.
- Installed Nova FRONT v17 in VTube Studio; v16 and earlier checkpoints preserved. The application remains open with v17 loaded; Cubism has the saved editable source.

## Why
The old blink scaled the lash assembly with the eye opening. Upper lids now change curvature over intact irises. Sclera remains independent and irises stay clipped beneath foreground lashes. This repairs the requested blink and skin wedge, without claiming a whole-avatar quality milestone or knowledge of Crelly's private rig.

## Verified
- Final MOC SHA256: b978f5020ba7158464ed01fcc89475395be7214023c7f18c01f574c692f21aa3.
- Compiled checks: 137 blink samples, independent winks, 63 gaze/opening combinations, draw order/masks, stable pupil geometry, no skin/hair colors in opaque lash pixels. Non-affine upper-lid curvature confirmed by >13-pixel residual from best affine fit on each side. Fifteen existing mouth combinations retained.
- Inspected neutral, partial, near-closed, closed and gaze extremes at high magnification. Rejected an earlier kinked export and remeshed both upper lashes before final export.
- Browser video playback, seeking and final mid-blink/closed views inspected. Videos are offline renders of the exact exported runtime, not native recordings or camera-tracking tests.
- Native VTS loaded v17. Its application log confirms the eye-review and downward-gaze motion triggers; partial lid motion was visible. Full native sequence was not captured at high magnification. Narrow log excerpt and loading screenshot saved in preview/v17. Keyboard activation, camera tracking and speech calibration are not established.
- Runtime/installed referenced assets match. Checkpoint archive has 216 entries, SHA256 verified per entry, integrity passed.

## Open / next
- Original 360x335 face crop still limits surrounding skin/hair resolution; edge softness is inconsistent with cleaner eyes. This is not pixel-identical reference reconstruction.
- Commercial quality remains unestablished. Head turns/neck coverage, hair/brow/ear separation and physics, mouth/jaw polish, speech calibration and broader expression testing remain.
- Source generator needs native Cubism reimport/remesh/export after artwork changes. Use the saved v17 cmo3 as the editable rig checkpoint.
- Review: http://127.0.0.1:8891/Live2D/preview/eye-review-v17.html
- Portable package: runtime/Nova_FRONT_v17_VTube_Studio.zip
- Session checkpoint: checkpoints/2026-10-03_144816/Nova_v17_session.zip
- Archive SHA256: 38861285804d4d2f14a2ff046cd959deb580e3ea6d9b47bb5f3b81bb4c485288.

## For Cole / next agent
The review page is left open. On-screen 1/F6 is the configured 16-second natural blink, slow closure and gaze review. Keep source, exported-render verification and native tracking claims separate. No Nova architecture/state or sealed model storage was changed.
