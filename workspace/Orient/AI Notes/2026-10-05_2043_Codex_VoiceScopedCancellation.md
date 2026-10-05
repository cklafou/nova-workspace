<!-- @nova: Record request-scoped voice cancellation and recognition-state integration before root-owned live audio validation. -->
# Voice cancellation and recognition state
**Summary:** Finished the voice client side of request-scoped cancellation and integrated the selected recognizer's transcribing state. Source is released to root for reload/live native validation.

## Did
- `general_tools/voice_gateway/nova_link.py`: `stop(request_id, timeout_s=2)` sends only that request ID and awaits an exact final `stopped` receipt. `stop_pending` is not success. No fallback to global stop.
- `general_tools/voice_gateway/control_worker.py`: End call, superseding input and full-duplex barge-in request cancellation for this socket's own pending request. Local output retires immediately. Shutdown waits for bounded cancellation acknowledgement before socket close; unconfirmed cancellation is reported honestly.
- `general_tools/voice_gateway/turns.py`: old scoped acknowledgements cannot retire a newer request. Bounded retired-reply identity history also blocks a late cancelled reply in replies scope.
- The optional recognizer `on_state` callback now exposes transcribing, then restores the current session state without replacing active playback. Root owns the recognizer implementation/config/assets; selected backend creation remains strict.

## Verified
- 73 gateway tests passed, including root's four Whisper tests; 30 controller tests passed.
- New fixtures verify exact scoped stop over a local WebSocket, stop_pending versus final acknowledgement, cancelled late-reply suppression, and worker acknowledgement before socket closure. A worker fixture also confirms transcribing state forwarding.
- These are isolated tests. No audio, model inference, runtime restart or Nova state edits occurred in this slice.

## Open / handoff
- Routing agent owns the server's same-socket request registry and scoped handler. Root owns reload, live audio/model queue and final native `--smoke-audio` validation. Client ownership is released.
- 2036_VoiceReplyPlaybackRepair records timeout/playback diagnostics. Its snapshot predates this additional request-scoped cancellation; the rule against global stop still applies.
- Actual conversation relevance/latency and human audibility remain separate from transport and component proof.
