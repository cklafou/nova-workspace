<!-- @nova: Record bounded opt-in provider diagnostics and truthful witness read-attempt reporting without a prompt-policy change. -->
# Provider diagnostics and read attempts
**Summary:** Added short-lived local capture of the actual outgoing provider JSON fields and timing phases, so the slow/off-topic voice response can be diagnosed from payload evidence. Read refusals no longer claim successful verification in new pipeline details.

## Did
- `nova_body/nova_voice/provider_diagnostics.py`: disabled by default. A marker in `Temp/provider-diagnostics/capture.json` with `capture_id` and timezone-aware `expires_at` enables at most ten minutes of capture. Final payload fields are captured after fitting, image data URLs are explicitly replaced, and a canonical original-payload SHA256 is recorded. Per-capture limits:32 files,8MiB; each file at most1MiB. Atomic writes remain in Temp.
- `nova_body/nova_voice/nova.py`: measure outgoing generation/audit first-token, first-content and total time; preserve cancellation/error behavior. Record returned provider token/timing metrics when present. Correct witness read reporting to attempted/returned/refused/failed; returned text is not verification. Existing event key remains compatible.
- `general_tools/nova_chat/server.py`: time context update, semantic memory and workspace context separately, with request correlation; fingerprint includes the helper.
- Added `test_provider_diagnostics.py` and relevant regressions in witness-delivery and server-transport tests. The UI agent separately corrected the old pipeline labels.

## Verified
- 7 diagnostic +33 witness-delivery +31 server-transport tests pass. Fake transport verifies captured JSON equals the real fetch function's outgoing fields; cancellation still propagates, errors remain errors, limits prevent further capture, expired/default-off markers create no receipts, and image pixels never enter diagnostics.
- Scoped AST/diff checks pass. No live provider calls, audio actions, model configuration changes, service restarts or personal-state edits performed by this subagent.
- The earlier greeting's checked source/records retained the current request. Exact successful provider payloads were not previously logged; these diagnostics close that evidence gap without assuming a prompt fix.

## Open / next
- Root owns safe runtime reload, enabling a unique capture marker and one controlled speech-path test after the user's active turn is idle; remove the marker afterward. No capture marker was created here.
- Witness policy, strict parser and sampling remain unchanged; the rejected candidate was not redeployed.
- `witness_max_rounds_voice=2` currently means two revision opportunities after the first audit. Each audit can request three reads plus a final model call; binding arbitration can add another consensus turn. This explains potential serial latency but is not changed by this instrumentation.
- Root owns Orient explanations/review baselines and final live conclusions. Source is released.
