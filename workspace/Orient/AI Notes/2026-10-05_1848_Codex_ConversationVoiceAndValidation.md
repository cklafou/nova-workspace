<!-- @nova: Record completed Conversation voice controls, continuity repairs, rejected witness experiment and a failed live conversation check. -->
# Conversation voice and validation
**Summary:** Voice controls are now embedded in Conversation and real local audio components work. The live Nova link delivered a correlated reply, but the conversation test failed on relevance and latency. The witness prompt experiment was rejected and rolled back.

## Did
- Added Conversation Start/Stop voice, separate microphone/output mute, device selectors and bounded audio tests; no layout reset or autosave.
- Installed reproducible CPU-only Moonshine/Silero environment with a temporary Windows system voice. Repaired worker startup, cancellation, recognition recovery, device filtering and stale transcript handling.
- Added bounded checkpoints to existing task records and protected current requests/checkpoints through context fitting. No personal state was hand-edited.
- Excluded virtual environments from indexing/sync/backups/Git/code audits; removed 1,646 previously tracked dependency paths from the index, preserving disk files and Git history.
- Coordinated with Claude in the actual Collaboration room; incorporated its voice/witness review. No response arrived after lock message91 before the final update.

## Verified
- 59 gateway, 27 controller and12 voice UI checks passed. Existing8 Conversation-power and21 layout checks passed. Real six-second mic capture and native speaker playback completed; generated speech was transcribed by Moonshine.
- Final loaded server PID46212 reported running_latest_code=true. Start voice reached listening; mic mute acknowledged with no transcript/error; Stop returned off.
- Continuity:87 relevant isolated checks, including19 new checkpoint/context cases. Initial sync suite34; final focused environment exclusion suite12. These are fixture/source assurances, not broad autonomous task success.
- Witness candidate3 was locked before holdout:25/27 unseen,21/26 controls, but a false approval on a real historical count error. Rejected; exact pre-experiment prompt restored.56 production tests pass. Separate12 frozen-candidate contract tests also pass; they are not deployed-policy tests.
- Live --smoke-link request80296545d2df4b0f92d016dbb7bc3d8c / run987cd7e03d4a4c2c8be02c01479de96c: delivered after312.804s, audit INCOMPLETE, four NullTTS units, no audio. Asked for a short greeting without tools; Nova used model-file tools and answered an older topic. Correct request survives checked assembly and fitting. No demonstrated queue bug; exact provider request bytes not captured.

## State and limits
- Nova and voice are OFF. Controller/collaboration remain available, final controller PID22952 at verification. Only the Orient generator changed after that final controller boot; voice/body source loaded during testing was current. Updated Orient is generated and checked separately.
- Human audibility confirmation, natural spoken conversation, custom voice and native avatar lipsync remain unverified. Temporary system voice is labelled explicitly.
- Do not present voice transport success as conversation quality. Reply relevance/latency and witness judgment remain the main quality gaps. Capture the exact provider request before another prompt change; do not retune on the now-consumed holdout.

## Evidence / for Claude
- Orient/Architecture/evidence/2026-10-05-voice-continuity-validation.md: concise implementation, measurements and limits.
- Temp/voice-validation/live-link-result.json and worker-audio-polling.json: observed runtime/native receipts.
- Temp/witness-dev-2026-10-05/candidate_3/acceptance.md: full rejection and rollback provenance.
- Read1839_Codex_WitnessHoldoutRejectedAndRestored.md and prior1808/1812/1817 notes for detailed source ownership. No agents retain write ownership now.
