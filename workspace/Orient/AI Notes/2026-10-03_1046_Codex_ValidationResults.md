<!-- @nova: Codex's October 3 Windows regression, live Nova and controller validation results, fixes and remaining gaps. -->
# October 3 validation results
**Summary:** 108 automated tests pass on Windows. Real controller restart, model-only restart, Nova's host/VM command execution, screenshot observation, handoff, terminal output, widget population and session persistence were exercised. This is not blanket certification for unattended autonomy: the remaining findings below are real.

## Did
Read Claude's `2026-10-03_0958_Claude_OrientAndSyncHandoff.md` and `2026-10-03_1027_Claude_ModernizationReview.md`, plus the shared note rules. Earlier ownership response: `2026-10-03_1033_Codex_ReviewFollowup.md`.

Fixed these reproduced defects, with regression cases:
- `general_tools/nova_chat/server.py`: `/api/version` now compares normalized SHA-256 source contents. Same-size/same-timestamp code edits are detected; watcher timestamp headers and CRLF changes do not cause false restart warnings. Added missing critical watched sources. This watches selected files, not every imported dependency.
- `general_tools/architecture_map/hooks/pre-commit` and its installed `.git/hooks/pre-commit`: stage only the four generated documents and generated inventory. The old hook silently staged unfinished AI notes/evidence as well.
- `general_tools/architecture_map/orient.py`: malformed review JSON/schema fails checking/publication instead of silently suppressing all warnings.
- `general_tools/nova_sync/watcher.py::build_file_index`: catch/report Orient failures and continue autosave. Claude correctly caught this interaction with the new strict registry check.
- `nova_body/nova_runtime/llama_control.py`: wait up to ten seconds for the old model socket to close before stop/restart can report success; do not convert a no-op Start into a successful restart. Preserve the independent witness. Autostart retains an explicit `started: false` result.
- `nova_body/nova_runtime/koels_equip.py`: propagate failed/skipped restarts rather than returning outer `ok: true`.
- `nova_body/nova_voice/tool_router.py`: duplicate-heading/text append refusals now have `status: refused` and `ok: false`.
- `nova_body/nova_runtime/work_queue.py`: five expired worker leases become visible failures; a completed event key can recur with a new job/payload while preserving its old completed record. Outstanding jobs still deduplicate. Failed jobs remain for explicit retry.
- Added regression coverage in body `tests/test_review_followup.py`, controller `tests/test_source_fingerprint.py`, architecture `test_review_registry.py`, and sync `tests/test_updates.py`.
- Added requested purpose comments to `static/control.css` and `tool_router.py`; updated CONTROLLER, Orient source explanations, lessons, review baselines and dated modernization evidence. The six-hour directive expiry and open verification/storage qualifications are now explicit.

## Why
The first suite passed but did not cover every failure mode. New failing tests reproduced Claude's lifecycle/queue/outcome/watcher findings before fixes. Startup fingerprints and independent receipts were used to distinguish code on disk, code loaded, model narration and actual execution.

## Verified
| Area | Evidence | Result / limits |
|---|---|---|
| Runtime | `python -m unittest discover -s nova_body/tests -v` | 37 passed, including real subprocess timeout/cancellation in isolated fixtures |
| Architecture/Orient | `python -m unittest discover -s general_tools/architecture_map -p 'test_*.py' -v` | 42 passed |
| Controller/Qt | `python -m unittest discover -s general_tools/nova_chat/tests -v` | 22 passed; includes three Qt logic/profile/geometry tests |
| Sync/identity/hooks | `python -m unittest discover -s general_tools/nova_sync/tests -v` | 7 passed in disposable Git repositories; no real push/history rewrite |
| Syntax | Python parsing + Node `--check` | 11 explicit Python targets, two JS files and seven inline script blocks; newly changed runtime modules also imported by tests |
| Orient health | `orient.py --check --strict` | Current, no pending prose review flags or dangling references at final check |
| Full restart | Actual Services button, twice | Old stack exited; new launcher/chat/model PIDs; browser reconnected and watched source hashes match disk |
| Model-only restart | Actual Services button after the socket-wait fix | Main PID changed 35248 to 23484; witness PID 36948 stayed healthy. Model finished loading and returned healthy |
| Normal Nova model/tool loop | Attributed chat session `Codex validation 2026-10-03` | Host and VM arithmetic commands actually executed; structured receipts success/exit 0. Guest screenshot actually created, passed to Nova, independently inspected and matched her description |
| Terminal | Actual UI command | Correct arithmetic output displayed |
| Human VM handoff | Control buttons + actual tool-router probe | Owner became human; routed action refused; owner returned to Nova |
| Widgets | Library opening + visible content | Services, Control, Conversation, Sessions, Tasks, Generation, Profiles, Activity, Thoughts, Files, File viewer, Terminal, Preview, Perceptions, Pipeline, Live log, Console, System and Variables displayed appropriate live data/empty states. File viewer loaded README. System showed current runtime and two-GPU telemetry |
| Preview | Actual embedded HTML page | Nova's variables page rendered. A raw JSON health endpoint was blank in this embedded browser, so it is not counted as a Preview success |
| Conversations/appearance | Actual UI close/reopen, rename and reload | Closed test conversation remained in history and reopened; name and density persisted. Test density restored to Comfortable |
| Drive read export | Fixture update/delete/dedupe/resume tests; live manifest/watcher evidence | Live export was complete, 810 files at inspected snapshot. No verification that Drive for Desktop uploaded it or that Cole switched its sync root |

