<!-- @nova: Record gateway follow-up continuation, combined-reply identity and maintained source documentation without claiming live voice proof. -->
# Voice continuation gateway
**Summary:** New voice input and barge-in stop obsolete local audio only. Explicit End call retains scoped body cancellation. Combined replies can speak once for the latest acknowledged voice input while preserving typed/voice input correlation.

## Did
- `general_tools/voice_gateway/control_worker.py`: remove new-input/barge-in Stop calls; explicit End call/shutdown considers all still-owned pending IDs, even earlier audio-ineligible ones. Forward actual hearing/finishing_turn/transcribing states and expose configured pause allowance through probe/start metadata.
- `nova_link.py`: parse `message_context` as an applied-input binding event. `turns.py`: bind aligned request/reply pairs and input revision under stable response/run IDs. Foreign typed aliases may have null request IDs; null never matches a voice-owned input. An initial context update can bind an already-acknowledged local input when the original typed start was missed. Later updates preserve the run and append identities. Final frames cannot self-bind, add unannounced inputs or roll back revisions. Duplicate final frames cannot produce repeated speech.
- Combined terminal outcomes close covered pending inputs. Old drafts that omit the newest voice input stay silent; a correct combined reply speaks with the latest eligible voice request ID. Missing acknowledgement, wrong run/reply or malformed revisions never loosen identity.
- `nova_chat/static/index.html`: active-turn input badge says “added to active work” with next-completed-step explanation; ordinary waiting input still says queued. No layout or audio controls changed.
- Maintained docs: `voice_gateway/README.md`, `architecture_map/orient.py` Execution path, and `notes/controller_layouts.md`. Added body `nova_runtime/conversation.py` and chat `_steer_request` to Execution path watches. Review baselines remain untouched for root's final pass.

## Verified
- Full gateway suite: 96 tests ran, 95 passed and one existing skip, including 14 new gateway continuation tests. The new tests include real ResponseEvents construction with fake session/output, mixed typed/voice aliases, two-utterance worker orchestration, local barge-in and explicit End call cleanup.
- Controller suite: 31/31. Voice UI: 21/21. Queue badge renderer: 2/2. Scoped diff check passed.
- Fakes/local mock transports only. No live Nova inference, microphone, playback, lifecycle, desktop or Nova-owned state changes were performed by this slice. Current core continuation and full relocation evidence belong to the other owning slices; no native provider-inference steering claim is made.

## Handoff
- Root owns server/body integration review, review-baseline marks, deployment and any later human voice test. The latest user feedback remains unresolved by fixture evidence alone. Natural speech quality and latency must not be described as passed.
- Source is released after the final narrow malformed-revision regression. No further source or UI changes planned here.
