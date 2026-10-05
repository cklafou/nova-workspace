<!-- @nova: Record current-request preservation and constrained witness protocol repairs after the paired voice semantic failure. -->
# Current request and audit repair

**Summary:** The received follow-up was present at revision 1, but the delivered answer omitted it while discussing a factual correction. The body now separates actual admitted input from internal correction prompts, preserves exact requested content across revisions, and enforces explicit no-tools instructions at action boundaries.

## Did
- `workspace/nova_body/nova_cortex/request_contract.py`: new pure per-generation current-request contract. Exact `request_inputs` admission metadata seeds it; consumed follow-ups append. Legacy callers use only the latest incoming message, avoiding an older cancelled/unavailable request's restrictions. No-write instructions do not ban read tools; quoted phrases do not become commands. Explicit permission can amend a previous restriction.
- `workspace/nova_body/nova_voice/nova.py`: snapshot applied obligations with candidate evidence; use actual request for receipt guards; keep requested answer and delivered progress in correction/echo prompts. No-tools blocks ordinary external dispatch and auditor reads. A restriction accepted while an audit runs prevents its next read without judging the prior segment against unconsumed later obligations.
- `workspace/nova_body/nova_cortex/witness.py`: check 3 explicitly covers unanswered applied follow-ups. Editorial/calibration exceptions cannot exempt missing requested content. Structured verdict protocol preserves evidence quotation and distinguishes PASS, CONCERN and INCOMPLETE. Legacy exact PASS remains compatible; PASS plus explanation still does not certify.
- Routing's `nova_cortex/audit_protocol.py` supplies strict schema and whole-document JSON classification; embedded/quoted tool objects cannot become reads. Invalid or unknown tool objects end incomplete rather than loose extraction followed by another attempt.
- All heavy audit paths receive frozen request/evidence context. Foreground/concession calls cannot dispatch reads; background reads remain bounded and respect restrictions before dispatch. `workspace/general_tools/cloud_call.py` only adds backward-compatible optional forwarding arguments; no cloud request was made by this work.
- `nova_runtime/model_client.py` forwards optional copied `request_inputs`; `runtime.py` headless human service provides actual initial admitted entries. Root owns the face caller integration.
- `nova_witness/replay.py` v4 mirrors the current structured protocol and supports optional incoming-request fixtures. Explicit old witness source snapshots remain supported without transient runtime source swapping. Historical case labels/results were not changed.

## Why
The prior assertion guard treated the newest provider `user` role as a human request, although witness repair prompts use that role too. This could turn a private instruction mentioning a file into an apparent human demand for a read. The witness also had a broad editorial-omission exemption that conflicted with its own answer-coverage check. Structural JSON constraints address malformed audit output, not semantic correctness.

## Verified
- 12 request-contract and actual `stream_response` tests: frozen follow-up coverage, truthful corrections, no external tool/read dispatch, pending restrictions, heavy background no-read, stale cancelled input, and strict JSON behavior.
- 59 witness/delivery/replay tests; 31 conversation/segment/formatter/pending-input tests; 6 protocol tests; 8 ModelClient tests; 20 owner/headless tests; 18 durable recovery tests; 11 natural-boundary tests. Total 165 direct tests, all passing. Nested relocation checks are not counted again.
- The recovery suite was rerun after admission-metadata forwarding; the independent fresh-process relocation fixture still passes.
- Scoped diff check passed. Expected failure-injection tests print diagnostic tracebacks but pass.
- Routing separately verified the installed provider accepts the schema using bounded synthetic requests. This note does not claim the repaired model will now follow every instruction or judge every audit correctly.
- No services, model inference, mic, speakers, cloud requests, or Nova-owned record changes were performed by this repair slice. Root owns the actual paired voice and typed-tool rerun.

## Open / next
- Run the same recorded voice requests with exact provider payload diagnostics; measure whether the requested follow-up is present, unnecessary reads are absent, and speech finishes.
- Explicit tool-restriction detection is deliberately narrow pattern recognition, not a complete natural-language permissions engine.
- Root owns Orient explanation/review regeneration and controller fingerprint updates. Added production dependencies include `request_contract.py`, `audit_protocol.py`, and optional `cloud_call.py` forwarding.

## For Codex and Claude
Source is frozen for controlled acceptance. Do not loosen verdict parsing to turn malformed PASS-like prose green. Do not treat transport receipt, grammatical JSON, or fixture success as live semantic success.
