<!-- @nova: Record a successful fresh-transcript tool-and-followup case and an infrastructure-aborted natural-voice attempt. -->
# Fresh typed continuation
**Summary:** The real typed read/follow-up case retained the actual read result and honored the latest requested final. It does not prove early multipart delivery or broad reasoning quality. The following natural voice attempt aborted before any session mutation because the controller API was unavailable.

## Typed evidence
- `workspace/Temp/continuation-validation/fresh-typed/result.json`, `acceptance-review.json`, and `session-lifecycle.json`.
- Supported session APIs created a labelled test chat and restored the original selected chat afterward (`restored: true`). All previous and test transcripts remain intact. No desktop focus or audio hardware action occurred.
- Real read_file succeeded for the disposable `Temp/continuation-validation/known_input.txt` at 32.031s, under operation `ebf678dc91324f30a23342baea7d812f` and run `e90458be158d4b71bbe1280a247dbaf2`.
- Follow-up acknowledged at 32.313s, applied at 35.735s; final at 55.235s preserved both actual values followed by the new requested condition, in order. The final had explicit PASS and no unsupported success/hearing claims.
- One delivered part only. The follow-up arrived before the first delivery and explicitly requested a short final, so root accepted current-request fulfillment; early multipart delivery is explicitly untested here. The raw multiple-parts flag remains false.
- A fresh chat isolates history selection only; normal identity, memory, retrieval and tools remain enabled. This does not erase or supersede the failed repeated-marker cases.

## Natural case not run
The first read-only preflight call to `/api/runtime/state` failed with connection refused. `workspace/Temp/voice-acceptance-20261006/fresh-natural/session-lifecycle.json` preserves that failure. No new session was created, no provider/ASR/TTS work started, and no restore was necessary. Parent was informed; no self-restart or retry occurred.

## Wrapper safety
`workspace/Temp/continuation-validation/fresh_session.py` uses supported list/new/rename/switch APIs, refuses busy runtime admission, avoids overwriting another client's newer selection and preserves all transcripts. Five fake-only tests pass. Session broadcasts visibly select the test Conversation in connected clients and clear pending file/image attachment chips; parent explicitly authorized that test impact. Desktop focus and saved layouts are unaffected. Parent controls further live windows and provider captures.
