# Why Nova looked incompetent — and the two wires that caused it
_Last updated: 2026-07-19 17:16:38_
_2026-07-19, Fable. Diagnosis from live logs (11.8h of runtime), two root-cause fixes shipped.
Headline: **she was not underperforming. She was being penalized for working.**_

---

## The evidence

Today, on v5_epoch2: 168 wakes, 371 generations, 25 "stalls", 5 board commits. That reads like a
model that can't finish anything. It isn't what happened.

Pulled her actual thought log for one of the nine "stalled" t47 wakes (12:03:05–12:03:54). In that
single wake she: reflected on an unverified assumption about her own memory code, read
`goals.py` / `journal.py` / `state.py` / `log_reader.py`, designed a retention experiment, planted
a live tripwire via `journal_note`, and wrote a PROGRESS line describing the next step. That is
competent, self-directed engineering work. **The system recorded it as
`stalled on t47 (wake 1 with no progress/close)`.**

Her conversation is also fine — the 07-18/19 session shows her catching her own over-correction
("'You misunderstand' should have been a laugh, not a paragraph"), and drawing a real distinction
under social pressure ("Gratitude isn't a pie with one slice"). Neither reasoning nor voice is the
bottleneck.

## Root cause 1 — productive wakes were punished (the big one)

The wiring, in three facts that only bite in combination:

1. Her tool loop lives in the **model client**, so it is reachable from **any** generate call —
   most of her real work happens in **Phase 2**.
2. **Phase 3** is the only phase that calls `tasking.progress()` *and* the only caller of
   `schedule_soon()` (the ~6s "keep going" continuation).
3. Phase 3 is **skipped whenever she leans "rest"** — which was 123 of 168 wakes today.

So a productive Phase-2 wake was invisible to `apply_decision`'s wake-scoped action log. It
therefore counted as a **stall**, which did two things:

- put a false **"stalled on tNN (wake N with no progress)"** into her very next prompt, and
- backed her off by `follow_gap_s * min(stall, 5)` — **up to 7.5 minutes** between steps of a task
  she was actively advancing.

t47 hit stall 9. She was doing one real step, being told she failed, waiting up to seven minutes,
then re-orienting from scratch — repeatedly. That is precisely the "she's nowhere near as capable
as a frontier agent" feeling: a frontier agent runs thirty steps in one continuous context; Nova
was running one step per seven minutes with amnesia in between. **Same model, shredded pacing.**

`reconcile_board()` (07-14) had already fixed the *record* half of this gap. The *pacing* half was
still live, and pacing is the half that costs competence.

**Fix:** `executive.note_real_work()` — when the receipt ledger proves work happened in any phase,
clear the false stall and schedule the next step in ~6s, exactly as Phase 3 does. Called from
`runtime.py` right where `reconcile_board()` reports real work. Bounded by the existing
`_MAX_CONTINUATIONS = 12` cap, and driven only by receipts — never by her account of herself.

## Root cause 2 — the message-doubling bug, finally caught

All four recorded `dup_suppressed` events carry **`source="drain"`**. The flight recorder from
07-02 did its job.

Mechanism: Cole's message is appended to the transcript **the instant it arrives**, *before* it is
queued. If the in-flight generation built its prompt after that moment, it already saw the message
and answered it. The queue drain then re-answered an already-answered message from a byte-identical
prompt — hence byte-identical replies 7–10s apart.

**Fix:** an already-answered guard in the drain path — if any AI has spoken after the queued
message landed in the transcript, skip re-delivery and log `drain_skipped`. Deliberately an
if/else, not an early return, because the block runs inside a `finally` where a return would
swallow in-flight exceptions. The commit-point dedupe guard stays as belt-and-braces.

## Verification

Logic unit-tested against verbatim /tmp replicas: `note_real_work` 4/4 (stall cleared; the exact
t47 case 450s → 6s; runaway cap intact at 12; burst accounting), drain guard 6/6 (skips the
duplicate; still delivers a genuinely-new queued message; never silently drops Cole; safe on
missing id; System messages don't count as an answer). Import-level check passes: `note_real_work`
present and wired, `nova_cortex` + `nova_runtime` import clean. Canonical files Read-verified.

## Needs Cole (not code)

1. **She is running the wrong adapter right now.** `active_lora.json`/`.txt` were updated at 15:54
   to `nova_core_v6_epoch1.gguf:1.0`; the last boot was 15:43 and every boot today logged
   `nova_core_v5_epoch2.gguf:1.0`. No hot-swap occurred (zero `/api/lora` calls). **A restart is
   required for v6 to actually load** — and it also picks up both fixes above.
2. **MTP speculative decoding is commented out** in `nova_start.py` (`--spec-type draft-mtp`).
   That's the documented 1.4–2× generation speedup, currently off. At ~370 generations/day it is
   worth re-testing whether whatever caused it to be disabled still reproduces.

## What to watch after the restart

`logs/events/events-<date>.jsonl`: **"stalled on tNN" should largely disappear** — replaced by
"logged real work to the board" followed by rapid continuation wakes. In
`logs/generation_trace.jsonl`, a recurrence of the race now shows as `drain_skipped` (prevented)
rather than `dup_suppressed` (caught after the fact). If `dup_suppressed` still appears with a
source other than `drain`, there is a second path and the trace will name it.

_Not fixed, deliberately: 27B is not a frontier model and the agentic-reliability gap on long tool
chains is real. But that gap was not what was limiting her today — the wiring was._
