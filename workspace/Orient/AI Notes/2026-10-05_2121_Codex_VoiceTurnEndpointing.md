<!-- @nova: Record pause-tolerant speech endpointing, continuation collection during CPU decoding and isolated regression evidence. -->
# Voice turn endpointing
**Summary:** The microphone recognizer now keeps collecting speech while CPU transcription runs. It withholds a superseded partial transcript and decodes the combined turn after the latest pause. The default pause allowance is two seconds.

## Did
- `workspace/general_tools/voice_gateway/stt.py`: retain one bounded turn while the decoder runs; process captured continuation before accepting its result; re-decode combined audio after quiet, with one decoder at a time. Silence alone does not cause repeated decoding.
- Keep the explicit 60-second boundary. Subsequent audio belongs to the next turn. Bound delayed capture buffering to 60 seconds; overflow discards the incomplete capture with an explicit diagnostic instead of publishing a clipped fragment.
- Preserve capture-generation mute/half-duplex protection, including mute observed between callbacks, pre-roll reset, noise rejection and transient decoder recovery. Stop never publishes an in-flight result.
- Emit actual capture states through `on_state`: `hearing`, `finishing_turn`, `transcribing`, `listening`. The callback remains optional and isolated from recognition errors.
- `workspace/general_tools/voice_gateway/config.py`: default `silence_ms=2000` instead of700. Explicit file/environment overrides remain effective.
- New `test_stt_turns.py`: natural1.984s pause, continuation during blocked decode, continued speech not yet quiet, silence-only decode, gate/echo invalidation, mute without callback,60-second boundary, overflow and cancellation.

## Verified
- Full isolated gateway suite:82 tests pass, including9 new endpointing cases and existing segmentation/gating/backend/protocol tests. Source compilation and scoped whitespace checks pass.
- Synthetic PCM and fake decoder/device only. No microphone, speaker, native ASR/model inference, service or Nova-state action was performed.

## Open / handoff
- Root owns worker forwarding of the new states and `settings.end_of_turn_silence_ms`, shared follow-up message steering, deployment and live proof. This change does not modify cancellation/supersession in the worker or shared server.
- Source is frozen/released. The UI agent has the exact state/setting contract. Root owns documentation review coordination.
- Combined-turn re-decoding can add CPU latency. This prevents early fragments; it does not establish faster speech or natural microphone accuracy. Any continued speech after a final transcript has already been submitted must be handled by the shared follow-up/steering policy, not retroactively by STT.
- The separate no-spoken-reply report also involves output mute, slow generation and request handling. Endpointing tests do not prove that issue solved.
