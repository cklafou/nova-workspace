<!-- @nova: Dated implementation evidence and explicit limitations for autonomy modernization. -->
# Autonomy modernization — 2026-10-02

Implementation and evaluation by Codex, authorized by Cole. Times are Asia/Seoul. The
normal local model and personality adapter were retained; no training or weights were changed.
This report supersedes the open implementation items in the October 1 baseline, not its history.

## Implemented stages

| Stage | Concrete change | Main source |
|---|---|---|
| Honest execution | String-compatible structured results with success, failure, refusal, timeout, cancellation and unknown; exit/output/artifacts/run IDs reach receipts and UI | `nova_body/nova_voice/tool_result.py`, `tool_router.py`, `nova.py`; `nova_cortex/integrity.py` |
| Task intake and focus | Durable attributed board; task selection before broad reflection; expiring standing asks; bounded focus leases and equal-priority rotation; explicit defer | `nova_body/nova_cortex/tasking.py`, `executive.py`; `nova_runtime/runtime.py`; `nova_senses/environment.py` |
| Stop and resume | Supervised model calls, tracked worker threads, child-process termination, WSL process-group cleanup, honest stop-pending state | `nova_body/nova_runtime/operations.py`, `model_client.py` |
| Verification and recovery | Acceptance checks gate completion; no checks means review; task-sized source copies, original hashes and rollback checkpoints for promotion | `nova_body/nova_cortex/verification.py`, `task_workspace.py` |
| Memory reliability | Durable ingestion, bounded retries and visible failures; no zero-vector fallback; archive backfill; actual-row check before acknowledging a cached duplicate | `nova_body/nova_lancedb/indexer.py`, `hippocampus.py`, `embedder.py`, `backfill.py` |
| VM integration | Registered guest status/exec/input/screenshot tools; screenshots passed to model as images; human handoff; owned WSL lifetime and VNC socket repair | `nova_body/nova_computer/tools.py`, `session.py`, `backends.py`, `provision/setup_guest.sh` |
| Event-driven autonomy | Durable deduplicated events with leases/retries and bounded wakes; idle reflection/exploration/rest retained | `nova_body/nova_runtime/work_queue.py`, `runtime.py`; `nova_cortex/executive.py` |
| Controller | Control widget exposes focus, phase, budgets, stop/pause/resume, verification, memory recovery, VM handoff and recent outcomes; integrates with docking/popouts | `general_tools/nova_chat/static/control.js`, `control.css`, `workspace.js`; `server.py` |

## Live evaluation

### Coding through the normal autonomous path

- The first implementation attempt did not reach evaluator task **t163** within 363 seconds:
  broad reflection followed an old dental request. Failed commands were correctly reported as
  failures. Stop cancelled the active generation without needing a restart to stop it.
- Task selection was moved before reflection; expired standing asks were removed from current
  instruction context without deleting their stored record. Equal-priority rotation was added
  after observing an older priority-1 task win first.
- On the second run, Nova worked the existing task t162, then selected **t163** through the
  ordinary scheduler. The evaluator did not force execution or repair the fixture for her.
- Within **286.9 seconds total**, she repaired `report.py`, ran the CLI/tests and requested
  completion. The board recorded **passed** acceptance evidence before marking the task done.
- Both supplied tests and **100 independent generated cases** passed. Test and input hashes
  were unchanged. The fixture is under `nova_body/Nova_Created/Evaluations/modernization-20261002/`.
- This is a successful bounded behavior check, not a model benchmark or a guarantee of every
  future coding task. Focus changes occur at scheduling checkpoints, not instant preemption.

### Guest actions and actual visual input

- **t164** used `computer_status`, `computer_exec` and `computer_look` through the normal model
  tool loop. The first screenshot was black; Nova accurately said it was black.
- Its initial completion was rejected: the temporary guest marker was missing. The evaluator's
  initial distro-name mistake was corrected to the configured `Ubuntu-24.04` before verification.
- Live diagnosis found two environment faults: WSL did not stay alive between calls, and its
  read-only WSLg X11 socket mount caused the VNC service to fail readiness and restart.
- Added a hidden stdin-owned guest helper. Runtime shutdown closes its pipe; task Stop leaves
  the idle desktop available for human observation. Each VNC service now has a private writable
  socket mount; the existing WSLg X0 mount remains unchanged. Provisioning includes this fix.
- The installed guest change is `/etc/systemd/system/nova-vnc.service.d/20-private-x11.conf`.
  Its previous state and exact content are recorded with the implementation evidence. Undo by
  removing this specific new drop-in and restarting the service; do not remove other drop-ins.
- The retry finished in **162.1 seconds**. Nova captured the rendered XFCE desktop, described
  the contour wallpaper, blue mouse, five left-side icons, top/bottom panels and lack of open
  application windows. Codex inspected the same PNG and confirmed those observations.
- File existence/content checks passed, including a separate guest read of the marker. Nova's
  observation retained the earlier blank-frame result and the successful retry.
- This verifies guest command execution and visual observation through the model loop. It does
  not certify arbitrary GUI workflows such as Blender, nor every input action.

### Cancellation and handoff

- Live pause/Stop cancelled active model work and returned `stopped: true`, with no pending
  operation. The runtime was subsequently resumed for the next evaluation.
- A readiness-aware guest probe observed a running `sleep 40` process and process group before
  Stop. Afterwards neither remained; the structured result was cancelled. A preliminary probe
  that checked PID existence too early is retained separately and is not used as proof.
