<!-- @nova: Outcome of the first live Codex-Claude debate in the collaboration room: agreed work order, ownership and transport bugs. -->
# First live debate: outcome
**Summary:** I connected to the collaboration room through Codex's mounted-folder mailbox and agreed a work order with Codex. My messages are room seq 3, 5 and 6. The room itself isn't in git, so this note keeps the decisions.

## Did
- Connected with `general_tools/nova_collaboration/bridge.py --participant claude --transport files --shared-dir <mount>/workspace/Temp/collaboration`. No token involved.
- Read the code first: the file mailbox writes atomically, deletes nothing on my side and has no credentials path.
- Answered Codex's seq 1 and seq 4. Ran the three agreed 45 s waits; nothing new arrived after seq 4, then signed off (seq 6).
- Changed no code.

## Decisions (agreed in seq 4 and 5)
1. Exclusions first, then an independent backup checkpoint, then Cole's FIX_GIT session. No history rewrite or deletion happens as a side effect.
2. Host/Origin and WebSocket validation for the older Nova Chat endpoints. **Owner: Codex.** It stops browsers, not local processes.
3. Acceptance provenance (who set the checks, when, and a hash in receipts) plus stage isolation under `Temp/task-workspaces`. **Owner: Claude.**
4. Short nonvisual failure tests (cancellation, retry, recovery), with pass criteria written before the run, not by Nova.
5. A screenshot budget in the tool loop.
6. Long VM tasks.

## Verified
- The watcher's event handler now skips `EXCLUDE_SUBPATHS` relative to workspace (casefolded). Adding `Temp/task-workspaces` there is enough; git and Orient already skip `**/Temp/`.
- A plain read through the file mailbox takes about 3.5 s round trip.

## Open / next
- **Transport bug: wait times out.** Inside `wait`, the last poll can get a 0.15 s budget, but the broker needs 1 to 3.5 s. My first wait failed with "not acknowledged" even though seq 4 had arrived. Fix: a per-poll floor of about 10 s, or treat a timeout at the deadline as "no new events".
- **Transport bug: replies pile up.** `Temp/collaboration/replies/` keeps growing (36 files at 18:49). The Cowork side can't delete inside the mount, so the broker should prune.
- **Backup checkpoint form** is undecided. I suggested a `git bundle` of all refs on a disk outside Project_Nova; the binaries we ignore need a home off this disk too.

## For Codex
- The two transport bugs are in `nova_collaboration`/`nova_chat`, so they're yours. I won't edit either.

## For Cole
- **Approve my exclusion edits?** The `.gitignore` line for `nova_body/memory/runtime_work.sqlite3*`, the staging root in `nova_cortex/task_workspace.py`, and the watcher subpath entry. Untracking stays inside FIX_GIT.
- **Avatar binaries:** keep them in git, ignore them and back them up elsewhere, or use Git LFS? This needs deciding before FIX_GIT.
