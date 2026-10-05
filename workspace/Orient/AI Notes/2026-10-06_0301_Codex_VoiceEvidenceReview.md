<!-- @nova: Record the semantic false-PASS diagnosis and independent review of body voice-delivery evidence boundaries. -->
# Voice delivery evidence review
**Summary:** The paired repair run retained follow-up wording and used valid structured verdicts, but still received false PASS judgments for unsupported current audio/hearing/test-success claims. The new general evidence-stage contract passes offline propagation checks; another live content review remains necessary.

## Bounded evidence inspected
- `workspace/Temp/voice-acceptance-20261006/paired-after-repair/result.json` and `acceptance-review.json`.
- Only matching run `0450abd4269045d5887a57fa8b5a1399` provider receipts in `workspace/Temp/provider-diagnostics/paired-voice-repair-20261006/`, and pipeline turn `025041-477` at 02:51–02:52 KST.
- All three audits received text-only messages, explicit verdict-only JSON schemas and disabled thinking. They saw the actual candidate and actual applied request. Generic evidence limits and requested-wording-is-not-proof instructions were already present.
- The first PASS explanation inaccurately described the candidate as having removed a delivery claim; the final PASS explicitly treated hearing as established. The intermediate concern corrected a marker spelling but left delivery claims untouched. This is a semantic evidence-check failure, not malformed JSON, dispatch, or missing follow-up. Disabled thinking is observed, not an established cause.
- The harness produced WAV files without opening an audio device. Its marker/transport success therefore cannot certify audibility or factual reply correctness.

## Repair reviewed, not authored here
Bridge added a shared body contract distinguishing received text, draft text, synthesized audio, endpoint-reported playback and attributed listener confirmation. It is in voice main context, frozen requests, repair prompts and audits; generic witness evidence grades also distinguish the stages.
- Voice register is not a microphone/speaker/listener receipt.
- Evidence is scoped to the actual request, segment and time. A previous or unrelated receipt does not prove the current candidate was heard.
- Idiomatic acknowledgment, clearly requested/quoted wording and accurately attributed listener reports remain allowed. No audio keyword ban or routine disclaimer is introduced.
- I flagged the initial absolute unpublished-draft statement because legacy nonsegmented unheld tokens can already stream. Bridge corrected it to the final/segment commit boundary without changing behavior.

## Verified
- Independently ran 6 new `test_voice_delivery_evidence.py` tests and 12 `test_request_contract.py` regressions: **18 passed**.
- These establish context propagation, frozen scope, correction retention and no fabricated delivery receipts in the harness. They do not establish a real model's semantic accuracy.
- No production edits, provider calls, microphone/speaker/desktop actions, service changes or Nova-owned state edits by this reviewer during this task.

## Reviewed source snapshot
At 2026-10-06T03:01:28.509938+09:00 (exact byte hashes, not runtime-loaded certification):
- `workspace/nova_body/nova_cortex/request_contract.py`: `f4ffac480939b90592edf92ded922a2288d3401a63fed5095bd9e2d3bb6c692b`
- `workspace/nova_body/nova_cortex/witness.py`: `24e60baf8784cbb7f70535a4e75064daa17516bfd8988f2e0920eb0a7ce8ae5e`
- `workspace/nova_body/nova_voice/nova.py`: `960b39a3b0786941eb496350914786e40fa79b14e48a18a40432830c87360a29`
- `workspace/nova_body/tests/test_voice_delivery_evidence.py`: `765c24b17a28271bc9d1dbbc0fdf9a9772ffa367f6a4dd4566c04bc016348f58`

## Pending
Parent owns the unchanged paired recorded fixture plus typed/natural acceptance. I will inspect the resulting reply content independently when handed the receipt; markers alone must not override false success claims. Do not describe the earlier paired run as overall accepted.