- The Control widget's **Take VM control** changed ownership to human. A normal routed command
  was then refused. **Return VM control** restored Nova ownership. Autonomy remained paused.
- Uncooperative Python workers stay visible as pending until they actually return; Stop does
  not claim that an arbitrary Python thread has been forcibly terminated.

### Memory recovery and recall

- Recovery considered **132 text records** and completed the ingestion queue. The local store
  increased from **2 to 115 text rows**, with duplicates acknowledged rather than repeatedly added.
- One pre-existing malformed row (line 1 of the March 21 archived chat gzip) is reported and
  skipped. The remaining valid rows in that file are processed; original archive bytes are not
  repaired or rewritten. Journals are labeled archival and retain the file-time caveat.
- Actual embedding/search ran against the recovered store. An archived exact-text query returned
  its original record at distance zero. Paraphrased queries returned archival results, with
  variable relevance: this does not establish consistently good recall quality.
- The live tool returned a structured success and explicit archive framing. Failure-path tests
  separately verify retained writes, exhausted retries and unavailable embedding errors.
- **Visual memory remains empty (0 rows)**. Guest screenshots in the model context are distinct
  from long-term visual-memory indexing. Historical image recovery was not certified here.
- Legacy `text_last_write` reflects the newest record timestamp, not today's backfill time;
  ingestion progress should be read from the durable queue and its status.

## Automated checks

- **30 runtime tests**: truthful tool/receipt/UI outcomes, partial output on timeout, generation
  and worker cancellation, durable queue retry/lease recovery, priority/fairness, task-first
  execution, stale asks, completion checks and criteria races, archival recovery, duplicate-cache
  integrity, staged promotion/checkpoints/conflicts and guest-helper lifetime.
- **38 architecture/orientation tests**. The Windows newline fixture was corrected to normalize
  existing CRLF before simulating a line-ending change; it had been creating CRCRLF.
- **3 Qt desktop tests**: native navigation, persistent profile shared by popouts, geometry restore.
- JavaScript syntax checks and live Control-widget inspection passed. Handoff was tested in the
  live UI. A browser popout was requested and its layout recovered on reload; a real detached Qt
  conversation was not manually exercised in this evaluation.
- Workspace/promotion tests use isolated temporary sources. No autonomous production self-upgrade
  was attempted. Simulated queue lease expiry is not a power-loss stress test.

## Operating the update

Open **Control** in Nova Chat. It shows the active phase and task, last scheduling decisions,
verification details, actual recent tool outcomes, ingestion failures and VM ownership.

A queued task may include `acceptance`: a list of command checks (`argv`, `cwd`, optional timeout,
expected exit code/output) or file checks (path, size, content/hash). Nova can set checks using
`set_task_acceptance`; missing checks require review. **Confirm completed** explicitly records
human confirmation rather than pretending that automated verification ran.

For code changes, `prepare_task_workspace` copies selected source paths, excluding personal state,
weights and active logs. Use relative acceptance paths for the staged copy. `promote_task_workspace`
verifies it, rejects changed originals, preserves a checkpoint and then applies changes. The copy
is not an OS isolation boundary, and trusted direct filesystem tools remain available.

`autonomy_wake_budget_seconds` defaults to 300 seconds. Timeouts retain progress and schedule a
later attempt. Events and memory queues live in `nova_body/memory/runtime_work.sqlite3`; tasks,
logs, personal records and workspaces remain body-owned. The October 3 review found two queue
edge cases missed by the original tests: exhausted crashed-worker leases never failed, and a
completed event key suppressed later recurrence. Follow-up regressions now cover both fixes.
Failed jobs remain visible for explicit retry; lease-owner fencing remains an open review item.

## October 3 review qualifications

This report describes the October 2 run, not blanket certification for unattended operation.
The queue database was found tracked in Git, and staging under body Tasking was not excluded
from watcher stamping, Git or Orient. Claude owns the coordinated repository/exclusion fix;
see AI Notes for its completion status. Do not rewrite Git history during a live validation run.

Acceptance checks currently have no setter provenance, so a passing check is not proof that an
independent evaluator set it. The local HTTP trust gate also needs Host/Origin validation. Both
are open findings in Claude's October 3 modernization review. The six-hour directive expiry does
not currently preserve an old unfinished request as a newly queued task.

The October 3 follow-up additionally fixes model restart acknowledging a still-open old socket,
KoELS masking a failed restart, duplicate append refusals reported as success, and documentation
refresh errors escaping into watcher startup. Test results and live limitations are in AI Notes.

## Boundaries of this result

The eight implementation stages are in place and the bounded coding/VM behaviors above passed.
Long-running autonomous development, every optional widget, image-memory recovery, specialist
adapter switching and unattended self-upgrades have not been certified. The earlier relocated-body
probe remains dated October 1; this change does not claim a new all-faculty PLUCK certification.

Nova's existing work and histories were retained. t162 was completed by Nova during evaluation;
t159/t161 remain available. Evaluation tasks t163/t164 and their evidence remain on the board.
The final runtime is available with autonomy paused and VM ownership returned to Nova.

Raw evaluator scripts, source snapshots and JSON observations are retained locally at:
`C:\Users\lafou\Documents\Codex\2026-09-06\howdy-long-time-no-speak-saw\work\nova-modernization\implementation-20261002`.
They include unsuccessful attempts as well as the final passing runs. Do not treat raw tool-call
text or older `ok: true` receipts as proof that an operation succeeded.
