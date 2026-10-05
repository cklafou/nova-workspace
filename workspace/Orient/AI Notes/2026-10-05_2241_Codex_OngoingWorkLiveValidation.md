<!-- @nova: Record live segmented follow-up validation, measured latency, final controller state and remaining work. -->
# Ongoing work: live validation
**Summary:** The new conversation continuation/delivery path passed a bounded real-provider test. Autonomous attention, headless parity, and speech ordering have isolated fixture evidence. This does not close the natural-voice latency or full PLUCK acceptance work.

## Live evidence
- Started from Nova OFF / voice OFF. Started Nova through the controller lifecycle API, verified PID 44688 with `running_latest_code: true`, then sent one Codex test request and two follow-ups over WebSocket with explicit `voice_fast` register. No microphone, playback, external tools or desktop control was used.
- Observed two delivered segments under one stable run ID. Segment 1 retained input revision 0; both follow-ups were then applied at revision 2 and included in segment 2. Both carried explicit inline PASS. The terminal aggregate covered all three input aliases and did not duplicate transcript delivery. Programmatic marker ordering passed; Nova's self-assessment was not used as the test verdict.
- First delivered segment: 63.641 s. Second segment and terminal: 110.391 s. Context-memory preparation: 20.541 s. Main prompts: 38,912 and 39,101 tokens; prompt evaluation: 32.007 and 31.181 s; both reported cache_n=0. This is still unsuitable for natural voice conversation.
- Before shutdown: zero operations, no active owner, no pending body-owner inputs; autonomy remained disabled. Restored Nova OFF through lifecycle API. Final PID 5540 is chat-only, lifecycle off/pending false, voice off. A subsequent Orient evidence update is the sole stale fingerprint in that worker; functional runtime files match the live-tested build. The next worker start loads the documentation generator update.
- Receipts: `workspace/Temp/continuation-validation/live_turn_result.json`; exact opt-in provider/timing receipts in `workspace/Temp/provider-diagnostics/ongoing-work-live-20261005/`. Capture marker was removed afterward.

## Verification
- Root's server-function transport suite: 53 passing, including scoped Stop that waits for lease completion while the scheduler survives, sealed nested-input admission, completed-part preservation, and publication failure handling.
- Root reran 20 ownership/headless tests and 13 continuation tests, including the expanded relocated-body subprocess. Routing agent's 112 focused body checks, UI agent's 106 passing gateway tests plus one existing skip, and 29 frontend checks are reported in their notes. Root also ran voice-control 31 and controller/session/chat-only regressions.
- The copied-body subprocess has fake providers/tools/audit and temporary stores. It executes segment, boundary and headless/owner cases without general_tools imports. It does not certify relocated personal state/model dependencies or deny access to the original filesystem.
- Orient explanations and review markers were refreshed; final strict check follows this note's publication.

## Remaining / next
- Chat is an interface to ongoing work. Keep shared body work ownership and natural boundaries; do not reintroduce cancel-on-input or an arbitrary revision cap.
- Latency is the next measured blocker: semantic-memory preparation and full main-prompt reprocessing after audit. Changing delivery alone did not solve those costs. Inspect cache ownership/provider scheduling and context construction using the measured receipts before making performance claims.
- Existing reflect/decide/execute phase prompts remain, automatic semantic-memory context preparation differs by adapter, and active private execution context is transient. Durable tasks/receipts/transcripts are the restart basis; full in-flight recovery is not implemented.
- The existing Nova Chat window needs an interface reload for new JavaScript. Its layout/profile was not changed. Preserve any unsaved layout before reloading.
- Cole owns the next live microphone trial. No microphone test, speaker test, or mute operation should be started during that trial by an agent.

## For Claude
- Review request and scope were posted in Collaboration #105. This note supersedes earlier source-only deployment status. Further review should distinguish the successful bounded live continuation case from the still-unproven natural voice experience and whole-system PLUCK acceptance.
