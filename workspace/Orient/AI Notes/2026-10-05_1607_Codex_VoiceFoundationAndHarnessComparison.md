<!-- @nova: Record the offline voice transport foundation, gateway review repairs and Codex/Cowork comparison with remaining live checks. -->
# Voice foundation and agent architecture comparison
**Summary:** The voice transport and gateway foundation is implemented and tested without starting Nova. Cole's Codex/Cowork comparison is published, with Cowork's actual session observations and an explicit pending peer-review status.

## Did
- Answered and coordinated through Collaboration messages 60–77: Cole wants the comparison after the voice/avatar foundation, and Nova must remain off while he plays League. Claude acknowledged and supplied session observations in message 69.
- Added `workspace/general_tools/nova_chat/response_events.py`; updated `nova_chat/server.py`, `nova_body/nova_runtime/model_client.py` and `nova_body/nova_voice/nova.py`. Request/message/run identities and validated voice register survive queueing; exact-candidate audit status is distinct from delivery. Unavailable, superseded, cancelled and answered-elsewhere requests close explicitly. Stop and cancellation win over final delivery, including provider/observer edge cases. Chat-only requests do not touch Nova's personal transcript.
- Cross-reviewed Claude's gateway work. Claude repaired identity mismatches, stale reply speech, mic echo queueing, socket/mic supervision and misleading body events. In response to the outstanding room 74/77 handoff, Codex completed `speech.py`/`tts.py` shutdown fixes and regression tests: close stops/flushes and rejects late work; backend stop invalidates synthesis results; playback failures surface; null output and subprocess completion are not reported as observed audio.
- Corrected exact `@nova:` purpose headers in the changed gateway files. Updated its README and body-event documentation. Synthesis already computing may continue until the backend returns, but cancelled output cannot start later playback.
- Published `workspace/Orient/Architecture/evidence/2026-10-05-agent-harness-comparison.md` and linked it from the Orient generator. Read that report for official sources, exact Nova call paths, model/harness distinctions and the recommended order. This is the authorized targeted comparison, not the deferred comprehensive map project.

## Why
Nova already has environmental wake mechanisms, tool execution, persistent queues and acceptance verification. Evidence points toward improving reliability, evidence retention and resumable task state before replacing the architecture or attributing every difference to model family. Voice also needs trustworthy identity and cancellation before an avatar can present it faithfully.

## Verified
All checks used isolated state, fake providers/audio and (for socket tests) an ephemeral loopback mock server:
- Voice transport: 30 tests; witness delivery/callbacks: 31; model-client routing: 7; chat-only isolation: 7; source fingerprint: 2.
- Final gateway: 33 voice-flow + 2 socket/supervision + 9 committer tests = 44. Both independent reproductions in `workspace/Temp/voice_review_repros.py` now pass (capture-gate echo and backend stop during synthesis).
- Source compilation and scoped whitespace checks passed. No real inference, audio, GPU workload, dependency installation or host desktop control occurred.
- At 16:00 KST, `/api/version` reported PID 37804, `chat_only: true`, `running_latest_code: false`; ports 8080/8081 had no listeners. The existing broker was not restarted. Backend source changes load at the next normal restart/start.
- Cowork observations came from the actual collaborator, but its claimed outer hosting topology/model routing remain self-reported. A separate Codex worker reviewed the comparison; corrections were applied. Claude's critique had not arrived at publication, so the recommendations are not presented as joint consensus.

## Open / next
- Real microphone/STT/TTS, audible latency, echo behavior, avatar subscription/lipsync and native tracking remain unverified. Keep Nova/models/audio off under Cole's current instruction.
- The witness's frozen 26-case regression remains a dated 16/26 result, not general accuracy. Claude created 27 open dev and 27 sealed holdout cases. No new model evaluation ran; Codex has not opened the holdout. Lock a candidate before its single evaluation.
- Next architecture priorities are witness/evidence reliability, durable task/context state, targeted runtime/interface separation and controlled model/delegation comparisons. No broad rewrite or new autonomous experiment was started.

## For Claude
This answers `2026-10-05_1540_Claude_VoiceFirstStageAndWitnessCases.md` and room 73/75. Gateway file ownership is released. Review the shutdown follow-through and the published comparison when your active turn resumes; room messages cannot wake an ended turn. Do not start Nova while Cole's restriction is active. Preserve the sealed holdout.
