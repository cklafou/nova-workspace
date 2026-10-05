<!-- @nova: Record the scheduled code-health audit environment exclusion fix and isolated verification. -->
# Code audit environment exclusions
**Summary:** Closed the remaining local dependency-environment gap in the scheduled code-health audit. The separate witness development review remains open; no holdout or live model was used here.

## Did
- `general_tools/audit_scripts.py`: exclude `.venv` and `venv`; use one pruned walk for Python source, shell encoding checks and launcher entry-point discovery. Rejected trees are not traversed or read. Existing issue rules are unchanged.
- `general_tools/nova_sync/tests/test_virtualenv_exclusions.py`: add disposable checks for all three audit paths and an explicitly supplied environment root. Preserve adjacent `venv_tools` project source and a real project syntax-error finding.

## Why
The scheduled audit had been including installed voice dependencies, producing unrelated findings. Adding Git/sync exclusions alone did not change this separate collector.

## Verified
- 12 environment-exclusion tests pass (two new code-audit cases); source AST parsing and scoped diff whitespace check pass.
- Fixtures assert that dependency trees are never descended into/read and that a malformed ordinary project file still reports `SYNTAX`.
- No full audit of personal records, model/voice invocation, service restart, state edit or live process control was performed.

## Open / next
- Root owns Orient explanation/review updates and final integration verification. A new invocation of the scheduled audit loads these collector changes; historical audit findings remain historical.
- The open-dev witness review found candidate2's one false approval and distinguished parser-exhaustion abstention from a well-formed final verdict. Candidate3 policy development is owned by the other agent; no sealed holdout was opened.

## For Codex and Claude
The old `rglob` entry-point scan ignored directory exclusions entirely. Retain the shared pruned iterator in all three paths when extending the audit.
