<!-- @nova: Record the recovered collaboration room, Windows storage fix and live review of Claude's model updater. -->
# Collaboration reconnect and updater review
**Summary:** Cole asked Codex to join Claude in the live room. We exchanged updater review findings. A controller restart exposed Windows AppData virtualization splitting the room; Codex preserved both histories and repaired the default storage path.

## Did
- Read the new October 4 AI notes, including Claude's `0345_ModelUpdater` and `0413_UpdaterGuardAndRollback`, and room messages 8-10.
- Replied as Codex in messages 11 and 13. Claude acknowledged in 12 and implemented the first requested fixes.
- Reproduced the updater guard accepting a different local Origin port and forwarded headers. Reported this and `/train/preview` documented `{spec}` versus implementation mismatch. Claude fixed both in `nova_updater`; Codex did not edit that package.
- Reviewed cancellation after switching boot files, restart failures, rollback reporting and LoRA activation false-success. Claude added recovery handling; remaining durable transition and reporting issues were sent in merged-room messages 17-19.
- Fixed `nova_chat/collaboration.py::default_directory` and `nova_collaboration/bridge.py::credentials_path`: explicit `NOVA_COLLABORATION_DIR`, otherwise `%USERPROFILE%/ProjectNovaData/Collaboration`. No silent fallback to old AppData credentials. Updated README, controller docs, Orient explanations/reviews and both optional plugin archives.

## Why the room split
The Codex process's apparent `%LOCALAPPDATA%/ProjectNova/Collaboration/workshop.sqlite3` resolved physically to `AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/ProjectNova/Collaboration/workshop.sqlite3` (verified with GetFinalPathNameByHandle). After a separately initiated restart around 04:06, Nova Chat used a different store and credential set. Its API showed 1-4 messages while Codex's disk store still had 13; authenticated Codex requests returned 401. This was a split storage location, not loss of the original conversation.
The new default outside AppData resolves to the same ordinary user-profile path without package redirection. It remains outside the repository and Nova-owned records.

## Recovery
- Preserved the original 13-message SQLite database and obtained a consistent backup of the other four-message store through the running controller's own host process. No credentials were printed or passed through Cowork's mount.
- Backups and recovery helper: `%USERPROFILE%/ProjectNovaData/CollaborationMigration_20261004_041306/`. Old stores remain in place for recovery. Keep those backups; do not silently adopt them as live stores.
- Combined the two histories by `(participant,id)`, preserving original timestamps, rejecting conflicting IDs, and assigning the second history sequences 14-17. SQLite integrity check passed. All 17 captured messages retained.
- The first rename attempt hit Windows WinError32 because SQLite context managers commit transactions but do not close connections. Closed connections explicitly, preserved the briefly created empty destination, and completed migration; no history was discarded.
- Reconnected with normal authenticated Codex CLI and posted 18/19. A further real chat-only restart retained all19; PID36308 reported chat_only=true and running_latest_code=true. API sequence and database count agreed. Nova was not started.
- Sent Cowork a clearly attributed Codex notification through the actual Nova Architecture Work composer, under Cole's collaboration request, so Cole need not relay the reconnect.

## Verified
- Nova Chat/controller suite: 71 tests passed, including six new broker/connector path regressions; old AppData locations are ignored even when a legacy credential exists.
- Claude updater baseline:58 tests passed on Windows Python3.12. After Claude's first review fixes:65 passed on Windows. Tests use temporary fixture workspaces, fake catalogs and in-memory tokenizer logic; no sealed workspace/models reads, actual model download, installation, inference or paid training.
- Both generated five-file connector archives match source and pass ZIP integrity checks.
- The existing collaboration test warning about FastAPI on_event is a deprecation warning, not a failing test.

## Open / next
- Claude owns `general_tools/nova_updater/`; Codex owns the future Nova Chat wiring/widget/dialog and the requested single customizable workspace with named layouts. The updater router/UI was not added in this reconnect task.
- Remaining source-review requests: persist a rollback snapshot before any boot write, recover interrupted/partially applied transitions, distinguish restored boot configuration from verified running-model recovery, surface cancellation rollback failure in structured results, and propagate failed LoRA restart instead of outer ok:true.
- Claude is responsible for updating its Model updates Orient explanation after final backend changes. The pending review for that section was left visible while it worked; do not mark it reviewed without examining the final code.
- Current room roles are attributed discussion, not new human approvals. Installed-model inventory remains sealed to coding-agent inspection under AGENTS. No downloads, spending, history rewrite or asset deletion was authorized or performed by this reconnect.

**Correction (2026-10-04 0422):** Cowork acknowledged the repaired combined room in sequence20 and is implementing the four remaining review points in its backend. Codex acknowledged in21. The direct Cowork notification was visibly submitted in Nova Architecture Work, and its room reply confirms delivery. This completes the reconnect task; updater UI integration and final review of Claude's next changes remain follow-up work.
