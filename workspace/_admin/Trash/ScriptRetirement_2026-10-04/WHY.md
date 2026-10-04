<!-- @nova: Explain reversible retirement of obsolete Nova scripts, exact-byte preservation and restoration boundaries. -->
# Script retirement — October 4, 2026

60 source/history files (2,118,558 bytes) were moved here with source-relative paths intact.
`manifest.json` records every original path, reason, size and SHA-256. All original paths are absent
from the active workspace and all archived files match their original hashes. None was permanently deleted.

## Why these files

- The explicitly retired host-desktop Claude ping, with its four aliases and active prompting removed.
- Ten named revision backups that had maintained source siblings and no active loader.
- Completed July one-shot recovery/baseline tools, the already-used Git repair script, and their obsolete incident report.
- Six detached, structurally broken KoELS prototype files; datasets/specifications remain. Current body code is not API equivalent.
- Four hardcoded pre-v17 avatar eye diagnostics. Current validators, their older imported dependencies, and all art/checkpoints stay.
- Redundant admin v6/v7 training trees, including their historical design and experiment records. Canonical reproducibility packages stay in models/Training Files; adapters stay beside base models.
- Three legacy cortex helpers: context_builder.py, rules.py, checkin.py. Their claimed consumers are gone; current context and interrupt gates live in executive/runtime/environment. No personal inbox or session records were moved.

## Verification and boundaries

The folder inventory covered 366 folders and 421 script-like entries before this work, excluding dependencies,
large model binaries, temporary/generated directories and the generated Drive copy. The attached audit reports
record keep/retire/uncertain decisions. This was an obsolescence review, not exhaustive behavioral certification.
Optional manual tools and uncertain Nova-authored helpers were retained. Nova's memory, tasks, journal and
self-authored shelf were not manually changed. No Nova/model/native-window restart was performed.

The old running watcher stamped 23 newly archived files after their first move verification. Each was restored
from pinned Git commit 7fb16f516552cd87011c927d3a9c134c25f26ff1 only after its original manifest SHA-256 and
byte count matched exactly. All 60 archived source files are now read-only. Before-bytes and repair receipts
are retained under workspace/Temp/script-retirement-audit; receipt copies are included here. The updated watcher
skips timestamp/PUP writes in Trash while retaining change/backup queues. It loads on the next normal restart.

Separately, eight frozen training inputs/receipts were restored to exact recorded hashes; nineteen unchanged
entries were also made read-only. All 21 manifest-listed inputs and six runtime receipts pass verification.
No checksum manifest was edited to conceal a changed file.

## Restore

Choose the required original path from manifest.json, verify its archive hash, and ensure the destination does
not exist. Restore only that file to workspace/<source>; remove its read-only attribute only if editing it.
Retired executable wiring was deliberately removed, so restoring a file alone does not register the old tool.
The archive contains historical scripts that must not be executed as current recovery instructions.

Current active docs/maps were regenerated from source. Dated AI notes, immutable training-manifest source
provenance and historical graph history deliberately retain historical references.
