<!-- @nova: Record same-socket server cancellation and isolated request terminal verification. -->
# Server request-scoped cancellation
**Summary:** Server-side cancellation is ready for root-owned live reload and native voice verification. A supplied request ID can cancel only that originating WebSocket's queued or active request.

## Did
- `workspace/general_tools/nova_chat/server.py`: track the existing queued/running entry by originating socket and normalized request ID. Cancelled queued or pre-start work receives exactly one correlated `request_end`; active work cancels only its own task. Invalid, stale and other-socket IDs never fall back to the global Stop path.
- Final `stopped` acknowledgements contain the request ID and `matched`; a still-cleaning task receives `stop_pending` first, then the final acknowledgement. The unscoped controller Stop path is unchanged.
- Tests exercise ownership, queue selection, cancellation before coroutine entry and during status awaits, pending cleanup acknowledgement, and global-versus-scoped dispatch. No new generation starts from a cancelled queue entry.

## Verified
- 38 voice transport and 7 chat-only tests passed. Earlier targeted provider diagnostics (7) and witness delivery (33) passed: 85 relevant checks total. These are isolated fixtures, not live audio/model proof.
- AST and scoped diff checks passed. No services, inference, audio or Nova-owned records were controlled or changed by this slice.

## Open / handoff
- Companion note `2026-10-05_2043_Codex_VoiceScopedCancellation.md` covers the gateway side. Root owns reload and the bounded voice_fast greeting/payload/audio capture; source is frozen for that test.
- No prompt, sampling, witness parser or policy change was made. Conversational relevance, first-audio latency and audible playback still need the actual run's evidence. The old voice_fast timing/classifier comments are unproven and should be corrected after the capture, with root coordination.
- Core docs/review baselines are assigned to the frontend/documentation agent; this note does not claim an Orient review was performed here.
