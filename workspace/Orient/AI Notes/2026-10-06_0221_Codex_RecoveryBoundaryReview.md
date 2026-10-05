<!-- @nova: Record independent recovery-boundary findings and the limits of the offline review. -->
# Recovery boundary review
**Summary:** Reviewed current controller recovery, session pinning, shared context preparation, memory warm-up, and body checkpoint ownership. No live service, model, microphone, speaker, or personal-state actions occurred.

## Findings and coordination
- Confirmed with a disposable actual WorkCoordinator fixture that answering a new conversation could archive an interrupted old conversation while its original input remained pending, losing the next resume's action barrier. Bridge added an uncovered-input completion gate and regression.
- Found ownership could remain locked if the final checkpoint write failed. Bridge moved in-memory release/signalling into finally and preserved the write error.
- Found explicit Stop could be blocked by checkpoint failure. Root and bridge added cancellation-preserving handling. Parent-directory creation is now also within the normalized write-error boundary.
- Found durable-admission rejection lacked the voice transport's expected author/terminal event. Root added a correlated error and request_end.
- Found face recovery did not reconcile a final segment already saved before the body completion checkpoint. Root now checks exact saved segment identity/text before requeueing.

## Verified
- Ran `python -m unittest discover -s workspace/nova_body/tests -p test_work_recovery.py -q`: 16 tests passed, including injected persistence failure and cross-conversation recovery.
- Shared prepare_nova_context preserves the existing file/recall/grounding sequence. The store and encoders serialize initialization; warm-up runs on the background indexer thread and exposes readiness errors.
- Provider-cache evidence and six mode tests are documented separately in 2026-10-06_0213_Codex_ProviderCacheDiagnosis.md.

## Remaining handoff to root
At review time, Transcript.add still swallowed persistence failure, so its return alone was not durable publication proof. Root was also asked to align terminal unavailable/rejection events with durable input state so ended requests do not unexpectedly resume after restart. Subsequent root changes/tests should be checked before claiming these closed. No runtime restart/crash acceptance is implied by this source and fixture review.

## Follow-up review
**Correction (2026-10-06 0224):** Root repaired both remaining handoffs above. Server segments now use Transcript.add(require_durable=True): the full snapshot is atomically replaced after fsync while holding the same reentrant lock used by append/flush, and only then enters memory. Replacement failure preserves previous disk and memory. Unavailable/cancelled queue endings cancel the durable input. Independent rerun: seven session-pin and three segment-metadata tests passed.

Read-only live status at 02:23 KST: voice off; controller PID 37556 had stale server.py and recovery.py. Body context/indexer/encoder/provider hashes matched. Transcript.py and session_manager.py were missing from the version inventory; root was asked to add both before the final reload. No reload or provider call was made by this reviewer. Startup fingerprints remain source evidence, not a real crash/restart publication test.
