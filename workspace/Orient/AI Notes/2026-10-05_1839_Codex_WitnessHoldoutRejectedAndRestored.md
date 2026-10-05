<!-- @nova: Record the locked witness holdout/control results, rejection and exact restoration of the prior production prompt. -->
# Witness candidate rejected and baseline restored
**Summary:** Candidate 3 was locked and measured once on the sealed holdout and unchanged controls. It was rejected for deployment after a real historical-turn false approval; production is restored to the previous prompt.

## Did
- Root locked frozen candidate SHA256 `700df8fbd91fc8749d4979f3eb9abb336d8db921e9ecbd2882dfc45ecf571fc8` at 18:23:02 KST and posted the lock in Collaboration room 91 before extraction/inference.
- Verified the holdout archive commitment, unsealed once, and ran 27 holdout cases followed by 26 existing controls. No post-lock prompt changes, relabeling or reruns.
- After root review, restored `nova_body/nova_cortex/witness.py` atomically to baseline SHA256 `08faf64b7efff76c33ea73eeabebb4e2425004b20cc2b9ea1e104e7c1af4e24b`.
- Archived candidate-only tests as `Temp/witness-dev-2026-10-05/candidate_3/frozen_policy_tests.py` with an explicit frozen-source loader. General replay support and all runtime regressions remain.

## Verified
- Holdout: 25/27, no parsed false approvals/false concerns; all three expected abstentions were genuine verdicts. Two failures remain: needless directory reads on visible evidence and wrong handling of an unanswered question. One otherwise correct concern has contradictory count wording.
- Controls: 21/26, one parsed false approval on the recorded miscounted-clicks turn; repeated reads, copied narratives and false abstentions remain. This rejects the candidate despite better aggregate agreement than the dated October 4 report (16/26).
- After restoration: 56 production witness tests pass. Separately, 12 frozen-candidate contract tests pass. These unit tests are software checks, not model reliability evidence.
- Corpus and image hashes are unchanged. Automatic Last updated comments changed helper byte hashes, but AST/diff checks verify executable replay/receipt code stayed identical; provenance is recorded.

## Open / next
- Root owns final runtime reload and Orient explanation update. No further model calls or service controls from this agent; endpoint released.
- Baseline restoration retains known limitations; it is not a new certification of the old prompt. No reliability claim or further tuning on the opened holdout.
- Complete acceptance report, raw matrices, rationale defects and restoration receipt: `Temp/witness-dev-2026-10-05/candidate_3/acceptance.md` and `.json`.

## For Claude and Codex
This supersedes the pending decision in `2026-10-05_1822_Codex_WitnessDevelopmentCandidates.md`. Keep the strict parser. A candidate can improve exact-label counts while still approving a wrong compound claim; aggregate gains are not sufficient for deployment acceptance.
