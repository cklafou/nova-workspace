<!-- @nova: Record body-owned natural step attention, completed-action preservation, and nested audit identity checks. -->
# Attention during autonomous tool chains
**Summary:** Added optional body callback `on_boundary` so the same active work can attend human input after natural model/tool completion. Provider calls are never cancelled or truncated because new input arrived.

## Did
- `workspace/nova_body/nova_runtime/model_client.py`: forwards `on_boundary` only when supplied, preserving older clients.
- `workspace/nova_body/nova_voice/nova.py`: calls the injected body work-owner callback before model calls, after completed provider/tool calls, at completed audit calls/reads, and before final delivery. Facts contain bounded previews, full-content hashes, stable turn/revision identity, and actual completed action status/operation ID. Tool proposals are explicitly unexecuted.
- Nonempty attended context is copied, restricted to user/assistant messages and protected through the existing fitter. The original objective remains anchored. Completed drafts stay private; obsolete unexecuted proposals are reconsidered. Completed tools retain their receipt and compact action anchor. Total tool/witness budgets do not reset.
- Frozen audits and already-completed internal phase results survive audit/before-delivery attention without a new regeneration loop. Their original candidate revision is retained. The owner keeps the human response/context for subsequent work.
- `workspace/nova_body/nova_cortex/witness.py`: `preserve_turn_context()` restores the outer Pipeline ContextVar after nested same-task conversation work, including errors and cancellation.
- `workspace/nova_body/tests/test_autonomy_boundaries.py`: 11 isolated tests of actual ModelClient/stream_response with fake providers and tools.

## Verified
- 112 focused tests passed: boundary, conversation including relocated-body fixture, output segments, witness delivery/evidence/replay, provider diagnostics, ModelClient, and exact prompt-cache checks.
- New cases cover input during natural inference, three updates while a tool is in flight, no completed action replay, stale proposal withheld, frozen witness source continuity, before-delivery no-regeneration, total budget conservation, nested audit identity, callback errors, and explicit Stop.
- `git diff --check` passed. No model, service, audio, or desktop operations performed; no Nova-owned records edited.

## Open / next
- Root/bridge own runtime and headless/Nova Chat callback wiring and live validation. This note does not claim a running process loaded these files.
- Responsiveness remains bounded by the current provider/tool call's natural completion; no mid-thought control or cancellation-on-message is introduced.
- Parent owns current Orient explanatory updates/review baselines; include the new boundary fixture as appropriate.
