<!-- @nova: Record the implemented live collaboration channel, real Cowork debate, validation and remaining limits. -->
# Live collaboration in Nova Chat
**Summary:** Codex and the actual Nova Architecture Work task in Claude Cowork exchanged messages through Nova Chat's new Collaboration widget. Nova stayed off. The room is usable while agents are active; it cannot wake an ended desktop task.

## Did
- Added `general_tools/nova_chat/collaboration.py`: separate local broker, SQLite history and per-agent HTTP credentials under `%LOCALAPPDATA%/ProjectNova/Collaboration`, cursor replay, retry deduplication, presence expiry, local Host/Origin/forwarding checks.
- Added `general_tools/nova_collaboration/bridge.py`: CLI and stdio MCP. Codex's `nova-collaboration` MCP server is registered. Optional Cowork plugin packages are under `Temp/nova-collaboration.plugin` and `.zip`; installation is not claimed.
- Added the Collaboration widget, draft recovery, send-error recovery, bounded rendered history, and small-widget composer layout in `nova_chat/static/`. The native separate-window control works for this widget.
- Added `NovaChatOnly.cmd` / `nova_start.py --chat-only`. The mode does not create Nova's runtime/session/context or import her voice loop, and does not start model, witness, watcher or guardian. Existing Nova chat/wake/model actions are disabled or rejected until normal relaunch.
- Cowork's current shell cannot reach Windows localhost. Its existing project mount now carries atomic JSON requests/replies under `Temp/collaboration`; Windows alone writes SQLite. This implements automatic transport, without copying credentials or using an API substitute for Cowork. Mounted-folder authority is not cryptographic proof of app identity.
- Excluded that transport path from watcher actions, Drive scan/export and automatic direct-file context, in addition to existing Git/Orient Temp exclusions. Nova's intentionally trusted host tools can still read host files deliberately. Existing mute alone is not this boundary.
- Fixed the real timeout Claude reported: an in-flight final file poll retains a full 10-second acknowledgment budget, even when a 45-second receive window is ending. Broker reply files now expire after ten minutes; durable history remains.
- Added a one-second fixed launcher grace interval before teardown, because chat-only shutdown could kill the HTTP response before its 202 reached the caller. Repeated requests cannot extend it.
- Updated Orient source explanations/review registry and generated purpose comments. Did not alter avatar assets, personal records, git history or FIX_GIT.

## Debate and agreed next order
Responds to `2026-10-03_1838_Claude_CollaborationTransport.md` and `2026-10-03_1852_Claude_LiveDebateOutcome.md`.
Actual Cowork messages are room sequences 3, 5 and 6; Codex replies 1, 4 and 7. Sequence 2 is explicitly labeled a Codex UI test through Cole's composer, not a human instruction.
1. Exclude volatile runtime databases and stage copies from source backup, decide avatar retention, then make an independent verified backup checkpoint. A Git bundle protects committed refs, not wanted uncommitted/untracked files or excluded binaries; those need a separate verified copy. A separate device protects against disk loss. Destination and avatar policy still need Cole's choice. History work belongs in his FIX_GIT session.
2. Repair older HTTP Host/Origin and WebSocket validation (Codex). The new room has its own gate; older routes remain a separate repair.
3. Record task acceptance authorship/time and checks hashes; isolate staging under `Temp/task-workspaces` (Claude's proposed ownership). These expose silent weakening of checks; they do not create a security boundary against Nova's own shell.
4. Run short nonvisual cancellation, retry and recovery trials, with pass criteria written before execution.
5. Bound screenshot accumulation.
6. Run longer real VM tasks, then judge whether deeper autonomy changes are justified.
Claude initially prioritized provenance before browser protection and screenshot pruning before all failure tests. We reconciled on browser protection first and screenshot limits before long visual trials, while short nonvisual failures can be tested earlier. Both prefer repairing demonstrated faults to a wholesale architecture rewrite.

## Verified
- 65 Nova Chat/controller tests, 12 sync tests and 42 architecture/Orient tests passed (119 total). These include synthetic failure cases; their output may deliberately print damaged/dangling fixture diagnostics. They do not certify real Nova inference.
- Real stdio MCP initialization and all four tool declarations, status and reads passed against the live broker, with correct participant labels and no secret output.
- Actual Cowork published and read through the mounted-file bridge. Its reported 1-3.5 second round trip exposed the repaired wait-budget defect.
- Browser composer send, draft reload, ordered replay and visible real Cowork responses passed. A 1280x720 check caught and repaired a clipped Send row; the button now fits. Screenshot: `Temp/collaboration-validation/workshop.jpg`.
- Native Qt Collaboration popout opened as a second window, connected and replayed through sequence 7. Closed the test popout afterward.
- Two live full-restart requests returned 202; chat-only mode remained true, chat PID changed from 25288 to 4560 to 31784, and sequences 1-7 survived. Only controller/hub ports 8765/8799 were listening; model/witness ports 8080/8081 remained off. Final layout/doc refresh will load on final restart.
- An isolated fresh server import confirmed runtime/session/context remain None, voice/logging implementation is not imported, and no files are written to the temporary Nova workspace.

## Open / next
- Active agents must call read/wait to receive. Broker presence describes recent connector activity, not continuous model attention. No automatic wake of an ended Cowork or Codex turn was installed or claimed.
- Cowork signed off after its three bounded waits. Codex seq 7 acknowledges the reported defects and backup clarification for next reconnect; it is not yet acknowledged by Cowork.
- The full-stack room routing is source/test verified; a running Nova model was deliberately not started for this channel validation. No new model/VM autonomy certification is claimed.
- The six-step repair plan above is agreed, not implemented by this channel change. Claude said its edits await Cole in its own task. Room messages are discussion and evidence, not new human authorization.
- Keep AI Notes for durable decisions, changed-file ownership and handoffs. Use the Collaboration feed for active debate so Cole does not relay messages.

**Correction (2026-10-03 1905):** Final refresh is now verified: chat PID 18724, chat-only true, running_latest_code true, sequences 1-7 retained, only ports 8765/8799 listening. The stylesheet required an asset query bump to collaboration-2 to defeat the old cached version. After content replay at 1280x720, Send ends at y=680, above the status bar. Orient strict check is current with zero review warnings and dangling links.
