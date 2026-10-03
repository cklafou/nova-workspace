# Orient Review — how Codex did
_Last updated: 2026-10-03 08:36:07_
_Claude, 2026-10-02. Read-only review of `workspace/Orient/` + its generator
`general_tools/architecture_map/orient.py`. Every claim was checked against source, git
history, or a live run of Orient's own fingerprint function. Canonical copy also lives in the
Claude project as `claude/Orient_Review_2026-10-02.md`._

## Criteria (Cole)
1. A simple, single source of truth for Nova.
2. Gives humans and AI all the context they need.
3. Updates itself when changes are made, without manual intervention.

## Verdict: strong B. Excellent engineering and writing; the self-updating claim is only half true.

## Keep
- Shape: 11 loose root files -> 4 entry docs (README/ARCHITECTURE/OPERATIONS/INDEX) + Architecture/.
- Generator: content-addressed SHA-256 (no rewrite when unchanged), stores doc hashes and
  self-heals hand edits, atomic_write, secret-safe, prunes sealed models/ before descent,
  derived tables (faculty counts, registered tools, 60 HTTP routes), tested.
- Writing: calibrated — separates "exists" from "verified". OPERATIONS' "Test meaningful
  behavior" protocol is exactly right.
- Body/Orient split: SELF = her self-model (body); Orient = the map of her for developers.

## Criterion 3 — PARTIAL (most important)
3a. STALE RIGHT NOW. Orient's own fingerprint: generated 2026-10-01T11:18:34Z, stored input
    5d6bda50..., current df4e2271... — 14 source files changed (4 new: verification.py,
    operations.py, work_queue.py, ...). refresh() only runs inside Nova Chat (server.py:1111,
    every 30 s) or the watcher (watcher.py:216); neither is running.
3b. ALL NARRATIVE IS HARDCODED in orient.py (e.g. orient.py:189, the PURPOSES dict) and gets a
    fresh "_Generated <now>_" on every regeneration. ARCHITECTURE calls a durable event queue,
    task leases and explicit success criteria "the next architecture steps" — Codex is building
    those today. Once they land the doc will keep calling them future work under a new date.
    A fresh date on stale prose signals false freshness.
3c. Architecture/ (index.html, architecture.json, SVGs, INVENTORY.md, Calls_Order.md,
    Calls_Master_Index.md) is manual-only (REBUILD_MAP.cmd, calls_order.py), all dated 09-30,
    and nothing tells a reader it is on a different freshness regime.

## Criterion 2 — GOOD, with real losses
- SECURITY.md (11 KB threat model) -> one paragraph; code still points there
  (server.py:133, principals.py:42).
- TUNABLE_VARIABLES.md convention gone; server.py:374 renders "Convention:
  Orient/TUNABLE_VARIABLES.md" in the Variables page Cole sees.
- NOVA_CREATED_TOOLS.md catalog gone (Nova used it, 08-02 shelf audit).
- GOTCHAS #6 "Don't feed her her own voice" — 0 matches in new docs; directly relevant to the
  10-01 baseline failure ARCHITECTURE reports.
- Six dangling live pointers: principals.py:42, tunables.py:6, server.py:133/325/374,
  audit_scripts.py:723.
- OPERATIONS says old fragments are "in quarantine"; that folder is no longer on disk.

## Criterion 1 — MOSTLY, except INDEX
INDEX.md: 618 entries, 0 descriptions; 13 backup files listed as canonical; "Project entry
points" appears twice (sort-grouping bug) and the first copy omits nova_start.py — the real
launcher. Fix: derive one-line purposes from the existing `# @nova:` headers.

## Recommendations (order of value)
1. Hand-written sections declare the sources they describe + a reviewed date; generator emits
   "REVIEW NEEDED — <file> changed since this section was reviewed" when those sources change.
2. Refresh on every commit from any agent (pre-commit hook / watcher commit path) + a test that
   refresh() returns changed=False on a clean tree — stale docs fail the check.
3. Link check for Orient/<name>.md references; fail on dangling; fix the six.
4. INDEX: descriptions from @nova headers, exclude backup suffixes, group root files once.
5. Restore threat model, tunables convention, GOTCHAS #6 into OPERATIONS; derive the
   Nova_Created catalog from forge discovery.
6. Label Architecture/ as on-demand, or auto-rebuild it after gitignoring its 5.6 MB outputs.

## Side findings
A. _admin/Trash/ empty on disk (modified 2026-10-02 13:19); git HEAD still holds 374 files in
   6 quarantine folders. Recoverable from HEAD; cause unknown; not restored without Cole's OK.
B. origin/master still at a64b1dad89 (2026-08-06). FIX_GIT.cmd never ran (5 GB tar still in the
   13 unpushed commits); watcher's last commit 2026-10-01 12:22 KST. Nothing since August has
   left this machine via git.
