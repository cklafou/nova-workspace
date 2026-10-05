<!-- @nova: Record independent current-request, pending-permission and structured-audit review with offline regression evidence. -->
# Current request and audit boundary review
**Summary:** No remaining concrete blocker found in this bounded source review. Format compliance and request retention have isolated evidence; meaningful live voice behavior still requires the parent-owned paired acceptance.

## Changed by this reviewer
- Added `ActiveTurn.pending_inputs()` in `workspace/nova_body/nova_runtime/conversation.py`. It defensively copies queued message data without consuming, applying, revising or sealing it; the opaque transport-owner handle retains its identity.
- Added `workspace/nova_body/tests/test_conversation_pending.py` covering nested-copy isolation, FIFO preservation, no observer acknowledgment, later consumption, later additions and closure.
- No other production files changed in this review. Root owns Orient explanations and source fingerprints.

## Reviewed corrections by bridge and root
- Exact initial request inputs now come from admission metadata through ModelClient, with headless and Nova Chat callers wired. Compatibility fallback takes the latest user entry rather than adopting older cancelled requests.
- Explicit tool prohibitions are separated from no-edit instructions and quoted examples. Current applied follow-ups remain in repair/audit context, alongside already delivered segments. This is deliberately narrow phrase recognition, not a complete natural-language permission interpreter.
- Native inline audit supplies the JSON-schema response format; the whole-document parser rejects malformed, mixed and trailing output. Legacy exact PASS remains strict. A conforming verdict is not proof that its judgment is correct.
- Structured audit instructions retain verbatim evidence quotation. Optional heavy audit receives frozen candidate/request/evidence context; its action permission checks both later applied inputs and pending input before dispatch.
- A late no-tools follow-up suppresses a new inline read and asks for a bounded verdict-only result without changing the prior segment's frozen obligations. Heavy reads similarly recheck after their provider response.

## Independently verified offline
- 12 request-contract tests, 6 audit-protocol tests, 2 pending-snapshot tests, 7 witness-evidence tests and 8 ModelClient tests: **35 passed**.
- An additional fake-heavy-provider race began with reads allowed, accepted a no-tools follow-up while the continuing segment's fake cloud call was in flight, and returned a proposed file read. No read dispatched; progress and amended final segments retained revisions 0 and 1. The first harness attempt submitted after final sealing and was correctly rejected; the corrected continuing-segment harness passed.
- No live provider request, microphone/speaker/desktop action, service restart, cloud request or personal-state edit was performed during this review. The earlier schema-only synthetic probes are recorded in `2026-10-06_0235_Codex_AuditProtocolSchema.md`.

## Source receipt
These are exact on-disk SHA256 values at 2026-10-06T02:51:01.104678+09:00. They identify the reviewed snapshot, not runtime-loaded certification. Watcher timestamp edits can change byte hashes independently of behavior.

| Source | SHA256 |
| --- | --- |
| `workspace/nova_body/nova_runtime/conversation.py` | `557e450bb72052781e93f3e6a00b34a06b8bb83e3bf0ea9ee363a6b1a0c6b842` |
| `workspace/nova_body/nova_runtime/model_client.py` | `7d94bca14c2147f4a3ee027e153bbbd02bce16c199d74f84dd97b2111fc593aa` |
| `workspace/nova_body/nova_runtime/runtime.py` | `e389c78477c68b7a60f7917fe052391c83c0e95e8d221f39b19b9cad5d521c84` |
| `workspace/nova_body/nova_cortex/request_contract.py` | `d5918b6933ef1d76853e71592e011d23437f296d401b46be638f434550af1da2` |
| `workspace/nova_body/nova_cortex/audit_protocol.py` | `deb30a8793802d8c8e82d7f292a25c606d73d2904ecf306f687501445384c54b` |
| `workspace/nova_body/nova_cortex/witness.py` | `f0340d60e088cd5f51cc3c8122e67acca0720be11f17ea7001fe17302990f6a2` |
| `workspace/nova_body/nova_voice/nova.py` | `9723a28b4f2a5c3c99bbf4a1a5368dbce6e40bb6c344f4481f7fe5b6ff435125` |
| `workspace/general_tools/nova_chat/server.py` | `7e4068017ed3e349a6bb177928a5507d56ce06b4e1e84234da54a1ebe4a9aeb0` |

## Open / handoff
Root and the voice acceptance agent own the next matched recorded-audio/live-body run. They must evaluate follow-up completion, audit outcomes and actual latency separately from schema/transport correctness. No witness-policy relaxation or audio-success claim is implied by this review.
