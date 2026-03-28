# HEARTBEAT.md
# Nova's autonomous Thoughts cycle. Run this on every heartbeat trigger.
# Yield Protocol applies throughout: one action per turn, check in after each exec.

---

## Step 1 — Orient

Read your priority queue:

[READ: Thoughts/priority.md]

Note what is active, what is blocked, and what is highest priority.
If priority.md shows no active or blocked thoughts, skip to Step 5.

---

## Step 2 — Process Master_Inbox

Check whether any module responses have arrived:

```
exec: python -c "import os; p = 'Thoughts/Master_Inbox'; items = [f for f in os.listdir(p) if f.endswith('.md')]; print('\n'.join(items) if items else 'INBOX_EMPTY')"
```

If INBOX_EMPTY: skip to Step 3.

**File format** (written automatically by the inbox router in nova_chat/server.py):
```
{timestamp}_{author}_{task_id}.md
```
Example: `20260328_143022_Claude_Research_0328.md`

Each file contains:
- A `# Inbox Item: [TASK_ID]` header
- Author, timestamp, task ID metadata
- The full message content under `## Message`

For each item returned:
1. Read it: [READ: Thoughts/Master_Inbox/FILENAME.md]
2. The Task ID is in the filename and in the `# Inbox Item: [TASK_ID]` header.
   Match it to a Thought folder in `Thoughts/`. If no matching folder exists,
   the item is noise (e.g. an [ERROR] or system notice) — delete it and move on.
3. Route to the correct thought's inbox:
   ```
   exec: python -c "import shutil; shutil.move('Thoughts/Master_Inbox/FILENAME.md', 'Thoughts/THOUGHT_FOLDER/inbox/FILENAME.md')"
   ```
4. Open that thought's master.md and update:
   - Mark the module as "received" in the Pending Module Responses table
   - Append to the Decision Log: "[timestamp] — Received response from [module]. Routed to inbox."
5. Yield check after each move.

Process ONE inbox item per heartbeat turn if there are multiple. The next heartbeat handles the rest.

---

## Step 3 — Advance Highest-Priority Active Thought

Read the master.md of the highest-priority ACTIVE thought:

[READ: Thoughts/THOUGHT_FOLDER/master.md]

Review the Current Plan checklist. Find the first unchecked step.
Take ONE action toward completing that step.
After the action:
- Append to that thought's Decision Log what you did and what the result was.
- If the step is now complete, check it off in the master.md.
- If a new module call is needed, fire it and add it to the Pending Module Responses table with the Task ID echo format.

**Yield Protocol applies.** One action. Stop. Do not chain multiple steps in one turn.

---

## Step 4 — Update priority.md if needed

Only update priority.md if something changed:
- A thought moved from active to blocked (awaiting module response)
- A thought completed (move to Finished/, remove from queue)
- A deadline changed based on new information

Update via the Proposed Changes Protocol (copy to logs/proposed/ first) unless the change is minor enough to write directly.

---

## Step 5 — Final status

If all thoughts are complete or none exist: reply `HEARTBEAT_OK` and stop.
If work was done: briefly note what was advanced. Do not write a report. One sentence is enough.

---

## Cole's Additional Tasks
# Cole writes any one-off instructions below this line.
# When Cole adds something here, do it first (after Step 1), then continue the cycle.
# Remove the task from below once complete and tell Cole it is done.
