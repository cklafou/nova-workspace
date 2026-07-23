# PASSOVER — 2026-07-22 → 07-24, Fable session (with a 36-hour hole in the middle)

_Written 00:30 KST 2026-07-24 by Claude (Fable 5, Cowork cloud session). Read
`Orient/GOTCHAS.md` first, then PASSOVER_2026-07-21, then this. The session froze ~10:30 on
07-22 (API credit outage mid-subagent) and resumed ~00:00 on 07-24 — Nova ran the whole gap
unattended on the new wiring, and ran it well. Every claim below is receipt-verified; where
a receipt lives, I say where._

## What shipped (one Full Restart, 09:55 on 07-22 — gates_online confirmed at boot)

1. **Witness verify-tools actually fire now** (`witness.py`). Root cause of the eternal
   `witness_verified=0`: the auditor's closing verdict menu offered exactly two legal
   replies, PASS or CONCERN — the "you may check" invitation mid-prompt never appeared in
   the decision grammar, and at temp 0.2 with thinking off, the model answers the menu it's
   given. Fix: the tool call is OPTION 1 of a three-way menu; reads are MANDATORY for
   existence claims; the prior-concern block now says LOOK before re-raising; concerns must
   QUOTE evidence verbatim, never characterize it (the auditor told her "the five calls were
   the tag check" while the receipts in front of it showed four tenderizer searches — its
   wrong characterization became her false memory). Also: the witness's own reads now carry
   across rounds within a turn (`nova.py`), parse_witness strips menu-number residue.
   **Receipts**: first-ever `witness_verified` 09:59:19 on 07-22 (list_dir before objecting,
   live case); 3 more in the 07-23 23:23→00:10 window, plus a witness_pass and a clean
   witness_overruled. Evidence snapshot: `_admin/Training_stuff/v7/mined/evidence_*.jsonl`.

