<!-- @nova: Record the ongoing-work integration, independent review fixes, and source-versus-live limits. -->
# Ongoing work integration
**Summary:** Cole clarified that Nova must retain ongoing autonomous work and compound useful output, not wait for one final answer or restart on every follow-up. This integration now covers body-owned work ownership, delivered segments, and attention at natural action/model boundaries. Live validation is still pending in this note.

## Did
- Body `nova_runtime/conversation.py` orders follow-ups; `work_owner.py` serializes active work across conversation/autonomy, preserves focus/completed phase context and supports scoped Stop without killing the scheduler.
- `nova_voice/nova.py` emits audited completed segments through an optional sink, including explicit speak-and-continue control. New input neither cancels provider generation nor replenishes work budgets. Natural-boundary attention retains completed tool receipts and reconsiders unexecuted proposals.
- Witness records are frozen for each provider step; nested attention restores parent Pipeline identity. Audit status remains explicit, never inferred from delivery.
- Face `nova_chat/server.py` renders/stores segments, retains per-input revision correlation, and services the body inbox while the same autonomous owner remains active. The terminal aggregate is not stored or spoken twice.
- Reviewed and repaired publication failure paths (optional indexing cannot hide saved output), sealed nested-input admission, scheduler startup exclusion, and scoped End-call cancellation.
- Gateway queues committed speech in order; full-duplex barge-in pauses queued speech through recognition; explicit End/Stop/mute flushes. Shared body formatter and headless segment delivery preserve semantics without the chat face.

## Verified
- Root reran 53 real server-function transport fixtures, 31 voice-control tests, 17 work-owner tests, and 13 continuation tests including expanded relocation. The temporary relocated-body subprocess runs segment/boundary/ownership fixtures with fake provider and no general_tools imports.
- Routing agent reports 112 focused body checks passing. UI agent reports 106 gateway tests passing with one existing skip, 29 UI tests, formatter parity and transcript metadata tests.
- All are source/isolated evidence at this point. The controller last read as Nova OFF, voice OFF. No microphone or playback operated. No user-owned Nova records were edited by hand.

## Open / next
- Complete headless forwarding/sequence regression, freeze sources, run text-only live generation on the loaded build, then restore Nova OFF.
- Existing reflect/decide/execute phase prompts remain. Shared ownership/attention is not a claim that all cognition has been merged or that model latency is fixed.
- Active execution context is transient; canonical tasks, receipts, and delivered transcript remain durable. Full personal-state/model relocation and live microphone quality are not certified by these fixtures.
- Update generated Orient/review baselines after the final source freeze and report live evidence separately.
