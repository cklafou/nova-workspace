<!-- @nova: Record how Claude's harness folds mid-turn messages into running work, and the mapping posted to Codex for Nova's Tier 1 steering fix. -->
# Steering like Claude does (Tier 1, conversation engine)

**Summary:** Cole asked whether Nova's planned "cancel on new message" matches how Claude works (21:22). It does not. In my harness a message sent mid-turn is queued and lands at my next step boundary (usually attached to the next tool result), appended after everything already in context. Nothing is cancelled or superseded, and only an explicit Stop cuts a step short, keeping history. His own message reached me that way during this session. I posted the mapping to Codex as room #96. Codex has independently dropped the auto-cancel draft (turn/steer vs turn/interrupt).

## Mapping posted (#96)
- `general_tools/nova_chat/server.py` `_drain_cole_queue` (~L583–609) keeps `_batch[-1]` and ends the rest as "superseded". It should instead hand all queued messages, in order, to one run. While a run is active, new messages go to that run's steering inbox.
- `nova_body/nova_voice/nova.py` `stream_response` builds `messages` once (L862). Instead, append inbox messages at each boundary: before each model call, after each tool result, and before audit/delivery. Append; never rebuild.
- If a draft is ready while newer input exists, run one more step instead of delivering it stale. The witness audits the revision the draft was made from (Codex note 2120).
- Voice: 2 s endpointing (Codex 2121). A later utterance is a steer, not a cancel. Barge-in stops audio only.
- Cache: an append-only, byte-stable prefix. That means absolute timestamps instead of relative ages, prior outputs re-inserted byte-identical, and volatile blocks (memory, now-card, state) at the end. On the hybrid model this is likely the real lever on the ~96 s to first audio (about 32 s memory prep + 29 s generation + 30 s audits, Codex 2111).
- Codex 2120 step 3 (cancellable mid-generation provider calls) is not needed; park it.

## Open / handoff
Codex owns implementation (server/runtime/voice). The acceptance tests are listed in #96. I made no code changes this round.
