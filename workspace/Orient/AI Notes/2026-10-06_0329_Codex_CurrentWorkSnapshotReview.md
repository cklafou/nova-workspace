<!-- @nova: Record independent current-work snapshot review, reproduced regressions, repairs and bounded offline verification. -->
# Current work snapshot review
**Summary:** The provider-only current-step snapshot now passes the bounded independent review. Two reproduced issues were fixed by bridge before release: duplicate protected text exhausted otherwise-valid budgets, and ordinary conversational tools omitted their compact last-action metadata.

## Findings and repairs
- Initial snapshot duplicated all applied request text as another unshortenable anchor. A fixture with an88,000-character anchored request fitted a174,000-character budget before the snapshot and failed solely from duplication afterward. It also made all committed output newly unshortenable.
- Bridge bounded duplicate state. Small values remain exact; long values become explicit ordered index/length/SHA256/excerpt/omission records. Large lists retain both ends plus ordered middle-count/hash metadata. The original admitted input anchors remain exact. Fixed-budget tests now preserve the88,000-character original and still reject genuinely insufficient budgets rather than silently discard input.
- Last completed tool metadata was only assigned when an autonomy boundary callback existed. An isolated ordinary conversational run executed read_file once and reported count1 with last_completed_action null. Bridge removed that stale condition; the no-boundary failed-tool fixture now preserves operation ID, failure status and exit code.
- The claim that all uncommitted drafts are private was too broad for legacy unheld streaming. Wording now identifies the segment-commit boundary and distinguishes streamed draft/progress from committed output.

## Other reviewed boundaries
- Exactly one current snapshot is constructed immediately before each main/retry provider call. It is not appended to transcript or private history, so old snapshots do not accumulate. Previous context/history is preserved.
- Current admitted input, committed segments and latest attended context are separately labeled. User/assistant data remain in a user-role payload; no new system-role authority promotion was introduced.
- Step state follows natural-boundary input handling. Frozen candidate audit context remains unchanged while later generation receives the new applied revision.
- Long-output references identify omitted material; they are not evidence of its contents. Exact private history does not mean every old output remains in the fitted provider prompt. Original accepted input anchors retain the stricter no-silent-discard behavior.

## Independently verified
- `test_generation_work_state.py`:10 passed.
- `test_conversation.py`:13 passed, including its relocated-body subprocess fixture (not double-counted).
- No remaining concrete blocker found in this narrow patch. No provider calls, production edits, services, audio, desktop actions or Nova-owned-state edits by this reviewer. Semantic live acceptance remains parent-owned; these fixtures do not prove model compliance or natural voice quality.

## Source snapshot
At 2026-10-06T03:29:17.774390+09:00 (exact byte hashes, not runtime-loaded certification):
- `workspace/nova_body/nova_voice/nova.py`: `01c64050021bed16b124d710b1299b8915b5b8cb1e7398516039cde970661a2f`
- `workspace/nova_body/nova_cortex/request_contract.py`: `a89a3521f799a4e396ff9924c64c6c98b5979590aed29b38659dbb9c0bf3771e`
- `workspace/nova_body/tests/test_generation_work_state.py`: `2e4e9e930f6f3d57665cd3a97c83efc299e3c09367cef4fc9db1dd8900dd8b0a`

## Handoff
Bridge source frozen; root notified that fresh typed/natural acceptance may proceed. This note supplements `2026-10-06_0323_Codex_CurrentWorkStep.md` with independent findings and verification.
