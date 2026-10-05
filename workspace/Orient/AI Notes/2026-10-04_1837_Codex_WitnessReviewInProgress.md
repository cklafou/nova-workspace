<!-- @nova: Record solo ownership and validation status for the witness review fixes while Claude is unavailable. -->
# Witness review follow-through in progress
**Summary:** Cole asked Codex to finish what it can solo after Claude reached its usage limit. Taking over the replay and review follow-through from collaboration messages 51-53; avatar work remains owned by the other Codex chat.

## Did
- Read Claude's review and the 26 independently labelled controls. Runtime and replay now share compact receipts that retain actual outcomes instead of spending the old 220-character slice on environment notes.
- Verdicts take precedence over quoted tool JSON. Revised answers still enter the concession check when their re-audit is incomplete or errored.
- Added a combined witness image cap with explicit omissions, literal-safe audit sampling, and image-free diagnostic payload logging.
- Hardened launch verification against warning lines and failed initial window enumeration; made the cold-start wait tunable. Unknown outcomes get neutral Pipeline events.
- Preserved Claude's control labels and prior reports. Replay v3 records the changed evidence/sampling contract.

## Verified so far
- Offline: replay 15, delivery 19, computer launch 22, evidence 7, Pipeline 20 scenarios passed before the final added UI/redaction regressions.
- Prior live browser and Pipeline evidence is in the 1511 ComputerRepairValidation note; these new changes have not yet been loaded or exercised live.

## Open / next
Run final regressions, check live lifecycle, evaluate the fixed controls through the local model if idle, run voice readiness, and update authored Orient documentation. Voice gateway speech is not implemented/validated. No Windows desktop control, no personal-state edits, no avatar edits.
