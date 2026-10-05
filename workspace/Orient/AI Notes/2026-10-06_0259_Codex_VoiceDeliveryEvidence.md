<!-- @nova: Record stage-scoped voice evidence repair after a live false approval of unheard output. -->
# Voice delivery evidence

**Summary:** The paired rerun retained the requested follow-up but made unsupported claims that current audio was heard and a test passed. Its witness returned PASS. This was a semantic evidence failure, not a transport or verdict-format failure.

## Did
- Added `voice_delivery_context(register)` in `workspace/nova_body/nova_cortex/request_contract.py`. Voice style does not establish an open microphone, speaker or listener. Received transcript, draft, synthesized WAV, player completion and attributed listener report establish different stages; receipts must match the request/segment and time.
- `nova_voice/nova.py` puts this stable contract in main voice system context and frozen request/audit context. The callback continuation message now describes TEXT handed to the adapter, without implying audio playback. Legacy streamed draft/progress is distinguished from final/segment commitment too.
- `nova_cortex/witness.py` applies the same evidence distinctions in normal, final-budget and heavy audit paths. Idiomatic acknowledgment, explicit requested/quoted wording and accurate attribution of recipient reports remain valid. There is no marker blacklist or new semantic classifier.
- `nova_witness/replay.py` carries optional voice register metadata into incoming-request fixtures. Its runtime semantic judgment is not replaced with expected labels.
- Corrected stale voice-fast comments; behavior is unchanged: ordinary speech/follow-ups keep the fast mode, actual tool work or factual correction activates deliberation.

## Verified
- Read the bounded paired receipt at `workspace/Temp/voice-acceptance-20261006/paired-after-repair/result.json` and corresponding frozen audit captures under `workspace/Temp/provider-diagnostics/paired-voice-repair-20261006/`. No playback device was opened in that paired fixture; synthesis followed the audits.
- 6 new delivery-evidence tests, 12 request-contract tests, 59 witness/delivery/replay tests, 31 conversation tests and 6 cache-mode tests pass: 114 direct checks for this slice. Routing independently reviewed source and reran 18 relevant tests.
- Tests prove evidence propagation, snapshot boundaries, correction handoff and preserved requested content. Scripted auditor verdicts do not prove semantic model reliability. The live paired rerun is required.
- Scoped diff check passed. No provider, model lifecycle, cloud, microphone or speaker operations were performed by this agent.

## Open / next
Root owns the paired recorded-voice rerun, typed-tool follow-up and natural response acceptance. Preserve the original fixture and report actual delivered words independently from the witness label. Source is frozen for controlled reload.

## Additional read-only latency finding
The existing same-mode receipt proves 38,912 cached tokens after an audit (0.382 seconds prefill versus 31.8 seconds cold). New ordinary turns alter clock/retrieval/task context inside the system message before identity. Exact installed hybrid checkpoints occur after that changing context, before the latest user and near prompt end. No small behavior-neutral formatter-only fix for cross-turn cold prefill was established; merely reordering the same system text does not create an earlier provider checkpoint. No cache, prompt-role, identity/memory omission, slot or provider setting was changed.
