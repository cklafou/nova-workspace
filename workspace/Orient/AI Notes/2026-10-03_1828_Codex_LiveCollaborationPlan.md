<!-- @nova: Record the live Codex and Cowork collaboration integration scope and initial routing finding. -->
# Live collaboration work
**Summary:** Cole authorized a live collaboration channel linking actual Codex and Claude Cowork with Nova Chat, plus joint discussion of next work. Implementation and connection checks are in progress.

## Did / why
- Read the shared notes through 1449. Avatar work remains separate.
- Confirmed current Nova Chat is stopped. Existing mute gates replies after storing and indexing messages; it is not a private collaboration channel.
- Plan: separate collaboration transport/store and widget; verify actual Cowork integration and keep Nova context/memory excluded.

## Verified
- Source routing inspected; no new collaboration code or live exchange verified yet.

## Open / next
- Establish real Cowork connection, implement bounded messaging and visible connection status, test restart/replay and isolation.

## For Claude / Codex
- Codex owns the collaboration implementation for this pass. Please coordinate before changing nova_chat. No API model will be presented as the existing Cowork session. Git exclusions reserved by Claude in the 1027 note remain separate until coordination.
