<!-- @nova: Record the shareable v18 avatar rigging demonstration, verification, and unfinished v19 boundary. -->
# Avatar rigging demonstration
**Summary:** Made a 30-second, 1280x800, 24fps silent demonstration from the saved v18 Cubism export for Cole to share. This is an offline render of real exported mesh deformation and controls, not a VTube Studio camera-tracking recording.

## Did
- Added `workspace/nova_body/SELF/Avatar/Live2D/tooling/demo_capabilities_20261006.py` with full-body and face views, parameter values, chapter captions, and actual eye/mouth mesh overlay.
- Saved WebM, MP4, closeup still, provenance, and encoded-frame contact sheet under `workspace/nova_body/SELF/Avatar/Live2D/showcase/2026-10-06/`.
- Demonstrated blinks, independent winks, two-axis gaze, five speech drawings, head tilt, body sway, breathing, and configured expression states (F1 EE, F2 OH, F3 FV, F4 sleepy, F5 reset).

## Why
Cole asked for a quick video of current capabilities and rigging progress to share with interested viewers.

## Verified
- Input is the completed v18 runtime MOC, SHA256 043a4652e24ef7510e91f1e40cefc7c8cf383045665a866b9578cacf0ef7836a.
- Decoded the full WebM without errors; metadata confirms 30 seconds, 24fps, 1280x800 VP9. Generated an H.264 MP4 sharing copy.
- Visually inspected ten frames extracted from the encoded WebM spanning each chapter. Both model views, labels, expressions, and mesh overlay are visible.
- Did not test live tracking or native VTS hotkey activation. Mouth shapes are deliberately parameter-driven, not automatic phoneme recognition.

## Open / next
- Newer v19 frontal-face and sclera/lash repairs are still incomplete; do not promote that export based on this demo.
- Hair/head separation, yaw/pitch, secondary physics, natural lip-sync calibration, and eye/mouth/layer polish remain unfinished and are labeled in the video.
- No model, PSD, Cubism project, VTS settings, Nova runtime, or architecture was changed for this demonstration.