# v3 personality-LoRA package — pre-flight review
_Last updated: 2026-07-08 08:44:42_
_2026-07-07, Fable. Reviewed `_admin/Training_stuff/v3/` + build plan against the v2 overfit
diagnosis. **Verdict: GO** — with the runbook's three gates enforced and two notes below._

> **ADDENDUM, same day — both notes FIXED before handoff.** (1) `train_nova_lora_v3.py` now tries
> `assistant_only_loss=True` with a one-batch probe and falls back to full-sequence loss (v2
> behavior) on its own if TRL/the Qwen template can't mask; `NOVA_ASSISTANT_ONLY=0` is the escape
> hatch; a first-logged-loss of ~0.0 means a degenerate mask (fallback manually). Control flow
> unit-tested 4/4. (2) 8 verbatim-frame autonomy examples appended to `..._additions.jsonl` (now
> **59** rows; merged **167**, runbook updated): full `build_reflection` frames byte-matched to
> `executive.py` (stamp/RECENT CONVERSATION/last-reflection+MUST-move/board/journal/closing),
> change+interval+cole reasons, 2 verbatim sustained chains, 1 `build_decision` cole_pending
> REQUIRED-reply example. Re-validated: 167 rows, zero dupes, role alternation clean, longest
> ~2,071 tok < 4096. The runbook now also warns explicitly against uploading the two staging
> jsonl files. Package is handoff-ready as-is.

## What was checked (programmatic, not vibes)

**Dataset.** `nova_core_v3_additions.jsonl` = 51 rows, all valid JSON, uniform
`{"messages":[...]}` schema, shapes 23×2-msg / 2×4 / 23×6 / 3×8 = 22 wake-style + 20
conversational multi-turn + 9 register singles — matches the runbook's stated 20/22/9. Merged with
v2's 108: 159 rows, **zero internal dupes, zero v2 overlap, zero contamination** (no "Nova:"
prefixes, no `<think>` tags, no AI-disclaimer language, no non-English blocks). Durability rule
holds: no dates, versions, model names, file paths, or task names baked in ("Cole" by name in 5
rows — intended). Longest example ≈742 tokens → `max_length` 4096 has ~5× headroom. Assistant
reply length: additions mean 266 chars vs v2's 207 — same register, no essay drift.

**Quality (read, not just parsed).** Multi-turn examples genuinely advance per turn (no
restating); wake examples model existing-and-deciding rather than task-seeking, including
choose-to-rest and Cole-interrupt shapes; sustained chains quote the prior reflection back and
push it forward — exactly the v2 failure being targeted.

**Script** (`train_nova_lora_v3.py`): r16/α32 (2:1), 2 epochs, LR 1e-4 cosine + warmup 0.03,
bf16 frozen base, packing off, per-epoch saves, max_length 4096, same target modules as v2, seed
fixed. Matches the plan's fix for the r64/α128/4-epoch/2e-4 over-imprint. Runbook sequencing is
right: base-repo-id gate → MTP smoke test → balance top-up → train → per-epoch GGUF → local A/B
**at weight 1.0**.

**Staging vs shipping:** `nova_core_v3_autonomy.jsonl` (15) and `_sustained.jsonl` (4) are build
components — 18/19 rows already inside additions (1 was edited when merged; the edited variant is
present). **Upload only the three runbook files.** Concatenating the staging files too would
double-train those rows.

## Two notes (non-blocking)

1. **Loss masking.** SFTTrainer default trains on the full templated sequence — user turns
   included. Single-turn v2 didn't care; v3's wake examples have long user boilerplate that will
   soak loss and could teach her to *emit* wake-prompt-ish text. Rank 16 limits the damage, but on
   the pod try `assistant_only_loss=True` in `SFTConfig` first; if TRL/Qwen-template support
   errors out, proceed without it (v2 precedent) and let the A/B judge.
2. **Wake-frame fidelity is ~70%, deliberately.** The training wakes paraphrase `executive.py`'s
   real frame (tag shape, board-as-context, "one honest line" all present) but 0/22 use the
   literal `It is <time> (<time_of_day>)` line, 1/22 a `RECENT CONVERSATION` block, and reasons
   are nearly all "idle timer" (live wakes are mostly "change"/"cole"). Fine — disposition
   transfers, and verbatim boilerplate would risk parroting. But if the autonomy-continuation A/B
   underwhelms at 1.0, the first knob is a handful of wake examples that match the live frame
   verbatim, not more epochs.

## Mount quirk (ops note)
`_admin/Training_stuff/v2/` intermittently refuses reads in the sandbox; verified
`v2/nova_core_v2.jsonl` ≡ `v1/nova_core_v2.jsonl` (108 rows, matching content) via the file tools.
Either copy is the correct upload.

## Acceptance (unchanged, restated)
Coherent AND in-character at `--lora-scaled …:1.0` across 12+ varied turns, forced topic shifts,
callbacks, and a reflection→wake→advance chain, plus a sane idle test. If the best epoch still
needs <1.0, it's over-trained — iterate config/data, don't ship a dilution.
