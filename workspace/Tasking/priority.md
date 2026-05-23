# Nova Priority Queue
_Last updated: 2026-05-23_
_Managed by the autonomy server. Updated on: task created/advanced/completed, or Cole speaks._

---

## PRIORITY 0 — ABSOLUTE LAW (ALWAYS ACTIVE, CANNOT BE OVERRIDDEN)

**IF COLE SPEAKS — STOP EVERYTHING. RESPOND TO HIM FIRST.**

Cole's word is absolute. It supersedes every active task, every pending module
response, every queued action, every deadline, and every plan — no exceptions.

When Cole speaks or sends a message (Discord, Nova Chat, or any channel):
1. Halt all active tool calls and module requests immediately
2. Acknowledge Cole and respond to what he said
3. Resume only after Cole has been addressed AND has not given further instruction

No task priority level, no module output, no self-generated urgency, and no
external trigger overrides Priority 0. This rule is permanent.

---

## PRIORITY 1 — CRITICAL (time-sensitive, blocking)
_(Tasks that have hard deadlines or are blocking other work)_

_None active._

---

## PRIORITY 2 — HIGH (important, do soon)
_(Tasks that matter significantly but have some flexibility)_

_None active._

---

## PRIORITY 3 — MEDIUM (normal queue)
_(Standard work items in order of creation)_

_None active._

---

## PRIORITY 4 — LOW (background / when idle)
_(Tasks to work on only when nothing higher is pending)_
_None active._



- **Process pending audit_queue.json items** — audit_queue.json has 40+ unprocessed file operations (renames/deletes) from commit be877011 dated May 9th — all still marked 'pending' with no resolved_by. Need to verify which files actually exist/changed and mark each item as resolved or remove if already handled.
---

## BLOCKED — awaiting module responses
_(Tasks Nova has fired module calls for and are waiting on. Check Master_Inbox for updates.)_

_None active._

---

## SUSPENDED — paused intentionally
_(Tasks put on hold due to missing prerequisites, hardware, or Cole's instruction)_

_None active._

---

## DECISION LOG
- 2026-05-23 — Completed: **Clear Moondream task - delete master.md** — Cole explicitly said this was supposed to be deleted, not executed. Remove from active tasks and clear Tasking/Finished/cancelled/Moondream2/master.md if it exists.
- 2026-05-23 — Queue reset to a clean slate after the failed autonomy test (bogus/meta tasks removed, legacy Thoughts-folder artifacts archived). Fresh start for the next test under the new system.
_Append-only. Newest entries at top. Record every significant priority change here._

- 2026-05-23 — Completed: **TASK_MM_0513**: Download moondream2 vision model (model files already present).
- 2026-05-13 — Completed: **TASK_BG_0512**: patch_depth_server.ps1 — depth slider enabled in nova_qt.
- 2026-03-28 — Priority queue initialized.
