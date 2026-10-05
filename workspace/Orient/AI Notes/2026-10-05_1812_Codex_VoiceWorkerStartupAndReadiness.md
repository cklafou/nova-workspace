<!-- @nova: Record the verified Windows voice worker startup repair and bounded readiness/segmentation improvements. -->
# Voice worker startup and readiness
**Summary:** Fixed the real native-library startup stall with an open control pipe. Direct mic and speaker tests completed. Added local-asset readiness, compatible-device filtering and speech segmentation protections; full conversation validation remains with the main integration task.

## Did
- `general_tools/voice_gateway/control_worker.py`: poll Windows control pipes before reading available bytes; publish early startup status; preserve stop/EOF control. Expose prepared-asset/VAD readiness and filter device choices by actual PortAudio 16 kHz mono support checks. Route recoverable recognition diagnostics through existing body events.
- `general_tools/voice_gateway/stt.py`: require local prepared Moonshine/Silero assets (no surprise model download or silent Silero energy fallback), cache the ONNX model, require 192 ms voiced audio, retain 288 ms pre-roll, use VAD hysteresis, trim trailing silence to 192 ms and recover after per-utterance decoder failures. Gate transitions clear pre-roll. Bound decoding tokens by utterance duration.
- `general_tools/voice_gateway/config.py`: document Windows TTS and expose installed voice-name/segmentation settings.
- Added `test_worker_readiness.py`; updated existing frame/gating/probe fixtures for the new contracts.

## Why
Fresh workers with an open blocking stdin read stalled while importing NumPy. Sending a control newline immediately released the import; even a blocking native ReadFile reproduced the symptom. PeekNamedPipe plus available-byte reads removes the pending blocking read. This establishes the interaction, without claiming a complete diagnosis of Windows CRT internals. Device format checks also prevent offering known 16 kHz rejects, while minimum speech reduces accidental noise-triggered requests.

## Verified
- Real direct microphone: completed six-second in-memory capture; peak 0.0083618, RMS 0.0012353; exit 0 in 6.4 s. No recording or transcript was saved.
- Real direct speaker: Windows system voice playback API started in 0.81 s and reported played in 6.16 s; exit 0. This is API completion, not independent human hearing confirmation.
- Receipt: `Temp/voice-validation/worker-audio-polling.json`; failed reproductions retained alongside it.
- 57 gateway tests and 26 controller tests passed. New tests cover a fresh-process native import with stdin held open, Unicode pipe framing/EOF, noise rejection, onset/tail, decoder recovery, half-duplex pre-roll clearing, missing-assets refusal and incompatible-rate filtering.
- Actual no-stream capability query: default Realtek MME input 1 and FiiO MME output 5 remain compatible; 11 inputs and 17 outputs offered, 24 incompatible direction/device entries excluded. No audio streams opened for this query.
- Prepared-asset probe reports Moonshine/windows/Silero ready. Diff whitespace check passed.

## Open / next
- Root owns live UI start/mute/stop and controlled end-to-end voice validation, service loading and final Orient integration. Audio ownership was explicitly released before those checks.
- This is a temporary Windows system voice baseline, not Nova's chosen/clone voice. Device availability can change; runtime errors remain visible. Minimum speech reduces noise risk but cannot prove every recognized utterance is human intent.
- Runtime probe checks local file presence/nonzero size; setup verifies pinned SHA256. It does not rehash hundreds of megabytes on each status request.
- No GPU model, Nova state, microphone recording or model inference was used by these regression tests. The witness development/holdout task is separate.

## For Claude and Codex
The blocking-control-read reproduction is stronger evidence than assuming a first-run antivirus delay. Please retain that regression. Voice source was released after this note; do not attribute an end-to-end Nova voice outcome to these component tests.

**Correction (2026-10-05 1813):** The final gateway total is 59 passing tests after a further root review caught a missing post-decode capture validity check. A transcription now discards its text when the capture generation changed during decoding or the microphone gate is still closed. Two blocked-decoder tests cover invalidation followed by reopening, and mute before another audio callback. The previous gate fixture now expects the stale pending transcript to be discarded. Controller tests remain 26 passing.
