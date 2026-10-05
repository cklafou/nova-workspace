<!-- @nova: Record witness development candidates 2 and 3, their bounded comparisons and unresolved evidence errors. -->
# Witness development candidates
**Summary:** Prompt-only candidates improved several development judgments, but candidate 3 still has malformed audits and false abstentions. The strict parser is unchanged; the holdout has not been opened.

## Did
- Updated `nova_body/nova_cortex/witness.py`: independent auditor role, speaker-relative attribution, object/value binding, visible-source versus claimant separation, and incomplete/refused evidence policy. Only audit prompt construction changed.
- Added policy-contract regressions in `nova_body/tests/test_witness_policy.py`.
- Froze candidates and same-model/adapter metadata in `Temp/witness-dev-2026-10-05/candidate_2/` and `candidate_3/`; reports and candid analysis are preserved alongside them.

## Why
Candidate 1's malformed approval text concealed two bad judgments; loosening the parser would have exposed them as false approvals. Changes target evidence sufficiency and response consistency without relaxing parsing or changing labels.

## Verified
- 68 isolated witness tests passed; 12 policy tests repassed after the final pre-run review adjustment.
- Development only, fixed 27 cases and runtime sampling/three reads: baseline 18/27, candidate 1 21/27, candidate 2 26/27, candidate 3 25/27. One run per variant is not a reliability estimate.
- Candidate 2 still falsely approved omitted receipt contents. Candidate 3 correctly abstained there and produced zero parsed false approvals, but another omitted-frame case still returned unsupported conversational prose which the parser safely rejected.
- Candidate 3 also exhausted reads for an already visible paused screen and missed an unanswered human question. Format 25/27; median/p90 3.31/17.26s; total request latency 175.83s.
- Development fixture hash, parser, evidence caps and read loop are unchanged. No personal records, services or model configuration were changed by this work.

## Open / next
- Root owns acceptance/lock and final Orient explanation updates. Candidate 3 has not earned protocol/abstention criteria; preserve its limitations rather than claiming safety from the aggregate score.
- No holdout inspection or run until an explicit candidate lock. Current source matches frozen candidate 3 hash `700df8fbd91fc8749d4979f3eb9abb336d8db921e9ecbd2882dfc45ecf571fc8`.

## For Claude and Codex
- Read `Temp/witness-dev-2026-10-05/candidate_3/analysis.md` for exact observed failures and comparison. Strict parsing is still protecting unsupported outputs; do not extract PASS from free prose.
