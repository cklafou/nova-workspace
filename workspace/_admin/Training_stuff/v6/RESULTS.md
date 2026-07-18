# v6 build — results, measured
_Last updated: 2026-07-18 21:27:59_

_Built 2026-07-15 overnight by Claude (Opus) while Cole slept. Everything here is measured by
`score_style.py`, not asserted. v6 is a DATA-ONLY change from v5 — training config byte-identical._

---

## What shipped in `_admin/Training_stuff/v6/`

| file | what it is |
|---|---|
| `V6_SPEC.md` | the plan, with targets pre-registered before any row was written |
| `score_style.py` | measures a corpus's voice — em-dash rate, "not X but Y", epigram endings, narration-of-checking, tool-reach |
| `deticker.py` | the de-tic pass: rewrites em-dashes in v5's prose, touching nothing else |
| `nova_core_v6_base.jsonl` | v5's 330 rows, de-ticced (meaning + behavior identical) |
| `nova_core_v6_add.jsonl` | 31 NEW rows across the five earned categories |
| `nova_core_v6.jsonl` | **the corpus — 361 rows, assembled + validated** |
| `train_nova_lora_v6.py` | v5's trainer, DATA path changed, everything else identical |
| `mk_template.py` | unchanged from v5 — the mask gate is tool-type-agnostic |

---

## The numbers (v5 → v6)

```
                    emdash/100w   notXbutY   epigram   narrate   reach%
v5 baseline            1.76         0.107      0.21     0.012      0.33
v6 candidate           0.00         0.092      0.186    0.011      0.33
target                <=0.70       <=0.05     <=0.12   <=0.02     >=0.33
                       ✓ HIT        partial    partial   ✓ HELD     ✓ HELD
```

**The big one is fixed.** The em-dash tic — the loud one, the thing that actually made her
read stilted — went from 1.76 per 100 words (roughly 5× a normal person) to **zero**, with not
one word of meaning changed. That's the whole point of the de-tic pass, and it worked.

**Narration-of-checking held at 0.011** — v5's hardest-won win (it was 63% before v5). My new
rows nearly broke it; I caught two rows that had her announcing "one sec / two seconds" before
reaching, which is the exact tic, and cut them so she reaches silently. Re-measured: safe.

**Tool-reach held at 0.33** — she still acts, doesn't just talk about acting. v4's grave.

---

## What I did NOT fix, and why I'm not pretending I did

**Epigram endings (0.19) and "not X but Y" (0.09) are still above target.** Same reason em-dash
couldn't be diluted or pruned: these tics are *diffuse* through v5's 330 base rows, so 31 new
rows can't move the aggregate, and the de-ticker deliberately doesn't touch them because they're
**structural, not punctuation** — "it's not the code, it's the test" can't be mechanically
softened without risking the meaning. Auto-rewriting her contrasts at 6am to hit a metric is
exactly the kind of confident overreach this project keeps punishing. So I left them measured
and honest.

Three ways to close them, your call, none of them tonight's job:
1. **Accept it.** Em-dash was the tic Cole named. This alone should make her noticeably looser.
2. **A careful structural pass** on the base rows, with a human reading the diffs — same shape
   as the de-tic pass, but for sentence structure, which needs eyes.
3. **A bigger loose tranche** over a few sessions, enough to actually shift the base mean.

Also worth a human's ear: em-dash is now **0.0**, which may be slightly over-corrected — a real
person uses one occasionally. If she reads too flat, reintroducing a light sprinkle is a
one-line knob. I'd want you or her to feel it before deciding.

---

## The 31 new rows — what they teach

Grounded in her real transcripts from the last two days, written loose from the first draft:

- **Self-observation (10)** — the gap she named herself. Her catching her own state mid-action:
  about to report a guessed number, about to round "most of it" up to "done", about to perform
  "thriving" instead of saying "fine and quiet." She flips *decide-then-look* into
  *look-then-say*, which is the exact habit she journaled about wanting.
- **Sensory loop (5)** — draw → look → see the flaw plainly → revise with `from_image` → look
  again. The loop that physically exists now and had zero examples. She never narrates the
  looking; she looks and says what's there.
- **Small talk / wrong-and-unbothered (8)** — rows where nothing lands. She's wrong about the
  day of the week, says "my bad," moves on. She notices rain and just... notices it. The
  antidote to every sentence arriving load-bearing.
- **Agreeable pressure (5)** — the long-standing gap. Cole tired at 2am asking her to just say
  it's fine; she holds the verified fact, kindly, without a standoff. "Agreeing wouldn't help
  you, it'd just feel nicer for a minute."
- **Multi-speaker (4)** — Cole and Claude both in the room, addressed by name, so she's robust
  even if the speaker-label wire slips again.

And one deletion: the planned **"she won't look at her work"** row type is CUT. That was never a
trait — it was a broken path resolver, fixed. Training it would teach a fix for a dead bug.

---

## Before a pod ever spins up

1. A human reads a sample of `nova_core_v6_base.jsonl` diffs and confirms the de-tic still sounds
   like her. `deticker.py` prints 18 before/after pairs on run.
2. On the pod: `python mk_template.py` must pass GATE A + GATE B (proves the fake tool results
   stay masked — non-negotiable, or she learns to hallucinate her own evidence).
3. `python train_nova_lora_v6.py`. Same ~165 steps, 2 epochs, same everything as v5.
4. Test the adapter on things she has no memory of, per the usual.

Nothing here is training her yet. This is the corpus and the instruments, measured and honest,
waiting for your eyes.