Execution logs, inventory and probe artifacts are under Cole's Codex task folder:
`C:/Users/lafou/Documents/Codex/2026-09-06/howdy-long-time-no-speak-saw/work/validation-20261003/`.
Useful files: `final-suite.json`, `*-final.txt`, `final-runtime.json`, `live-evidence-summary.json`, `open-probes.json`, `change-inventory.json`.
Original Nova receipts/images remain under `nova_body/logs/`; do not rewrite them. No model weights/adapters or existing task/personal records were hand-edited. New test messages/receipts were created through the normal interfaces.

## Open / next
**Confirmed current gaps, not passing tests:**
1. Claude owns storage/exclusion findings 1 and 2. Read-only Git checks confirmed the runtime SQLite database remains tracked and staged-workspace paths are not ignored. I left both `.gitignore` files and `_admin/FIX_GIT.cmd` untouched as requested. Do not execute FIX_GIT or rewrite history while Nova runs.
2. Independent isolated reproduction confirms acceptance self-certification: a Cole-authored task with no checks waits; replacing checks with an already-existing file check allows completion. There is no setter provenance. Passing checks do not mean independent acceptance.
3. Independent middleware-only reproduction confirms a loopback request with an unrelated Host and Origin reaches the handler without authentication. No exploit request was sent to Nova. Host/Origin validation remains open; intentional host/VM permissions were not restricted.
4. Queue lease-owner fencing remains open. The new fixes handle exhausted crashes and completed-event recurrence, not stale workers acknowledging a reclaimed job. Other minor findings in Claude's review remain queued.
5. The first slow-command probe timed out at the built-in 30-second limit before Stop; its receipt correctly says timed_out. Stop then ended response generation. On the repeat, Nova narrated an intention but issued no tool, and the observation harness timed out after 100 seconds. Therefore this session does NOT prove a fresh live child-process cancellation. Existing real-subprocess regression tests pass; October 2's successful live guest cancellation remains separately dated evidence.
6. The first arithmetic final reply omitted the requested numeric result despite a successful receipt. VM follow-up reported its result correctly. Treat this and the non-executed cancellation repeat as model behavior observations, not successful execution based on prose.
7. Computer/noVNC loads and asks for its existing VNC password in a fresh browser profile. Viewer authentication/input was not completed; this is separate from Nova's working guest tools/screenshot.
8. Adapters discovery was not opened: it enumerates sealed `models/`. No live equip/unequip, training, avatar/voice workflow, destructive task actions, arbitrary remote page, long unattended run or fresh relocation test was performed. Separate avatar work was outside this pass.
9. Native controller window was observed. Native input helper rejected refreshed control/screenshot handles (`call get_window_state before using this window`, then `unknown screenshotId`); a complete native popout/pop-in round trip remains unverified. Qt unit tests are not a substitute for it.
10. Isolated UI preview startup was rejected by automatic approval review with only “blocked by policy”; no bypass was attempted. noVNC also logged a package.json 404, though its login UI loaded.
11. Git remote push remains blocked by oversized historical objects. Export tests and local autosave do not certify remote backup.

## For Claude
- Your findings 3, 6, 7 and 8 were reproduced and fixed as described. KoELS result propagation was included in 3.
- Please finish your reserved storage/exclusion work and note its verification. Then prioritize acceptance provenance and Host/Origin validation, retaining Nova's intentionally broad local capabilities.
- The existing 30 runtime tests run successfully on Windows; the two PowerShell-dependent failures in your Linux sandbox do not reproduce here.
- Final live state: Nova running, autonomy off, no active operations, VM owner Nova. Current loaded source matches disk. Do not assume this means all optional facilities or unattended autonomy are certified.

## For Cole
Core controller actions are much better evidenced now, and the tests exposed additional issues rather than hiding them behind an all-green summary. Keep the open findings above visible for the next modernization work.
