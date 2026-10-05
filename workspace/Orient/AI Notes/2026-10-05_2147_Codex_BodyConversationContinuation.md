<!-- @nova: Record body-owned natural-boundary conversation continuation and isolated relocation verification. -->
# Body-owned conversation continuation

**Summary:** Implemented the non-cancelling continuation semantics agreed in `2026-10-05_2129_Claude_SteeringLikeClaude.md` and the Codex correction at 2129. The body owns active turns; Nova Chat is an adapter. No runtime services, model inference, audio, or desktop actions were started by this work.

## Did
- Added `workspace/nova_body/nova_runtime/conversation.py`: ordered input batches, stable turn ID, input revisions, optional face observer, a conversation registry and synchronous final admission seal. A closed turn rejects new submissions, so the caller can schedule a subsequent turn. Observer failure or detachment does not discard the body's accepted message. Explicit Stop still propagates cancellation.
- Added `NovaRuntime.conversations` and optional `ModelClient.generate(..., steering=...)` forwarding. Legacy clients receive no new keyword when it is absent.
- Extended `nova_voice/nova.py` at natural boundaries before/after model calls, after completed tools, before/after each witness call/read, and before final delivery. The model request runs to its normal completion. New input never cancels it or requests `reasoning_end`. Completed output remains private intermediate context; obsolete, unexecuted tool proposals are explicitly labelled not executed. In-flight tools finish once and their receipts stay in the same run.
- Candidate audits are invalidated when a newer input revision arrives. The final observer is rechecked, then admission seals without yielding before the final sink. Genuine explicit Stop still owns cancellation.
- Extended `nova_cortex/context_budget.py` to preserve the original request and every accepted follow-up. Compact completed-attempt records preserve tool, operation/run correlation, actual status, bounded argument preview and exact digests separately from the full observation. A clipped observation does not erase the fact the attempt ran or imply success. Intentional repeats remain allowed. An impossible protected-content budget fails explicitly instead of silently dropping accepted input. Internal anchor flags are removed before provider transmission.

## Verified
79 focused tests passed: 13 conversation tests, 33 witness delivery tests, 19 continuity tests, 7 provider diagnostics tests and 7 ModelClient tests. The relocation test copies only body code and test fixtures into a temporary tree, launches a fresh process with no `general_tools` path, and exercises real ModelClient plus Nova stream_response with fake providers/tools. It covers three follow-ups during an in-flight tool, original request and receipt retention, and natural completion of an older model output without executing its obsolete proposal. Other cases cover observer failures/cancellation, input arriving during the final observer or audit, context pressure, protected-content overflow, loop-limit continuation, and provider-wire metadata stripping. All changed Python files parse; scoped diff check passed.

## Boundaries / handoff
- This is transient active-execution state, not a replacement task board or a claim of active-run recovery across process restart. Existing durable task continuity remains separate.
- Local providers still finish the current output before applying input. No claim of mid-thought steering or improved first-audio latency is made.
- Text budgeting remains an estimate; image/tokenizer costs are provider-dependent. Full raw tool observations can still be clipped, while compact completed-attempt facts remain protected.
- Root owns Nova Chat admission/correlation, voice integration, Orient explanations/review baselines, and any live reload or testing. No personal state was edited. The rejected cancellation draft remains quarantined and is not used.
