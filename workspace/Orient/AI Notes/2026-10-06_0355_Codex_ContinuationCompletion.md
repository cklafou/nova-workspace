<!-- @nova: Summarize completed continuation/recovery repairs, final live evidence, remaining voice limits and restored controller-only state. -->
# Continuing work: implementation and final evidence
**Summary:** The outstanding body-owned continuation and recovery implementation is complete, including the specific stale-follow-up regression. Real-model tests also show that fast, consistently correct natural voice is not yet achieved. Keep those conclusions separate.

## Implemented
- `nova_body/nova_runtime/`: durable input admission, original-work/phase retention, crash recovery, explicit Stop, uncertain-action holds and receipt-based reconciliation. Completed side effects are not blindly replayed; partial output does not complete an entire goal.
- `nova_body/nova_voice/nova.py` and `nova_cortex/request_contract.py`: one bounded provider-only current-work snapshot after natural boundaries. New messages amend ongoing work; completed candidates/parts retain their evidence and are not discarded. Old correction/NOW context cannot represent the latest state. Shared headless/face context retains attribution and semantic retrieval.
- Chat face: durable segment publication, original-session recovery/pinning, request identity and rejection cleanup. Voice gateway: capture holds and committed speech queue/Stop behavior. Recall warms CPU encoders with visible readiness; conversational voice continuation preserves compatible provider caching.
- Audits use constrained JSON and frozen actual request/evidence scope; no-tools requests constrain reviewer reads. These repairs do not make model verdicts infallible.
- Removed the obsolete all-WebSockets-disconnected shutdown watchdog. Fixed the inner worker startup allowance and the launcher's incomplete-POST acknowledgement race. Explicit Quit still belongs to the launcher.

## Verified, with limits
- Body final slice:110 focused tests; independent current-work review23. Root face transport62, session pin7, segment metadata3; gateway110 passed/1 existing skip; hub/launcher/ack28. These overlapping slices are not an additive grand total.
- Fresh-process relocated-body recovery retained disposable identity/task/inputs/receipts, held an uncertain action, reconciled from a real later observation, delivered once and resumed the original autonomous phase. Model injected; not a complete personal-state/every-faculty PLUCK certification. `Temp/recovery-validation/2026-10-06_relocation.json`.
- Actual typed file-read plus in-flight amendment: one read, retained values/new condition, one run, final55.235s. Final-only delivery was appropriate after its amendment; no early-part claim. `Temp/continuation-validation/fresh-typed/`.
- Original-history, unchanged-PCM marker replay now retains the previously lost follow-up and delivers two parts. First32.157s, terminal88.422s, four valid WAVs; audit NOT_RUN then PASS. Recognition still substitutes Amber/Ember. `Temp/voice-acceptance-20261006/paired-current-step/`.
- Natural recorded conversation delivers two parts and changes ten minutes to five while staying in one run. Full semantic acceptance FAILS because the later advice invents an on-desk bin/storage exception; both model audits approved it. First42.500s, final61.812s, nine WAVs. `Temp/voice-acceptance-20261006/fresh-natural-ready/`.
- Real scoped Stop completed about235ms after response start. Six native file-synthesis queue/cancel/hold/resume checks passed. No microphone or speaker was opened; Zira is temporary. Synthetic English recognition does not measure Cole's microphone or live voice quality.
- A real no-input socket disconnect left the same worker alive after20.141s. Final reloaded launcher withheld a control response until the delayed body arrived and returned200 for already-off Nova. Evidence: `Temp/continuation-validation/socket-disconnect-result.json` and `final-lifecycle.json`.

## Remaining limitations
Natural real-time voice is not finished: cold roughly34k-token prompt processing alone took27.873s in the typed case, and corrections/audits add more. Within-run cache reuse is proven; fast cross-turn responses are not. A model can still violate constraints and its witness can falsely approve it. No fixture-specific bin ban, blanket expensive reasoning mode, history reset or false acceptance was used to hide that. All failed receipts remain intact.

## Final operating state
Nova OFF; model/witness ports8080/8081 closed; voice OFF; provider capture marker removed. Latest controller code is running in chat-only mode (worker32444, launcher2560 at verification), original conversation restored and all test sessions retained. No desktop window was opened or focused. The controller backend remains available for Nova Chat.

The temporary headless test launcher originally skipped the hub together with its viewer. After an idle global Stop, its verified worker was terminated; the owning launcher then performed normal guardian/watcher/model cleanup. The diagnostic wrapper was corrected to keep the real hub and omit only presentation, and the final chat-only launch used that corrected wrapper. This harness cleanup is separate from the fixed production WebSocket watchdog.

## For Claude and Cole
The specific ongoing-work/recovery foundation and regression repairs are delivered. Do not call the natural voice experience or autonomous reasoning reliability fully accepted. Future changes should target measured cold-context/audit latency and independent constraint/evidence evaluations; keep useful completed work, current goals and actual receipts intact. Root updated Orient explanations and review watches; the final strict check is recorded with the handoff.
