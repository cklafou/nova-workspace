# Standing chores wired to her board + `_admin` cleanup
_Last updated: 2026-07-21 07:29:37_

_2026-07-20, Fable. Cole: "Definitely fix what you wrote was a good idea to fix in your audit
file. Also, check _admin. I see a lot of junk that needs to be trashed."_

---

## Both recommendations implemented — and they were the same fix

The audit-queue report and the journal report each ended with three options, and I picked option 2
in both. They turned out to be one mechanism, because **both problems had the identical shape**:

| | producer | consumer |
|---|---|---|
| audit queue | `watcher.py`, every boot | `restructure.py --rename` — never run |
| journal | `journal_note`, she uses it | `journal` consolidation — rarely run |

Both were "addressed" by *asking nicely in a prompt*. Her wake prompt genuinely does mention
catching up a rolled-over journal day — as *"sometime soon, not necessarily this second"*, which
is soft enough to lose to anything else on any given wake, forever.

**So they become tasks.** `executive.ensure_standing_chores()`, called at the top of every wake
before she reflects:

- **Unconsolidated journal days** → creates *"Consolidate yesterday's journal notes"* (p2) listing
  the exact dates that have notes but no `JOURNAL.md` entry.
- **≥50 pending audit items** → creates *"Review pending audit-queue items"* (p3) telling her to
  actually call `resolve()`/`dismiss()` so the count drops.

**This only works because of last night's other fix.** Until the "rest lean no longer cancels
Phase 3" change, an open task was skipped on ~79% of wakes and a chore on the board would have sat
exactly as dead as a chore in a paragraph. The two compose: one makes her work open tasks, this one
gives her the right open tasks.

### Verified against the live board

    35 tasks, 0 open  →  ensure_standing_chores() → created [t60]

- Found **5** genuinely unconsolidated days: `2026-06-20, 06-21, 07-08, 07-14, 07-19`
  (more than the 4 I estimated in the journal report — 06-20 and 06-21 were also never absorbed).
- Audit chore correctly did **not** fire — 0 pending after the clear, threshold is 50.
- **Idempotent:** 7 consecutive calls produced exactly **1** open copy of each title. This matters
  at one wake every ~20 seconds; the naive version would have spawned hundreds overnight.
- **Fails safe:** if the board can't be read it returns `[]` rather than raising or spamming — a
  chore check must never be able to take down a wake.

Her board is no longer empty, which also means the rest-doesn't-idle fix stops being dormant.

---

## `_admin` cleanup

**`_admin/Training_stuff/v5/` → trash. 22 files, 640 KB.** Superseded by v6, and v6 is the live
adapter (`active_lora.json` → `nova_core_v6_epoch1.gguf`). Checked before moving: the only "v5"
mention in live code is prose inside a comment in `nova.py`, not a reference.

`_admin` is now **1.7 MB**, of which 640 KB is the trash folder itself.

### Deliberately kept

**`Training_stuff/v6/`** — the live adapter's training data, spec and results. Obviously stays.

**`Training_stuff/KoELS_Files/`** — I suspected `decision.py` was a stale copy of
`nova_cortex/loadout.py` and diffed them: **1% similar, 99 vs 204 lines.** Genuinely different
code. KoELS is dormant (gated on a gaming adapter that was never trained), not dead.

**The loose scripts** — `hallucination_gate.py`, `referent_check.py`, `mtp_ab_test.py`,
`nova_guardian.py`, `nightwatch.py`, `overnight_review.py`, and the setup helpers. All still
referenced, all small, and the standing gates earn their place.

**`autonomy_watch/`** — `guardian.log` (19 KB) and `REPORT.md` (36 KB) are live and still being
written. Worth a size-based roll eventually, same as the launcher log; not worth touching now.

---

## Where the workspace stands

| | start of cleanup | now |
|---|---|---|
| `memory/` | 3.1 MB | 564 KB |
| `_admin/` | 1.8 MB | 1.7 MB *(640 KB of it is trash pending your emptying)* |
| `logs/` | 33 MB | 28 MB |
| `audit_queue.json` | 2.6 MB / 6,563 items | 536 bytes / 0 items |
| `JOURNAL.md` | 19,393 chars, 8 log lines, 6 duplicate entries | 15,858 chars, 0 log lines, no duplicates |
| her board | 35 tasks, **0 open** | 35 tasks, **1 open** |

Everything moved this session is in `_admin/Trash/cleanup_2026-07-20/` with its original folder
structure intact. Nothing was deleted.
