# Nova Priority Queue
_Last updated: 2026-05-13_
_Managed autonomously by Nova. Updated on: task created, task completed, module response received, deadline changed, or Cole speaks._

---

## PRIORITY 0 — ABSOLUTE LAW (ALWAYS ACTIVE, CANNOT BE OVERRIDDEN)

**IF COLE SPEAKS — STOP EVERYTHING. RESPOND TO HIM FIRST.**

Cole's word is absolute. It supersedes every active task, every pending module
response, every queued action, every deadline, and every plan — no exceptions.

When Cole speaks or sends a message (Discord, Nova Chat, or any channel):
1. Halt all active tool calls and module requests immediately
2. Acknowledge Cole and respond to what he said
3. Record the current state of any interrupted task in its master.md before
   touching anything else (so work is not lost)
4. Resume only after Cole has been addressed AND has not given further instruction

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

- **Clear Moondream task - delete master.md** — Cole explicitly said this was supposed to be deleted, not executed. Remove from active tasks and clear Tasking/Finished/cancelled/Moondream2/master.md if it exists.
- **TASK_AUDIT_0513**: Review memory/audit_queue.json for pending rename/delete events from commit be877011. Run restructure.py or manual cleanup as needed.
  - Created: 2026-05-13 (autonomous cycle)
  - Status: active

  - Created: 2026-05-23 (Cole request)
  - Status: queued

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
- 2026-05-23 — Completed: **TASK_MM_0513**: Download moondream2 vision model using download_models.py script to models/ directory.
- 2026-05-13 — Completed: **TASK_BG_0512**: Run patch_depth_server.ps1 from workspace root to enable depth slider in nova_qt. Verify server.py and nova.py were patched correctly.
_Append-only. Newest entries at top. Record every significant priority change here._

- 2026-05-13 — Autonomous cycle: Added TASK_AUDIT_0513 (audit_queue.json review) to PRIORITY 4 queue, immediately started execution.
- 2026-03-28 — Autonomous cycle: Added TASK_BG_0512 (patch_depth_server.ps1) to PRIORITY 4 queue.
- 2026-03-28 — Priority queue initialized. Thoughts system created.