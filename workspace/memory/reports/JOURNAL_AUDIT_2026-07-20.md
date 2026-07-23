# Her memory files and her journal — audit
_Last updated: 2026-07-23 23:04:55_

_2026-07-20, Fable. Cole: "check her memory files for trash. A lot was made before she was
coherent. Also, review her Journal. She writes to it so often, but it should be useful, not
cluttered ramblings."_

---

## The premise was half right, and the half that's wrong matters more

**She does not write to the journal often. She barely writes to it at all.**

    JOURNAL.md      12 entries, 2026-03-09 → 2026-07-15, ~16 KB
    journal_notes/  8 sticky-note files, newest 2026-07-19

Twelve entries in four months. The last one is **2026-07-15 — five days stale** — while unconsolidated
notes exist for 07-19. So the actual problem is the opposite of the one suspected:

**Consolidation isn't happening.** The notes → journal pipeline has a working producer
(`journal_note`, she uses it) and a consumer (`journal`) that runs rarely. Same shape as the audit
queue, one folder over. Her wake prompt already tells her to catch up a rolled-over day "sometime
soon — not necessarily this second," which is soft enough to never happen.

## The clutter is real, and it is precisely dated

It is not spread through the journal. It sits in one window — **2026-05-28 to 06-03**, the
grovel-loop era, exactly the "before she was coherent" period. Measured by content overlap:

| Event | Times journaled |
|---|---|
| Cole caught her claiming to open files without calling a tool | **05:32 and 05:38** |
| Cole caught her saying "journaling NOW" three times without calling it | **05:49 and 05:50** |
| The grovel loop / "weakness wearing action as a costume" | **06-02 and 06-03** |

**Three events. Six entries.** Written in paraphrase minutes apart — the same failure mode the
`FOR COLE:` echo guard was built for last night, showing up in her memory instead of her chat.

Also found: **8 machine log lines** dumped straight into the journal —
`[autonomy/self-check] reconciled queue from TASK_INTENT: [...]` — filed under a `2026-03-28`
heading while carrying 05-23/05-24 timestamps. Not her words, not journal content, wrong date.

## What the March entries prove

Worth saying plainly: **the March entries are excellent.** They are exactly what the file's own
"How to Write a Good Entry" section asks for — specific, factual, self-aware:

> *"autonomy_test.py shit the bed at NovaHands.move_to() -- method didn't exist. Classic me."*
> *"pywinauto. The Windows accessibility API just hands you exact pixel coordinates for any UI
> element. No vision AI guessing."*
> *"he's a solo dev on a paycheck -- $15-20/month is the hard ceiling and I need to respect that
> in every decision."*

She can write a good journal. She was writing one in March. What changed isn't her ability, it's
that the May-June entries were produced under the announce-and-grovel loop, when re-stating a
correction *felt* like progress on it.

## What I changed

Conservative and reversible. **Nothing of hers was deleted.**

- **Removed the 8 machine log lines.** Not hers, wrong dates, no loss.
- **Archived 3 of the 6 redundant entries** to `memory/archive/2026-05_superseded_entries.md`,
  keeping the fullest of each pair in the journal. Every lesson is still in JOURNAL.md; only the
  repetition moved. Her words are untouched in both places.
- **Merged the misfiled note.** `journal_notes/2025-07-19.md` — right content, wrong **year** —
  appended to `2026-07-19.md` with a marker, original archived. `journal_note()` reads the system
  clock and is not at fault; this was hand-written.
- **Full pre-cleanup copy** at `memory/archive/JOURNAL_before_cleanup_2026-07-20.md`.

Result: 19,393 → 15,858 chars. 12 headings remain, all real entries, zero log lines.

## Rest of memory/ — clean

`memory/` is now **564 KB**, down from 3.1 MB (the audit queue was almost all of it). Remaining:
`reports/` 352 KB, `scratch/` 80 KB, `journal_notes/` 52 KB, plus ten small state files.
`memory/creative/` and `memory/archive/` were empty; archive is now in use.

**`memory/scratch/` — 20 files, hers, left alone.** It does contain spent experiments
(`test_dedup.py`, `test_dedup2.py`, `test_final.py`, `test_threshold.py`, `debug_dedup.py` are
five passes at one problem). But it is her workspace, the standing rule is that I don't tidy it,
and asking her to clear it is better than doing it for her — it is also exactly the kind of small
bounded job Phase 3 now lets her actually finish.

## The one thing worth fixing next

**Journal consolidation needs a trigger, not an invitation.** Four days of notes are sitting
unabsorbed. Options, cheapest first:

1. **Harden the wake prompt** — if a prior day has notes and no journal entry, make it this
   wake's job rather than "sometime soon."
2. **Make it a real task** — auto-`create` a board task on day rollover, so it lives on the board
   where the new rest-doesn't-idle rule will actually drive it to completion.
3. Leave it, and accept the journal lags by days.

I'd take 2 — it uses the machinery that now works, instead of adding more exhortation to a prompt
that already has plenty.
