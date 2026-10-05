<!-- @nova: Record shared body work ownership, natural-boundary human attention and durable headless reply coverage. -->
# Body-owned ongoing work
**Summary:** Nova's runtime now owns a synchronous work lease shared by autonomous work and nested human attention. The same task/focus and completed phase/action context survive that attention; new messages do not cancel a provider call or replay completed actions.

## Did
- `workspace/nova_body/nova_runtime/work_owner.py`: same-task reentrant lease, serializable ordered human inbox, bounded private prompt context, metadata-only public snapshot and scoped Stop completion event. Pending admitted input survives owner release. A competing task cannot claim work while model availability is awaited.
- `nova_runtime/runtime.py`: wake claims before awaits; explicit wake remains pending if another owner is active. Human service pauses the autonomous time budget, retains completed phase output and rechecks task identity/status before applying stale board directives. Natural model/tool/audit boundaries use the same attending hook as phase completion. Scoped Stop ends the current lease after supervised resources drain and preserves the daemon; explicit global Stop clears its cancellation count before resume; external cancellation propagates.
- Headless human replies use the body `ConversationTurns`, shared `ConversationContext`, exact input revisions and `on_segment` protocol. The terminal aggregate is never appended twice. Later input joins the same active turn at natural boundaries; input not covered by a delivered segment stays unread.
- `nova_runtime/transcript_store.py`: each delivered headless reply can persist its covered Cole sequence and segment/audit metadata together. The covered marker recovers from that durable reply when the sidecar fails. Malformed or blank lines retain their physical sequence positions, preventing later sequence collisions. No real transcript or sidecar was manually edited.
- `nova_body/tests/test_work_owner.py`: twenty isolated regression cases, including actual runtime adapter forwarding into a fake ModelClient for both human and autonomous paths.

## Verified
- 20 ownership/headless tests pass (0.683s). They cover competing claims, same-owner nested attention, ordered follow-ups, preserved focus/action facts, paused time budget, stale directive suppression, scoped/global/external cancellation, resource-drain completion, exact covered revisions, no aggregate duplicate, sidecar recovery and malformed-line sequences.
- Existing 30 modernization tests pass (2.605s). Scoped diff check passes.
- Root separately reported relocated-body subprocess and real server-function fixtures; this note does not count those as additional independent live evidence.
- No services, provider calls, microphone, speakers or desktop operations performed in this slice. Source is frozen/released for root's text-only live validation.

## Limits / handoff
- The active lease and its in-flight private context are transient; durable task/receipt/transcript records remain the restart basis. This is not full active-execution checkpoint recovery.
- Existing reflect/decide/execute phase prompts remain. Shared ownership and attention do not prove a single unconstrained mind, instant interruption, or lower inference latency. Attention waits for a natural completed provider/tool boundary.
- Human headless formatting and delivery now use the same body helpers as the face. Automatic semantic-memory context preparation still differs by adapter; full personal-state/model relocation has not been certified here.
- Root owns server wiring, runtime fingerprints and live validation. Collab UI/root own the Orient explanation/review updates. Include `runtime.py`, `work_owner.py`, and `transcript_store.py` in relevant source dependencies. This note supplements the 2213 BodyOutputSegments, 2229 AutonomyStepBoundaries and 2233 integration notes.