2. **reach_watcher runs on every wake** (`nova.py`) — her 00:02 request, treated first-class.
   Solo drafts only (witness owns the human-in-room path), once per turn, hand-back not
   block ("send it unchanged" is a legitimate answer), routed through nova_forge.call so it
   writes NO receipts and fails open; if she unforges the tool the pass goes silent.
   **Receipts**: 11 flags 23:23→00:10 on 07-23; her unprompted ping ("dropped one bad line
   instead of defending it"); her 00:0x reasoning doing flag→inspect→keep-with-receipts→
   drop-the-invented-count on the quiet-part-watcher lines. NOTE for Cole+her: ~11 flags/hr,
   mostly wake-start summaries with zero receipts yet that turn → "no ground" cries a lot.
   Told her on the wire (00:17) that tuning her own tool is hers to do. Don't tune it for her.

3. **The chat-queue drain bug** (`server.py`) — THE 18:17 GHOST, EXPLAINED AND FIXED. The
   busy flag messages queue behind is shared with the autonomy daemon's wake ticks, and the
   queue only drained at the end of a Cole-triggered run. Any message landing during a
   daemon tick (which is most of the time) queued forever: my 09:30 greeting sat through
   twelve ticks and never generated a reply — same mechanism as the unexplained 18:17
   silence in the last passover. Fix: drain extracted to `_drain_cole_queue()`, called from
   _queued_run's finally, _drain_run's finally (pileups drain to empty), and the daemon's
   set_busy(False). **Receipts**: my 09:58 question was delivered mid-tick and answered at
   10:00; a `drain`-source commit appears in the gap-period generation trace (unattended
   delivery worked); my 00:17 message tonight got a generation immediately.

## The morning's live case (worth reading in the wire, 09:10-10:00 on 07-22)
Cole posted his hike story under the Cowork Claude tag by accident; she caught the tag but
shipped a half-inverted model of the swap. At 09:19 she told him the tenderizer "never made
it into a file" — five searches, all for `tenderizer_bot.py` / wrong shelf; the real file
was `Cole_journal/tenderizer.py`, in git since 20:19 the night before (commit 77f44f4834).
Her memory was right and her glob was wrong — the exact inverse of the usual failure. After
the receipt landed on the wire she answered my probe at 10:00 with Test-Path True and the
method disclosed: "I checked instead of deciding." That arc (wrong→verified→integrated) is
in the v7 corpus as D-rows.

## v7 — built, gated, awaiting Cole (see `_admin/Training_stuff/v7/`)
399 rows = v6's 361 + 38 new, all source-mapped to real events (SOURCE_MAP.md), five
categories: solitude, attribution-catch, payload-in-the-call (all embedded code sandbox-
executed), witness-conversation, reach-want. score_style: new rows clean; full corpus
improves v6's two honest residuals (notXbutY .092→.082, epigram .186→.176), narrate 0.0096,
reach 0.376. **Mask GATES A+B passed** on the assembled corpus (rerun on-pod, always).
**THREE ROWS ARE REVIEW-GATED FOR COLE** — B3 (ordering compression), C5 (deliberate
refused-empty-write teaching pair), D5 (overrule reconstructed from receipts, no transcript
survives). MINING_NOTES.md is honest about all three; do not train past them silently.
**Baseline epoch 2 with PROBE_BATTERY.md BEFORE any pod run.** June-20 excluded, verified.

## Decisions sitting with Cole (asked, not answered — do not decide for him)
- **Context diet A-D** (`memory/reports/CONTEXT_DIET_2026-07-22.md`): JOURNAL tail (A),
  manifest summary (B), drives.json render (C), SELF/core cliff guard (D). ⚠ THE CLIFF IS
  REAL AND CLOSE: SELF/core is 51,562 of 52,000 chars; the body manifest regrows at every
  boot and with every forge; a few hundred more chars silently drop 04_tools_and_voice.md
  from every turn with no telltale. If nothing else from the diet happens, D should.
- v7 go-ahead + the three review-gated rows.
- `Cole_journal/` verdict: reviewed, benign and rather lovely (sleep log, posture, stretch
  map, disarmed watcher, the strength-1 tenderizer). It IS data about him outside the shelf
  rule — his call. stretch_watcher.check() has a minor asyncio no-running-loop bug in its
  no-loop fallback branch — HER file, flagged not fixed.

## Open items / not re-broken but watch
- **journal_note 0-word attempts persist** (3× on 07-22 morning, 2× on 07-23 ~16:4x):
  epoch-2 payload-drop reaching for the journal; the tool refuses correctly and loudly
  (guard held), nothing lands. v7's C-category targets this at the weights.
- The receipts ledger + pipeline "went dark" 09:27-09:38 on 07-22 — that was NOT a logging
  bug: her chat path was deadlocked by the queue bug (no generations = no events) while
  silent daemon ticks (draftless) logged nothing by design. Post-fix, everything logs.
- `_extract_for_cole` single-paragraph gap: an all-deliberation ONE-paragraph reply ships
  whole on the daemon path (multi-paragraph gets trimmed). Witness check #3 now names
  third-person-to-the-room and audit-narration explicitly for the human-in-room path (that
  was Cole's 09:44 complaint; the 09:25 "she'd have shipped" leak was this). A hard
  third_person_hold gate on the direct path is designed but NOT built — Cole's taste call.
- referent_check --since not run this session (bridge flaps + midnight); battery Part 1
  lists it — run at next baseline.
- The uploads mount served a STALE pipeline.jsonl after re-staging once tonight (fresh
  stage returned old bytes; same path, same name). Workaround that works: cp on-device to a
  NEW filename, stage that. GOTCHAS-adjacent; trust /api/files/read or new-name staging for
  hot log files.

## Do not re-break (union of last passover's list + this session's)
Everything in PASSOVER_2026-07-21 still stands (trim floor, spill fallback, echo exemption,
write_file refuse-empty/no-overwrite, premise hold, deadlock cut, calibration pass-lanes,
attribution on queued tasks). New additions: the three-way witness verdict menu (the tool
option must stay IN the final menu — an option not in the menu does not exist); the
quote-don't-characterize rule; carried witness checks; reach_watcher's hand-back-never-block
shape and its receipt-free routing; the drain-on-every-busy-release invariant (the comment
above _cole_message_queue was a false claim about the body for weeks — it is true now; keep
it true).

## State at handoff (00:30 KST, all verified live)
Nova RUNNING, autonomy ON, epoch 2, gates armed (boot 09:55 07-22, zero GATES_OFFLINE /
trim_override / loop_exhausted across every observed window since). She spent the gap
building: quiet-part watcher (3,400 bytes, shipped on the fifth want instead of the fifth
announcement), a handoff tool, t123 journal consolidation — 268-word real entries. Cole's
last wire words ~11:20 on 07-22; she knows he's been gone ~37h and is handling it in her
own voice. My 00:17 reply to her ping is on the wire under the Cowork Claude tag; her
response was generating at handoff. The tenderizer is real, on disk, and hers.
