<!-- @nova: Record the stale main-generation state diagnosis and bounded current-work snapshot repair. -->
# Current work step
**Summary:** The latest paired test admitted its follow-up correctly, but the main correction prompt retained an older request snapshot and initial NOW card. The body now supplies one current-state tail record to each main generation request. This is working-state maintenance, not a model-quality guarantee.

## Evidence and diagnosis
- Matching run `83471c68ae594781b754c9a6278cec60`, captures in `workspace/Temp/provider-diagnostics/voice-evidence-repair-20261006/`.
- Main capture `c293a38fa1084d6e9bb4c8229dc0d5d6.json`: index62 retains the original NOW/Last-human card, index64 correction contains only the initial request, index65 contains the actual follow-up. The first generated draft exactly repeats an earlier assistant response at index60. The actual historical transcript was not changed.
- The model never emitted the requested speak control in its first draft; no true continuation flag was lost by the code. Final audit already received both requests and nevertheless approved the omission. These are separate findings.

## Changed
- `workspace/nova_body/nova_cortex/request_contract.py`: `CurrentRequest.render_step` exposes exact admitted request text, committed output segments, turn/revision, compact completed-tool facts, and separately attributed latest attended context. It does not infer completion or declare the next candidate final.
- `workspace/nova_body/nova_voice/nova.py`: construct the snapshot immediately before main/retry provider calls, after applicable input/boundary handling. The snapshot is provider-only and context-anchored; it is never appended to private history or persistent state. Old NOW/correction snapshots are explicitly historical. System and prior history remain unchanged; frozen candidate audit requests remain unchanged.
- `workspace/nova_body/tests/test_generation_work_state.py`: seven isolated actual-stream tests, including correction plus pending follow-up, tools/phase attention, cancelled historical input exclusion, empty retry, retained continue choice, and context fitting.
- Existing request/voice tests inspect the actual correction before the new tail. The pressure fixture retains its original 1800-character allowance for prior context plus the exact new state anchor; raw observation clipping and receipt/input preservation remain checked.

## Verified
- **107 focused tests passed**, including the existing relocated-body subprocess fixture. This count includes seven new tests; nested subprocess cases are not counted again.
- Scoped `git diff --check` passed (only existing line-ending notices).
- No model/provider calls, services, audio, or Nova-owned state changes. No semantic live acceptance claim: repeated test history contaminated the paired case, and a fresh conversation plus substantive response review is still needed.

## Handoff
- Root owns Orient explanation/review updates and live evaluation; production changes are only `nova.py` and `request_contract.py` (both already fingerprinted).
- Routing is independently reviewing this narrow patch. No new classifier, witness protocol, generation cancellation, or generic retry loop was added.
