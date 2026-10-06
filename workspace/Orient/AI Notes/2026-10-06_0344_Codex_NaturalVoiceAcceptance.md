<!-- @nova: Record ordinary recorded-voice continuation and its remaining content and latency limits. -->
# Natural recorded voice acceptance
**Summary:** The real recorded-English speech path maintained one ongoing conversation across a changed constraint and produced two ordered parts. The response still invented an on-desk bin, so full constraint/evidence correctness is not accepted. No microphone or speaker was opened.

## Actual path and result
- `workspace/Temp/voice-acceptance-20261006/fresh-natural-ready/result.json`, `acceptance-review.json`, and `session-lifecycle.json`.
- The frozen synthetic evaluator asks for a ten-minute desk plan, then changes it to five minutes, everything on the desk, no drawers or other storage. No internal speak/control syntax and no real actions were requested.
- Real local Silero/Whisper large-v3-turbo CPU int8, production controlled voice worker and WebSocket, actual Nova body/provider, delivered segments, and real native Windows Zira synthesis to files. The capture/output device boundaries alone were replaced with recorded PCM and silent WAV publication.
- Run `f4b2544d802147ea801608093181f921`: revision0 gives the initial plan; revision1 changes to five minutes and keeping items on-desk. Two ordered delivered parts, both explicit PASS, nine valid WAVs, no duplicated terminal aggregate, both aliases closed. The original selected chat was restored and all transcripts retained.
- The later plan introduced an on-desk bin as a fact and a trash exception despite no supplied bin/location and the no-other-storage constraint. Continuation and useful adjustment are demonstrated; fully correct constraint handling is not.

## Timing and recognition
- Request to first part: 42.500 seconds; first completed WAV: 43.234 seconds; terminal: 61.812 seconds. Follow-up acknowledgement to applied revision: 27.438 seconds. This is not real-time conversational latency.
- Strict word comparison reports 1/41 and 1/20 differences, entirely ten-to-10 and five-to-5 numeric spelling. The requested meanings were retained. This synthetic case does not measure Cole's natural microphone/accent accuracy.
- The nine files contain 62.9 seconds of synthesized speech. Native device playback, audible queue timing, voice quality and human approval were not tested. Zira remains a temporary system voice.

## Infrastructure and cleanup
The earlier `fresh-natural` attempt failed on its first read-only preflight before creating a session or loading voice. Root diagnosed and removed a legacy all-WebSockets-disconnected shutdown watchdog; root separately verified the worker survives a closed test socket. That failed attempt remains preserved. The retry used a fresh labelled session through supported APIs and restored the original. Postflight reports current code, voice off, no active operations. No self-restart, desktop focus action, personal-record edit, archive or deletion occurred.

## Other evidence from this slice
- The fresh typed read/follow-up case passed scoped content acceptance; see 2026-10-06_0337_Codex_FreshTypedContinuation.md. It did not exercise early multipart output.
- Native file-only queue/Stop checks passed six real synthesis assertions, separately from fake-device regressions and the earlier real request-specific Stop receipt.
- Failed repeated-marker and false-PASS cases remain failures; none were rewritten or hidden by the fresh-session tests.
- Parent owns final Orient/source review and the eventual human microphone/speaker trial. No further provider cases are running from this agent.
