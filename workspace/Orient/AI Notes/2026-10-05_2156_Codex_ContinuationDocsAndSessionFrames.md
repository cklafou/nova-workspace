<!-- @nova: Record continuation documentation updates and the isolated Conversation session-frame regression. -->
# Continuation docs and session frames
**Summary:** Updated maintained Orient explanations for body-owned continuation and its measured fixture limits. Conversation now excludes late, tagged output belonging to another session.

## Did
- Updated `workspace/general_tools/architecture_map/orient.py`: Execution path, Runtime evidence and open modernization work, Configuration and evidence, Access and practical debugging, and Test meaningful behavior.
- Updated `notes/security.md`, `notes/tunables.md` and `notes/controller_layouts.md` beneath the same generator directory. Corrected endpointing from 700 to 2,000 ms; documented protected inputs/action facts, explicit context overflow, admitted versus applied follow-ups, and explicit Stop of shared conversation work.
- Added relevant new test paths to `reviews.json` watches. Left all review dates and baselines untouched for root's integrated review.
- Updated `workspace/general_tools/nova_chat/static/index.html` using selected `activeId`: other-session user echoes, response starts/tokens/contexts/finals cannot render chat bubbles. Other-session thinking still enters the global Thoughts feed but not inline chat. Untagged legacy/global frames remain compatible. Changing tabs does not cancel work.
- Added `workspace/general_tools/nova_chat/tests/test_conversation_frames.cjs` using the actual production message handler.

## Verified
- Two new frame tests pass; together with queue-badge tests, four Node tests pass.
- Generator parses, review registry JSON loads, scoped `git diff --check` passes (only Git line-ending advisories).
- Reviewed the body relocation fixture source: selected Python packages and two continuation cases run with fake provider/tools/audit in a fresh subprocess without the chat face. It does not move personal state, execute real inference, deny filesystem access to the original workspace or constitute a complete PLUCK pass.
- Runtime evidence records the separately reported 79 body / 45 transport checks and this agent's 95 passing gateway tests plus one existing skip. These are fixture results, not a live conversation or speech-quality verdict.

## Handoff
All eight pending explanation sections are ready for root's mark-reviewed/generation after integrated source freeze. Root owns server conversation_id propagation and live validation. No services, devices, Nova records or saved layouts were operated here.
