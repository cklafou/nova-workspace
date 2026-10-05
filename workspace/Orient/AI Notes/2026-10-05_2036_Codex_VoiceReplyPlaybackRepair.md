<!-- @nova: Record voice reply retention, playback diagnostics and integration tests before the next native conversation validation. -->
# Voice reply and playback repair
**Summary:** Fixed a demonstrated silence hazard and made each voice turn's speech decision/output visible. A real native Nova reply test is still pending coordinated runtime/audio validation; these changes alone are not an end-to-end voice success claim.

## Did
- `general_tools/voice_gateway/turns.py`: retain the current acknowledged request after the 300-second delay threshold; emit one delay warning rather than removing the correlation. Unacknowledged/retired requests still expire, and explicit stop/new input prevents late speech. Emit per-turn lifecycle and suppression reasons.
- `general_tools/voice_gateway/control_worker.py`: create the selected recognizer with strict `make_stt(..., allow_fallback=False)`, publish its label/readiness, and immediately retire/mute local speech when Stop voice arrives.
- `general_tools/voice_gateway/speech.py`: publish backend, selected output, synthesis/playback timing and actual reported completion outcome.
- `general_tools/nova_chat/voice_control.py`: expose `last_turn`, `last_playback` and bounded `recent_events`; unrelated replies cannot replace the current voice turn. Retain these diagnostics until another session begins.
- `general_tools/voice_gateway/gateway.py`: add `--smoke-audio` using a real TTS backend and the same sweeper; refuse NullTTS for that test. Existing `--smoke-link` remains explicitly silent.

## Why
The prior live-link receipt took 312.804 seconds to deliver. The microphone worker's old sweeper removed its request at 300 seconds, so that delivery would no longer qualify as its own reply. The old silent smoke path omitted the sweeper and therefore did not reveal this. This is a source-confirmed hazard, not proof of the precise cause of every user-reported silent turn; the current controller had no surviving live failure diagnostics when inspected.

## Verified
- 65 gateway tests and 30 controller tests passed at this checkpoint; changed runtime sources compile and scoped whitespace checks pass.
- Tests cover a reply delivered after 313 seconds, cancellation/new-input suppression after delay, bounded retained requests, immediate local stop, actual worker orchestration over a local WebSocket with fake capture/playback, strict recognizer factory use, and refusal to count NullTTS as audio validation.
- Earlier native microphone/speaker component receipts remain in `Temp/voice-validation/worker-audio-polling.json`; they do not prove a full natural conversation.

## Open / next
- Root owns STT/config/setup changes, model/service queue, restart and live audio until explicit handover. No audio or model inference was started by this implementation slice.
- Root's recognizer update targets English Whisper large-v3-turbo CPU int8; voice worker supports its selected-backend contract. Availability depends on the prepared environment/assets.
- Stop voice ends this local speech session. It does not issue a global Nova generation stop that could cancel another client's current request.
- Full native response/playback, recognition accuracy, reply relevance and latency still require live evidence. Root and the frontend agent own final UI/Orient integration.
