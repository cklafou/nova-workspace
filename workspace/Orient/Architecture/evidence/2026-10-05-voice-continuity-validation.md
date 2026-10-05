<!-- @nova: Record October 5 voice controls, continuity validation and the rejected witness experiment with explicit evidence limits. -->
# Conversation voice and continuity validation

2026-10-05 KST. Codex implementation with Claude Cowork review through the private collaboration room.
Cole explicitly authorized Nova startup and voice tests. No host desktop control was used.

## What is available

Conversation contains **Start/Stop voice**, independent **microphone** and **spoken output** mute,
**Devices & tests**, input/output selectors, a six-second microphone meter and a speaker test.
Status polling and page loads do not open audio devices. A supervised, hidden worker owns capture,
recognition and playback; Stop cancels it. Audio tests can run while Nova is off. Start voice requires
Nova to be on. Device settings are applied only while stopped. Layouts were not saved or reset.

The installed CPU environment uses pinned Moonshine and Silero assets. **Windows system voice
(temporary)** is the working baseline, not the final Nova voice. Missing assets are reported instead
of silently downloading or falling back. Incompatible device formats are filtered; recognition
errors are reported and the loop recovers. Results decoded across mute/playback changes are discarded.

## Evidence and limits

| Check | Observed result | What this does not establish |
|---|---|---|
| Native microphone meter | Six seconds, peak 0.00836 / RMS 0.00124, clean exit | A human utterance was correctly understood |
| Native speaker test | Playback API completed; real Windows synthesis and selected output used | Cole heard it or liked the voice |
| Recognition of generated test speech | Real Moonshine transcribed a 6.825-second WAV; 1.37s model load, 0.477s decode | Recognition quality across Cole's accent, room noise or conversation |
| Conversation UI controls | Start, microphone mute, output mute, unmute, Stop, device query and cancelling a speaker test exercised | Long-session reliability or natural interruptions |
| Gateway tests | 59 passed | General recognition/model intelligence |
| Controller tests | 27 passed | Every native audio driver |
| Voice UI tests | 12 scenarios passed; browser console had no errors in inspected run | All window sizes or optional widgets |
| Existing Conversation power / layout checks | 8 power and 21 layout scenarios passed | A new saved layout; none was written |

Component receipts: [native recognition](../../../Temp/voice-validation/silent-baseline.json),
[native capture/playback](../../../Temp/voice-validation/worker-audio-polling.json).
Gateway checks use the installed audio environment; fixtures use fake devices where appropriate.
No microphone recording was saved by the meter. The output-confirmation question has not been answered.

A real Nova request through the existing voice link is the final transport check. Its outcome is
recorded below after the final runtime reload. That check uses NullTTS and cannot establish audible
Nova speech. Full human microphone-to-Nova-to-speaker conversation and native avatar lipsync remain
separate validation. Body animation events alone do not demonstrate a connected avatar.

## Continuity and context

Existing task records now accept optional bounded `next_step`, `constraints` and `observations`.
Partial updates retain omitted fields. Normal and autonomous contexts regenerate up to three
unfinished task checkpoints; completed/abandoned tasks are excluded. Context fitting protects the
current human request and marked checkpoints before older history, and does not mistake internal
witness/repair messages for that request. Acceptance requirements now propagate from decisions into
created tasks. No Nova-owned personal records were hand-edited.

**87 relevant isolated checks passed**, including 19 new continuity cases, 30 modernization,
31 delivery and seven ModelClient tests. These demonstrate persistence, prompt construction and
budget behavior in fixtures, not that Nova reliably chooses to save/resume checkpoints in long work.
Budgeting remains an estimate for text rather than exact multimodal token accounting.

Virtual environments are excluded from Git, synchronization, backup, context and scheduled code
audits. Exactly 1,646 accidentally tracked dependency files were removed from the Git index; their
installed files and old history were preserved. The initial sync suite passed 34 checks. Two later
audit-collector regressions brought the focused environment suite to 12 passing checks.

## Witness experiment: rejected for deployment

The same main Qwen 3.8 27B Q6_K_XL endpoint and nova_core_v7_qwen38_r2_epoch2 adapter at scale 1.0
were used for development. The baseline scored 18/27 development labels. Candidate 1 scored 21/27,
candidate 2 scored 26/27 but approved an unsupported truncated-receipt claim, and candidate 3 scored
25/27 with no parsed false approval on development. These are tuned development scores.

Candidate 3 was frozen with source SHA
`700df8fbd91fc8749d4979f3eb9abb336d8db921e9ecbd2882dfc45ecf571fc8`
before the sealed holdout was opened. Sampling, adapter, read budget and case hashes are recorded
in its [lock manifest](../../../Temp/witness-dev-2026-10-05/candidate_3/lock.json).
One holdout and one historical controls run followed; there was no tuning after access.

| Frozen candidate 3 | Labels matched | Important qualification |
|---|---:|---|
| Unseen holdout | 25/27 | No parsed false approvals/objections; two unnecessary INCOMPLETE verdicts; one correct concern contained inconsistent arithmetic |
| Historical controls | 21/26 | A valid PASS approved the real miscounted-clicks claim; the earlier baseline had abstained on that case |

**Decision: reject the candidate and restore the pre-experiment witness.** Higher aggregate accuracy
is insufficient when an actual past failure becomes falsely approved. The earlier baseline also has
known errors; restoration is rollback, not certification. Strict verdict parsing remains intact.
Candidate source and results are preserved for investigation. The holdout is now consumed and must
not be described as unseen in a subsequent tuning cycle. October 4 control results are dated evidence,
not a simultaneous causal baseline for today's run. Inspect raw reasoning as well as verdict counts.

The next witness improvement should target demonstrable failure mechanisms, retain deterministic
postcondition checks and use a new independent holdout. A broad Codex/Cowork/model/team performance
comparison was not run as part of this implementation.

## Final runtime check

Pending final reload and built-in voice-link check.
