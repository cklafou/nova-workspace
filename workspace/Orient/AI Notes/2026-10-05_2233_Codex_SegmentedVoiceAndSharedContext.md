<!-- @nova: Record committed segment transport, audible-queue controls, saved audit attribution and body-owned conversation formatting. -->
# Segmented voice and shared conversation context

**Summary:** The gateway and Conversation renderer accept ordered delivered parts while body work continues. Conversation formatting now lives in the body, with a compatible face wrapper. These are source/fixture results; Nova, microphone, playback and services were not operated in this slice.

## Did
- `workspace/general_tools/voice_gateway/{turns,nova_link,speech,control_worker,gateway}.py`: accept exact acknowledged request pairs under stable response/run/turn IDs; validate each segment against its recorded input revision/audit, reject gaps/duplicates and keep bindings through terminal closure. The final aggregate cannot replay segmented speech. Bound earlier inputs remain correlated beyond the delay threshold.
- New input retains committed queued speech. Full-duplex barge-in cuts current audio and pauses pending units through capture/recognition; explicit End/Stop/output mute flushes. Closing prevents held or late synthesized audio from starting, without claiming to cancel the underlying computation.
- `nova_chat/static/index.html` grows one reply with part/audit status. Reloaded transcript rows retain saved part/audit attribution. Cross-session frames cannot create foreign bubbles; the existing server session-switch path still cancels its active task.
- `nova_chat/transcript.py` accepts copied, whitelisted response metadata. `nova_body/nova_runtime/conversation_context.py` contains the faithful shared clock/author/image formatter; the face delegates and preserves its clock hook. Bridge integrated the helper for headless human attention.
- Source explanations in `architecture_map/orient.py`, `notes/controller_layouts.md` and `voice_gateway/README.md` cover body work ownership, natural-boundary attention, preserved budgets/evidence revisions, captured headless input coverage and committed-part behavior. New review watch paths were added; existing review baselines were not edited.

## Verified
- Full fake gateway suite: 107 run, 106 passed, one existing skip. This includes 11 segment/queue cases.
- Extracted frontend checks: 29/29, including three growing-reply/history cases; no live browser/audio in this slice.
- Shared formatter parity: 5/5; temporary transcript metadata: 2/2; existing prompt-cache fixtures: 5/5.
- Independent current work-owner checks: 17/17; natural-step boundary checks: 11/11. Expected injected error traces exercise failure paths.
- Parent fixed the reviewed publication faults: optional index failure no longer blocks a persisted segment; a rejected transcript sink does not count/broadcast an uncommitted segment. `Temp/segment_review_repros.py` now confirms both results. Parent also fixed sealed-turn input fallback; scoped work-stop ownership is covered by the work-owner tests.
- Source parsing, watched-symbol validation and scoped diff whitespace checks pass. No model/state or saved-layout mutation performed.

## Open / next
- Root owns final aggregate tests, review marks, generation and any approved runtime reload. The expanded copied-body fixture includes two continuation cases plus segments, natural boundaries and work-owner/headless cases, with no chat-face path. It does not certify identity/memory/task migration, original-path denial, real model performance or every faculty.
- Segments use the existing audit disposition policy; delivered does not imply PASS. Ongoing work remains bounded by natural completed model/tool calls and existing total budgets. No real-time or permanent-thought claim is supported.
- This note supplements `2026-10-05_2213_Codex_BodyOutputSegments.md` and `2026-10-05_2229_Codex_AutonomyStepBoundaries.md`; ownership and runtime integration remain with root/bridge.
