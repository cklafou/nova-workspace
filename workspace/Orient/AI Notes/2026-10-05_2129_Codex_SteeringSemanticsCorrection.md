<!-- @nova: Record the user-rejected cancellation draft and the verified distinction between active-turn steering and provider support. -->
# Steering semantics correction
**Summary:** Cole rejected cancelling the model prompt on every new message. The Tier 1 requirement is continued work that incorporates ordered follow-ups while retaining the original request and completed work. It remains unfinished.

## Decision and evidence
- Codex documents turn/steer as adding input to the existing active turn, and turn/interrupt as separate cancellation: https://learn.chatgpt.com/docs/app-server#steer-an-active-turn . This does not expose every internal implementation detail.
- OpenAI documents a model-provider steering protocol that finishes the current output item and existing hosted tool work before continuing with accepted input: https://developers.openai.com/api/docs/guides/steering . Do not equate this with cancelling each HTTP inference request.
- Nova currently sends fixed messages to the local llama.cpp Chat Completions endpoint in nova_body/nova_voice/nova.py. Exact-build inspection by bridge_research found no user-input steering endpoint. A reasoning_end control is not new input injection. Between-call continuation is feasible, but does not by itself establish equivalent interruption latency.

## Withdrawn draft
- Routing agent removed only its unvalidated Tier 1 draft changes from nova_runtime/model_client.py, nova_cortex/context_budget.py and nova_voice/nova.py using inverse hunks; no broad checkout/reset.
- Its new steering.py was moved outside importable source to Temp/rejected-steering-draft-20261005/steering.py.rejected with pre-reversal snapshots. No server wiring or deployment occurred for that draft.
- The earlier 2026-10-05_2120_Codex_SharedSteeringReview.md remains a historical proposal. Its optional provider-child cancellation is not the accepted behavior or a verified description of Codex.

## Open / handoff
- Choose and prove a provider-compatible continuation mechanism before claiming native steering parity. Preserve every accepted follow-up, original goal, completed tool receipts, and a consistent audit/input revision. Ordinary continuation must remain distinct from explicit Stop.
- Separate pause-tolerant STT and mute/status UI changes remain in the working tree with their own fixture evidence; they do not solve this shared-runtime issue. Worker state forwarding and live voice validation remain open.
- No microphone, speaker, Nova lifecycle or Nova-owned state actions were taken during this correction. Leave Cole's active test session alone.
