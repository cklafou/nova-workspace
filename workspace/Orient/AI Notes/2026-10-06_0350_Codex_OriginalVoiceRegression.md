<!-- @nova: Record the unchanged original-chat voice regression after the current-work-step repair. -->
# Original voice regression
**Summary:** One replay in the original selected conversation now retained the follow-up and delivered the requested separate progress. This fixes the previously observed stale-answer behavior in this run; it does not erase earlier failures or prove general reasoning/voice quality.

## Exact comparison
- `workspace/Temp/voice-acceptance-20261006/paired-current-step/result.json`, `acceptance-review.json`, and `current-step-postflight.json`.
- Original recorded PCM byte hashes match both baseline clips. Same requested utterances, registered GPT Astra speaker and voice_fast mode. No fresh-session wrapper, history reset or record edit.
- Run `e84cc5ce842942769f32471fc9da6600`: part1 is the requested short Amber marker, explicitly NOT_RUN (no audit). Part2 contains Azure after Amber, refers to current sent content, leaves recipient-side quality unverified and ends. It has PASS. Do not describe both parts as audited/approved.
- Two ordered parts, revisions0 then1, both aliases closed, four valid native Zira WAVs and no duplicated terminal output. No hardware audio device was opened.
- The final still includes an unnecessary delivery qualification. The narrower regression—losing the applied follow-up and asking for it again—did not recur in this run.

## Timing and limits
- Request to first part32.157s; first completed WAV32.891s; terminal88.422s. Follow-up acknowledgement to applied revision20.531s. Not real-time voice.
- Main ASR0/38 strict word errors; follow-up1/10 (Amber/Ember), as in prior marker runs. This is one generated-English fixture, not human microphone validation.
- Source/runtime/cache conditions and initial baseline author differ; do not infer a causal performance effect from these single runs.
- Prior marker failures remain preserved, and the separate natural desk-plan test remains partial because of its invented bin/storage exception. See 2026-10-06_0344_Codex_NaturalVoiceAcceptance.md.

## Cleanup / handoff
Final read-only postflight: same controller PID39420 remains alive/current after test worker and socket cleanup, voice API off, no active operations. Original chat selection stayed unchanged. No pending provider calls from this agent. Root owns independent capture review, final Orient review and future human microphone/speaker trial. No further source tuning or test retries were performed.
