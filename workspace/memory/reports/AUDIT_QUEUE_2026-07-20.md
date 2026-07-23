# The audit queue — 6,563 items, none of them anyone's fault
_Last updated: 2026-07-23 19:51:37_

_2026-07-20, Fable. Cole: "clear her queue completely and look into why that queue exists and what
is needed to be done to fix this problem for the future."_

**Cleared: 6,563 → 0. 2.6 MB → 536 bytes.** `memory/` went from 3.1 MB to 564 KB.
Root cause fixed in two places so it cannot silently refill.

---

## What the queue is for

`watcher.py` runs as part of the stack and auto-commits on file changes. After each commit it
diffs against the previous one and records renames, deletes and new files into
`memory/audit_queue.json`, so that `restructure.py --rename` can later fix any references that
the rename broke. `audit_scripts.py` surfaces anything still pending as a HIGH REVIEW flag.

That is a reasonable design. Nothing about the idea is wrong.

## Why it reached 6,563

**Three failures stacked, and each one alone would have been survivable.**

### 1. The producer runs always; the consumer runs never

`watcher.py` is launched by `nova_start.py` on every boot — **always on**.
`restructure.py --rename` is the only thing that calls `resolve()`, and it is **never invoked
automatically** by anything in the stack. So items went in and nothing ever took one out.
Two months, zero resolutions.

### 2. The cap was unenforceable

`MAX_QUEUE_SIZE = 500` existed the whole time. Here is why it never fired:

```python
closed = [i for i in items if i["status"] != "pending"]
remove_ids = {i["id"] for i in closed[:to_remove]}
```

`_prune` only ever removed items that were **already closed**. With nothing resolving anything,
`closed` was always empty, `remove_ids` was always empty, and the cap capped nothing.

**A bounded buffer whose bound depends on a consumer that may not exist is not bounded.**

### 3. And the real volume driver: it was auditing a database

**5,306 of the 6,563 items — 81% — were `nova_memory_db/`**, her LanceDB vector store. That
directory rewrites its internal data files every time she remembers something, so every commit
filed dozens of "new file" and "deleted file" reviews. The queue was asking a human to review a
database's storage churn.

The exclusion lists to prevent that already existed. `watcher.py` has `EXCLUDE_DIRS` and
`EXCLUDE_SUBPATHS` and applies them to what it *indexes* — but the audit path reads
`git diff --name-status` output directly and queued every line raw. **The filter was sitting right
there and simply wasn't applied on this one path.**

---

## The fixes

**`watcher.py` — filter at source.** New `AUDIT_EXCLUDE_PREFIXES` (`nova_memory_db/`,
`prompt_cache/`, `logs/`, `models/`, `.nova_app_profile/`, `_admin/Trash/`, `_archive_`,
`_QUARANTINE_`) plus `_audit_should_skip()`, which also honours the existing `EXCLUDE_DIRS` /
`EXCLUDE_SUBPATHS`. Applied **once**, immediately after each diff line is parsed, so every event
type is filtered by the same rule rather than each branch remembering to.

**`audit_queue.py` — make the cap real.** `_prune` now, in order: ages out pending items older
than 14 days; then drops closed items; then, if still over the cap, **drops the oldest pending
too**. That last clause is the line the old code was missing and its absence was the whole bug.

Dropping unreviewed items is lossy, so it **says so on stdout** rather than doing it quietly:

    [audit_queue] queue over 500; dropping 400 oldest PENDING item(s) — unreviewed.

Silence about discarded data is how you end up trusting a queue that has been throwing things
away for a month.

---

## Verified against the real 6,563 items before clearing

| check | result |
|---|---|
| filter replayed over the actual queue | **6,563 → 666. 89.9% eliminated at source** |
| what legitimately survives | `_admin` 291, `memory` 114, `nova_art` 74, `nova_body` 65, `general_tools` 26 |
| 900 all-pending items, nothing resolved | capped at 500 *(old code kept all 900)* |
| 50 stale + 10 fresh pending | aged out to 10 |
| 20 fresh, under cap | untouched |
| over cap, only pending | drops oldest, announces the loss |
| 12 path cases (skip vs keep) | 12/12 — real code paths like `nova_body/nova_cortex/executive.py` still queue correctly |

Schema left intact and valid after clearing: `version: 1`, `items: []`.

---

## What still deserves a decision

**Nothing resolves items — that is unchanged.** The queue is now bounded and quiet instead of
unbounded and noisy, but the ~666-per-two-months of *legitimate* events still have no consumer.
Three honest options:

1. **Wire `restructure.py --rename` into the loop** so renames actually get their references
   fixed. The original intent, and the only one where the queue earns its keep.
2. **Give Nova the job.** She has hands and a forge now, and "which references did that rename
   break?" is exactly the kind of bounded, verifiable work Phase 3 is for.
3. **Decide it isn't worth it** and turn the audit off in `watcher.py`. Cheapest, and no worse
   than the last two months.

I'd pick 2, but it's your call and it isn't urgent now that the thing is bounded.

## Also trashed this pass

The items that were blocked while she was running: the two in-use `__pycache__` dirs in
`nova_forge/`, and `logs/nova_launcher.log` (5.6 MB, 07-13 → 07-20 — a fresh one starts on next
boot). Total across both cleanup passes was 131 files / 13 MB, which you have since emptied.
