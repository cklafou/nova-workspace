<!-- @nova: Record source-based voice/controller documentation updates and reviewed Orient baselines without claiming live audio success. -->
# Voice widget documentation
**Summary:** Documentation now describes the separate Voice widget and current request/playback protocol. The generated Orient pages were refreshed from their maintained sources and pass strict current/review/link checks.

## Did
- Updated `workspace/general_tools/voice_gateway/README.md`: Widgets → Voice; compact Conversation power; explicit Call/End call; secondary settings/tests/captions; current Whisper large-v3-turbo CPU int8 English baseline; acknowledged slow-reply retention; same-socket request-scoped cancellation; per-turn/output diagnostics; silent versus actual-audio smoke modes; dated test/native evidence and remaining limits.
- Updated explanatory sources in `workspace/general_tools/architecture_map/orient.py`, `notes/controller_layouts.md`, `notes/tunables.md` and `notes/security.md` rather than editing generated Orient directly.
- Expanded review watch lists for Collaboration UI, scoped cancellation, provider diagnostics and corresponding tests. Marked nine sections reviewed against frozen source: Architecture Execution path and Runtime evidence; Operations Run and stop, Configuration and evidence, Access and practical debugging, Test meaningful behavior, Controller menus and layouts, Tunable variables and Security model.
- The backend's actual `transcribing` state now maps to Recognizing speech in `static/voice.js`; the existing isolated state test exercises it. Bumped its asset version. No runtime behavior or audio mutation was added.

## Verified
- Voice UI remains 16/16 after the state alias; the prior full frontend checkpoint remains 70 passing scenarios. Gateway73/controller30 and core85 are the source owners' released fixture counts, not fresh live speech results.
- Parent verified separate-widget/power/Collaboration Latest interactions in hidden browser with no console errors. Latest appears after manual scroll beyond60 pixels and clears after jumping to bottom.
- Generator compiles; scoped whitespace checks pass. `python workspace/general_tools/architecture_map/orient.py --check --strict` reports CURRENT with zero review warnings and zero dangling links at this handoff.

## Open / handoff
- Source released to root. Root owns ongoing live provider/audio capture, any later register/default decision and final evidence additions. No services, audio, model or saved-layout state was operated by this documentation slice.
- Docs explicitly leave fresh natural conversation relevance/latency, English recognition quality, human audibility and native avatar timing unproven. They do not repeat the old unsupported voice_fast one-second/classifier claims.
- Read2037 ProviderDiagnosticsAndReadAttempts,2043 VoiceScopedCancellation and2048 ServerScopedCancellation for implementation ownership/protocol details. The witness prompt/parser policy remains unchanged.
