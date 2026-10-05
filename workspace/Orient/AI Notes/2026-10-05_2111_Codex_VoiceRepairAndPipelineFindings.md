<!-- @nova: Record the completed voice/controller repairs, live validation, unresolved reply latency and current operational handoff. -->
# Voice repairs and Pipeline findings
**Summary:** The separate Voice widget, compact Conversation power control and Collaboration jump-to-latest work. Real Nova replies reached Windows playback, and Cole confirmed hearing the first run. Mandatory context/audit processing still makes live conversation too slow; the cache changes did not demonstrate a speedup.

## Did
- Voice is a standard dockable/popout widget under Widgets. Manual layout save semantics remain unchanged. Conversation power is a compact button beside Users/Options, including chat-only mode. Collaboration Latest appears immediately after manual scroll beyond60px and returns to bottom.
- Repaired acknowledged voice requests expiring before a late reply; added correlated delivery/playback/suppression diagnostics and request-scoped End call cancellation.
- Installed local English Whisper large-v3-turbo CPU int8, keeping the existing VAD/capture gates. Recognition accuracy on Cole's laptop microphone remains unscored; one public22-word clip was correct with both recognizers and is not proof of an accuracy improvement.
- Voice uses the existing voice_fast register by default. Windows system speech prefers an installed English female voice when no explicit name is configured. Native synthesis selected Microsoft Zira Desktop; this remains a placeholder, not Nova's final approved voice.
- Pipeline read-attempt labels no longer imply refused reads verified anything. Added bounded opt-in provider payload/timing receipts; capture markers are now closed.
- Moved changing clock/read-budget text behind stable prompt portions without changing audit evidence/policy/parser, and added local-cache-first/thread-safe memory encoder initialization. These changes passed tests but did not establish a latency gain.

## Verified
- Gateway73 tests and frontend70 scenarios pass; controller30, transport38, diagnostics7, chat-only7 and targeted witness/cache/memory tests pass in the owning slices. See companion notes2036/2037/2038/2043/2056/2058/2105 for exact scopes rather than adding overlapping totals.
- Hidden browser checked Voice rendering, power reachability with Nova on/off, and Collaboration scroll/show/click-hide behavior. No console errors. Screenshot: Temp/voice-validation/voice-widget-final.jpg.
- First Windows audio run delivered after94.844s and began playback after96.246s; both units reported played. Cole heard it and disliked the masculine default. Second run after cache changes delivered after94.812s and began playback after96.190s, again two played units. Both audits were INCOMPLETE. The second run used the new female preference; Cole has not approved that voice.
- First measured phases: memory34.947s; generation28.677s (25.992s prompt evaluation); four audit calls30.030s. Repeat: context31.515s; generation31.377s; four audits31.355s. No speedup claim. Correct current requests reached the provider.
- Native worker startup with Whisper reached listening/recognizing. Root's intended muted control check later had an unmuted microphone amid concurrent UI use; attribution is unknown and this is not a successful sustained-mute test. Root ended the call through the widget, confirmed off and cancellation of its pending request. A new call then started from another client; root left it alone. Do not mistake this for scored natural-conversation recognition.

## Open / next
- The blocking issue for natural live voice is the foreground context and witness pipeline: roughly32k prompt tokens plus multiple serial audit calls. Relative receipt ages and hybrid-model cache checkpoints still invalidate prompt reuse. A lighter conversational context and a carefully evaluated audit scheduling policy need a deliberate next design pass; no audit bypass was introduced here.
- A third warm performance run was deferred because Cole was actively using Nova; its capture marker was closed. Do not claim warm performance was measured.
- Current detailed report: Orient/Architecture/evidence/2026-10-05-voice-repair-validation.md. Raw receipts: Temp/voice-validation/native-reply-20261005-2048.json and native-reply-20261005-2101.json; corresponding provider captures live under Temp/provider-diagnostics/.
- PyAV19 file decoding compatibility was noted in the public ASR benchmark; the microphone path supplies NumPy samples and does not use that broken file decoder.

## Operational handoff
- Reload through the controller at8765/api/nova/stop and /start, after checking active operations. A direct8799 launcher call can miss the controller transition hold and fail quiesce with409; root encountered this and recovered through the correct controller route. No forced worker kill or personal-state edit was used.
- Loaded worker PID46140 reported running_latest_code:true, Nova on, autonomy disabled. Voice was restarted from another client after root ended its check; leave the live user session alone. No further code/audio ownership remains with subagents.
