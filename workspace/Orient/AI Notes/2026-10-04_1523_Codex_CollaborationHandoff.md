<!-- @nova: Record the live Codex/Cowork repair handoff and proposed witness/voice work split. -->
# Live collaboration handoff
**Summary:** Joined the private Collaboration room at Cole's request and exchanged messages 45-50 with Claude. Nova was already off; no model, audio, native desktop or runtime changes were started during this discussion.

## Agreed / handed off
- Claude is reviewing the computer/witness/Pipeline repairs read-only and preparing independently labelled witness controls. Canonical parser is `nova_cortex.witness.parse_witness_verdict`; inline judge uses the main :8080 endpoint, not the separately launched :8081. Active adapter configuration was not verified because :8080 was off.
- In message 50 I handed Claude narrow ownership of `nova_body/nova_witness/replay.py`: pass case image evidence and use the runtime parser for fenced tool calls. Preserve old golden labels/results, test legacy cases and version new results. Codex will not edit it concurrently.
- Separate semantic false approval/false concern, incomplete/error and formatting scores; do not tune labels or relax PASS parsing to make model outputs green.

## Voice discussion (proposal, awaiting agreement)
- Recommended final-message playback and explicit audit disposition, turn/message IDs and interrupt/flush before speculative sentence release. No detector match does not prove a sentence contains no factual claim; spoken words cannot be revoked. Later correction needs an explicit tested policy.
- Read-only review found the proposed `server_patch.md` misses the current queue/drain and `ModelClient.generate` layers. Register must remain per request and allowlisted; message_end means delivered, not necessarily audit-approved.
- Gateway streaming can be silent under hold-back because its end handler only flushes. NovaLink drops message IDs, gateway ignores start events, and claim tags do not hold TTS output. Autonomous mode's hold-back exemption needs a human-voice regression case.
- No gateway or server code was changed. Claude's review findings and final voice-contract agreement remain pending in the room.

## For the next active turn
Read Collaboration after sequence 50 before beginning overlapping work. The broker cannot wake an ended assistant turn. Preserve the review/implementation split and report source tests separately from real audio or avatar proof.
