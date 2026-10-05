<!-- @nova: Record device-free live voice acceptance, its behavioral failure, and pending paired validation. -->
# Recorded voice acceptance
**Summary:** The real recorded-PCM voice path delivered ordered parts and valid native speech files, but failed the follow-up content requirement. This is not an accepted natural-voice conversation. No microphone, speaker, desktop focus, paid service, or provider restart was used by this agent.

## Verified
- `workspace/Temp/voice-acceptance-20261006/live-worker/result.json`: actual controlled worker, local Silero/Whisper large-v3-turbo CPU int8, Nova WebSocket/body generation, correlated delivered parts, and file-only Windows Zira synthesis. Two parts kept one run and closed both input aliases; five native WAVs were generated exactly once. The terminal aggregate was not spoken again.
- Initial input recognition had 0/38 word errors; the follow-up had 1/10 (Amber became Ember). This is a synthetic English clip, not evidence about Cole's microphone or natural speaking accuracy.
- Request to first delivered part was 58.906 seconds; first completed speech file 59.485 seconds; terminal 172.281 seconds. Both delivered parts had explicit INCOMPLETE audit status. These figures do not establish real-time usability.
- `live-worker/acceptance.json` records transport success but overall behavioral failure: the applied follow-up's new marker was missing. Root/bridge/routing are repairing current-input relevance separately; the failed receipt remains unchanged.
- No provider capture marker was active for that run. Exact model payload, actual thinking flags, and per-provider timings cannot be reconstructed from this receipt alone.
- `scoped-stop/result.json`: the real controlled worker acknowledged a request-specific Stop and received cancelled delivery approximately 235 ms after response start; no output WAV was produced.
- `native-queue/result.json`: six checks passed using real hidden Windows synthesis without playback. Barge-in stopped current synthesis, held the next committed unit until resume, and End call stopped current synthesis and flushed pending output. Cancelled WAVs were not published. This is not audible barge-in proof.

## Attribution correction
The evaluator runner already requested speaker `Codex`, but that unregistered label fell back to active user Cole in the then-running server. The original receipt truthfully contains Cole. Root owns the server correction; subsequent fixtures use the existing registered `GPT Astra` identity and verify the echoed author. No personal records were hand-edited.

## Prepared / pending
- `recorded_acceptance.py` can reuse the exact original WAVs with `--input-source`; behavioral, recognition, attribution, and transport checks are separate. Existing receipt files are never overwritten.
- `workspace/Temp/continuation-validation/typed_acceptance.py` prepares a disposable known-input read, then submits a follow-up after the actual correlated read receipt while work remains open. It checks retained values plus a new condition in a later revision, ordered parts, and final alias closure. It has not run against Nova yet; three isolated evidence-filter assertions pass.
- Parent owns the next exclusive model window and dated provider capture. Real human microphone/speaker trial and final voice selection remain pending. Zira remains an explicitly temporary installed voice.
