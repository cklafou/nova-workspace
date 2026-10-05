<!-- @nova: Record the half-duplex capture-loss repair and device-free voice acceptance preparation. -->
# Voice capture hold
**Summary:** A queued reply could start over a human turn already being captured, causing the half-duplex gate to invalidate that input. The worker and standalone gateway now hold future output until recognition completes or resets. Full live recorded-audio acceptance is pending an exclusive model window from root.

## Did
- `workspace/general_tools/voice_gateway/control_worker.py` and `gateway.py` track whether capture is already hearing/finishing/transcribing. Such a capture continues despite held queued output. Returning to listening releases the hold, including silence reset or recognition failure. Actual playback still gates new half-duplex input. Mute and explicit Stop override capture; full-duplex barge-in retains its cut-current/hold-rest behavior.
- `test_capture_output_gate.py` exercises the real controlled voice loop with fake transport, microphone and TTS. Three failures reproduced before repair; four cases pass afterward.
- Corrected stale gateway/committer descriptions: follow-up input does not flush committed speech, and voice_fast does not authorize speculative unaudited tokens. Sentence splitting cannot eliminate inference/audit latency.
- `Temp/voice-acceptance-20261006/recorded_acceptance.py` prepares PCM fixtures and runs production Silero/Whisper endpointing. Live mode invokes actual control_worker.voice with only hardware endpoints substituted: PCM input and native TTS WAV-only output. It has not yet sent a Nova request.

## Verified
- Gateway: 111 run, 110 passed, one existing skip. Voice controller: 31 passed. Voice UI: 22 passed. Scoped diff check passes.
- Real local Whisper on a generated English fixture preserved one published main utterance across an internal 1.2-second pause and one follow-up. Load 2.58s; decoding 5.30s for 17.34s PCM and 5.67s for 4.86s PCM. These are preliminary preparation timings; replay pacing was corrected afterward and requires fresh live measurement. The follow-up misheard Amber as Ember. No Cole accuracy claim follows.
- Installed System.Speech inventory contains only David and Zira. No Chatterbox/Piper/Kokoro/Torch is installed in the voice environment. Zira remains a temporary voice; no new engine or paid service was installed.
- No microphone, speaker, Nova call, desktop operation or saved-layout change in this slice. Synthesis to WAV and isolated local ASR were explicitly authorized.

## Next
Root owns the exclusive runtime/provider window and final Orient review marks. Complete real recorded PCM → ASR → body WebSocket → delivered segments → WAV, followed by scoped Stop evidence. File synthesis is not audible playback; Cole owns the next microphone/speaker trial.
