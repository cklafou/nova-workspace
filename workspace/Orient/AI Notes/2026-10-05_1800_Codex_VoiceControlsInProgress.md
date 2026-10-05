<!-- @nova: Record Conversation voice controls, continuity fixes and ongoing live validation. -->
# Conversation voice and continuity in progress
**Summary:** Cole authorized Nova and live voice tests. Conversation now contains voice controls, device selection and microphone/speaker tests. Work is still in validation.

## Did
- Added supervised local voice API and worker; Conversation controls do not start recording on page load.
- Installed a separate CPU voice environment with pinned dependencies and Windows system speech as a clearly temporary baseline.
- Added bounded task continuity and context retention without editing Nova-owned records.
- Excluded virtual environments from sync/context/backups and removed 1,646 accidentally auto-tracked dependency files from the Git index while preserving disk contents. Existing commits remain intact.

## Verified
- Offline controller/UI/continuity/gateway tests pass; exact final totals will be in the closing note.
- Silent Windows speech synthesis to WAV and real Moonshine transcription succeeded.
- Live witness development set: baseline 18/27, candidate 1 21/27. One false approval persists; holdout has not been opened. Median latency 14.2s versus 3.4s in these sequential runs.
- First native microphone test stalled before status events; Stop cancelled it. Diagnosis is active. No end-to-end live voice success claimed.

## Open / next
- Diagnose worker startup, then native device and full voice transport tests.
- Review remaining witness failures, freeze next candidate before the untouched holdout.
- Restart normally to load final controller, continuity and sync changes; autonomy remains paused.
- Update Orient and the comparison evidence. Claude resumed at collaboration message 86 and is doing read-only review.

## For Claude
- Codex owns voice source, controller/UI, witness candidate and continuity. Please send review findings in the room; do not edit those concurrently.
