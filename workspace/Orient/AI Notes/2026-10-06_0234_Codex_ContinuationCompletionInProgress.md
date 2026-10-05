<!-- @nova: Record in-progress recovery, cache, and voice acceptance evidence without claiming behavioral completion. -->
# Continuation completion in progress
**Summary:** The durable body and face recovery repairs are implemented and tested. The first combined recorded-voice run exposed an actual answer-relevance failure; the task is still active while that is repaired.

## Did
- Body coordinator checkpoints accepted inputs, original work, completed phases, output publication and action attempts. Explicit Stop is distinct from interruption. Uncertain effects require inspection and evidence-bearing reconciliation.
- Face queues recover original conversations without selecting another tab; missing faces fall back to body recovery. Exact persisted output reconciles a crash before body acknowledgement. Segment writes now require atomic durable publication.
- Stop still cancels actual work when checkpoint storage fails and reports the persistence error. Rejected inputs do not revive later.
- Shared context preparation now includes semantic recall for face and headless paths. Recall encoders use CPU and warm in the indexer's startup worker, with exposed timing/error state.
- Conversational voice_fast segments no longer accidentally change the thinking-mode prompt prefix. Actual tools/corrections can still enable reasoning.
- Fixed half-duplex queued output closing an already-active human capture; mute and Stop still win.
- Unknown explicit speaker names were being silently attributed to the active user. Preserve their names and let existing body principal screening classify them. Subsequent evaluator tests use the already registered GPT Astra profile.

## Verified
- Controlled same-mode main -> witness -> continuation cache probe reused 38,912 tokens: continuation prefill 0.382 s, compared with prior 31.181 s cold. First cold main remained 31.812 s. No template, role, slot, or witness weakening was used.
- First recall 25.37 s versus 24.6 ms warm; CPU warmup17.42 s and recall42 ms in isolated run. Loaded worker startup under current machine load later reported49.085 s; startup cost was not eliminated.
- Root checks:61 transport/identity,7 session-pin,3 segment metadata,7 embedding initialization,5 common formatter and30 modernization passed. Body agent's fresh-process relocation denied original-tree reads, retained synthetic identity/memory/task, and did not repeat an uncertain effect; injected model only.
- Recorded actual voice worker passed two-input/two-segment correlation, five valid synthesized WAV units, no aggregate replay and scoped Stop. No microphone or speakers were opened. One recognition substitution occurred in10 follow-up words; first38 words had no word errors.

## Open / next
- The same recorded voice run failed answer relevance: a recognized and applied follow-up detail was omitted after audit/correction work. Three audits made nine reads and emitted invalid prose verdicts; both delivered audits remained honestly INCOMPLETE. First segment took58.906 s after submission, terminal172.281 s. This is not a natural-voice or Tier1 completion claim.
- Bridge is repairing current-user obligation preservation and explicit no-tools handling through audit/guard corrections; routing is verifying strict structured audit output. Re-run the same behavioral fixture with diagnostic capture, plus a disposable real-tool follow-up.
- Reload final body/face sources before final acceptance; current worker has stale recovery/server changes. Root owns lifecycle. Leave Nova/voice off after testing.

## For Claude and Cole
- Do not restart or edit the active work independently while tests run. Provider cache repair and recovery fixtures are evidence-backed; live conversational behavior is still being worked on.
- Receipts: workspace/Temp/provider-cache-source/baseline-same-mode.json; workspace/Temp/recovery-validation/2026-10-06_relocation.json; workspace/Temp/voice-acceptance-20261006/live-worker/result.json and scoped-stop/result.json.
